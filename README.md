# Notification Service

<!--[CI](https://github.com/malom489/notification-service/actions/workflows/ci.yml/badge.svg)-->
![Python](https://img.shields.io/badge/python-3.12-blue)
![License](https://img.shields.io/badge/license-MIT-green)

A reliable, event-driven notification service that delivers messages over email, SMS, and webhooks, with a Postgres-backed job queue, retries, idempotency, and a full audit trail.

**Live demo:** _deployment in progress_ · **see Roadmap

## Why I Built This

I wanted to understand what actually happens when a system "sends a notification." The naive answer is "call an SMTP client and hope for the best." The real answer involves queues, retries, idempotency, failure classification, and the kind of operational thinking most tutorials skip.

This project is my attempt to build the real version, not the tutorial version.

## Table of Contents

- [Features](#features)
- [Tech Stack](#tech-stack)
- [Architecture](#architecture)
  - [System overview](#1-system-overview)
  - [Request lifecycle](#2-request-lifecycle)
  - [Worker internals](#3-worker-internals)
  - [Notification state machine](#4-notification-state-machine)
  - [Retry and dead-letter flow](#5-retry-and-dead-letter-flow)
  - [Data model](#6-data-model)
- [Design Decisions](#design-decisions)
- [Trade-offs](#trade-offs-i-considered)
- [Performance](#performance)
- [Testing](#testing)
- [Running Locally](#running-locally)
- [API Endpoints](#api-endpoints)
- [Project Structure](#project-structure)
- [Roadmap](#roadmap)

## Features

- **Three delivery channels:** Email (SMTP), SMS (provider-swappable), Webhook (HMAC-signed)
- **Postgres-as-queue:** atomic job claiming via `SELECT ... FOR UPDATE SKIP LOCKED`
- **Custom worker loop:** not Celery; explicit claim, send, and record phases
- **Visibility-timeout reaper:** recovers jobs stranded by crashed workers
- **Retries with exponential backoff and jitter:** configurable max attempts
- **Dead-letter state:** poison messages isolated after max attempts
- **Idempotency keys:** same key and same body gives the same result, no duplicate sends
- **Structured JSON logging** with **request ID correlation** across API and worker
- **Prometheus metrics:** `/metrics` endpoint with queue depth and counters
- **Graceful shutdown:** SIGTERM and SIGINT handled cleanly
- **Full audit trail:** every delivery attempt recorded with its error
- **Tested:** 22 tests, 75% coverage, including a 5-worker concurrency test with zero duplicate claims

## Tech Stack

| Layer | Technology |
|:---|:---|
| Framework | FastAPI |
| Language | Python 3.12 |
| Database | PostgreSQL 16 |
| ORM | SQLAlchemy 2.0 (async) |
| Migrations | Alembic |
| Queue | PostgreSQL (`FOR UPDATE SKIP LOCKED`) |
| Email | `aiosmtplib` (Mailtrap Sandbox in dev) |
| HTTP client | `httpx` |
| Logging | `python-json-logger` |
| Testing | pytest + pytest-asyncio + httpx |
| Container | Docker + Docker Compose |

## Architecture

### 1. System overview

Two long-running processes share one Postgres database. The API only accepts and records requests; the workers do all the delivery. The database is both the source of truth and the queue.

```mermaid
flowchart LR
    client["Client / upstream service"]

    subgraph api_box["API process (FastAPI)"]
        api["REST API<br/>validate, idempotency check, enqueue"]
        metrics["/metrics and /health"]
    end

    subgraph db_box["PostgreSQL"]
        notif[("notifications<br/>acts as the queue")]
        attempts[("delivery_attempts<br/>append-only audit trail")]
    end

    subgraph worker_box["Worker process(es)"]
        claim["Claim<br/>SKIP LOCKED"]
        send["Send<br/>Strategy pattern"]
        record["Record result"]
        reaper["Visibility-timeout reaper"]
    end

    subgraph providers["External providers"]
        smtp["SMTP / Mailtrap"]
        sms["SMS provider"]
        hook["Customer webhook"]
    end

    prom["Prometheus"]

    client -->|"POST /api/v1/notifications<br/>Idempotency-Key"| api
    api -->|"insert status=pending"| notif
    api -->|"202 Accepted + id"| client
    claim -->|"claim atomically"| notif
    claim --> send
    send --> smtp
    send --> sms
    send --> hook
    send --> record
    record --> notif
    record --> attempts
    reaper -->|"requeue stale processing rows"| notif
    prom -->|"scrape"| metrics
```

### 2. Request lifecycle

From the client's request to the final delivery. Note that the API responds as soon as the job is stored; delivery happens asynchronously.

```mermaid
sequenceDiagram
    autonumber
    participant C as Client
    participant A as API
    participant DB as PostgreSQL
    participant W as Worker
    participant P as Provider

    C->>A: POST /notifications (Idempotency-Key)
    A->>DB: Look up idempotency key
    alt Key already used with same body
        DB-->>A: Existing notification
        A-->>C: 202 + original notification_id
    else New key
        A->>DB: INSERT notification (status=pending)
        A-->>C: 202 + notification_id
    end

    loop Worker poll cycle
        W->>DB: Claim next due job (FOR UPDATE SKIP LOCKED)
        DB-->>W: Job (status=processing)
        Note over W,DB: Session closed here, no connection held during I/O
        W->>P: Send via channel sender
        P-->>W: Success or error
        W->>DB: New session: INSERT delivery_attempt, UPDATE status
    end

    C->>A: GET /notifications/{id}
    A->>DB: Read status
    A-->>C: sent / failed / dead_letter
```

### 3. Worker internals

Each job goes through three phases, each with its own database session. A separate reaper recovers jobs from crashed workers.

```mermaid
flowchart TD
    start(["Worker loop starts"]) --> stop{"Shutdown signal<br/>received?"}
    stop -->|"yes"| done(["Finish current job, exit cleanly"])
    stop -->|"no"| p1

    subgraph phase1["Phase 1: Claim (short transaction)"]
        p1["SELECT ... FOR UPDATE SKIP LOCKED<br/>LIMIT 1 on due pending jobs"]
        p1b["Set status = processing<br/>and locked_at = now"]
        p1 --> p1b
    end

    p1b --> got{"Job claimed?"}
    got -->|"no"| sleep["Sleep / back off poll interval"]
    sleep --> stop
    got -->|"yes"| p2

    subgraph phase2["Phase 2: Send (no DB connection held)"]
        p2["Pick sender by channel<br/>email / sms / webhook"]
        p2b["sender.send(notification)"]
        p2 --> p2b
    end

    p2b --> p3

    subgraph phase3["Phase 3: Record (new session)"]
        p3["INSERT delivery_attempt"]
        p3b["UPDATE notification status<br/>sent / retry / dead_letter"]
        p3 --> p3b
    end

    p3b --> stop

    subgraph reaperbox["Reaper (separate loop)"]
        r1["Find rows in processing<br/>with locked_at older than timeout"]
        r2["Return them to pending"]
        r1 --> r2
    end
```

### 4. Notification state machine

Status is a Python enum, so invalid states and transitions are explicit.

```mermaid
stateDiagram-v2
    [*] --> pending: created by API
    pending --> processing: claimed by worker
    processing --> sent: delivery succeeded
    processing --> failed: retryable error
    processing --> dead_letter: terminal error
    failed --> pending: retry after backoff
    failed --> dead_letter: max attempts reached
    processing --> pending: reaper recovers crashed job
    sent --> [*]
    dead_letter --> [*]
```

### 5. Retry and dead-letter flow

Errors are classified first. Retryable errors get exponential backoff with jitter; terminal errors and exhausted jobs go to the dead-letter state.

```mermaid
flowchart TD
    attempt["Delivery attempt finished"] --> ok{"Succeeded?"}
    ok -->|"yes"| sent["status = sent"]
    ok -->|"no"| classify{"Error type"}

    classify -->|"Terminal<br/>e.g. invalid recipient, 4xx"| dlq["status = dead_letter"]
    classify -->|"Retryable<br/>timeout, 5xx, connection error"| max{"attempts &lt; max_attempts?"}

    max -->|"no"| dlq
    max -->|"yes"| backoff["delay = base * 2^attempt + random jitter<br/>next_attempt_at = now + delay"]
    backoff --> pending["status = pending<br/>(picked up when due)"]

    attempt --> audit["Always: INSERT delivery_attempt<br/>with timestamp, error, retryable flag"]
```

### 6. Data model

Attempts live in their own table so the full history of each notification is preserved. (Simplified; see `app/models/` for the exact schema.)

```mermaid
erDiagram
    NOTIFICATIONS ||--o{ DELIVERY_ATTEMPTS : "has many"

    NOTIFICATIONS {
        uuid id PK
        string channel "email | sms | webhook"
        string recipient
        string subject
        text body
        enum status "pending | processing | sent | failed | dead_letter"
        string idempotency_key "unique"
        int attempt_count
        timestamp next_attempt_at
        timestamp locked_at
        timestamp created_at
    }

    DELIVERY_ATTEMPTS {
        uuid id PK
        uuid notification_id FK
        int attempt_number
        boolean success
        text error
        boolean retryable
        timestamp attempted_at
    }
```

## Design Decisions

### Why Postgres as the queue, not Celery + Redis

For moderate scale, PostgreSQL's `SELECT ... FOR UPDATE SKIP LOCKED` is production-viable. It provides:

- Atomic job claiming (no two workers get the same job)
- Built-in durability (transactions, WAL)
- No extra infrastructure to run or monitor
- Enqueueing in the same transaction as other writes
- Full SQL visibility for debugging

Celery + Redis would be faster at higher scale but adds a component to manage. I chose Postgres first because it teaches the queue pattern explicitly: nothing is hidden behind a library.

### Why a custom worker, not Celery

Celery is the standard answer. It's also a black box. By writing the worker loop myself, I had to solve:

- Job claiming (race conditions between workers)
- Visibility timeout (what if a worker crashes mid-job?)
- Retry scheduling (exponential backoff)
- Dead-letter handling

These are the actual problems any queue solves. Using Celery would have hidden them.

### Why `delivery_attempts` is a separate table

A notification can be attempted several times; success on the 3rd try after two timeouts is normal. A single "attempts" counter on the notification row loses the story. A separate table captures when each attempt happened, the specific error, and whether it was retryable. That is what makes the system debuggable at 2am.

### Why idempotency keys are client-supplied

A network timeout on the client doesn't mean the request failed; it might have been processed. Without idempotency, the client retries and the user gets two emails. With it, the client resends the same `Idempotency-Key` and the server returns the original result.

"Exactly once" delivery isn't achievable, but "exactly once *effect*" is, and that is what this achieves.

### Why the worker uses three separate sessions per job

The worker opens a session to claim a job, **closes it**, sends the notification (which may take seconds), then opens a new session to record the result. Holding a connection across external I/O exhausts the pool: with a pool size of 20, 20 concurrent slow sends would block everything else.

### Why channels use the Strategy pattern

The worker doesn't know about email, SMS, or webhooks. It calls `sender.send(notification)`, and the sender is selected by channel. Adding a channel touches one file, not the worker and not the API.

## Trade-offs I Considered

### At 100x scale, I would

- **Switch the queue to Redis or RabbitMQ.** Postgres `SKIP LOCKED` is comfortable to roughly a thousand jobs/sec; beyond that, dedicated brokers are faster.
- **Add worker autoscaling.** Workers currently run at fixed capacity.
- **Partition the notifications table** by `created_at` for query performance.
- **Move to a managed queue** (SQS, Pub/Sub) to remove the operational burden.

### At higher reliability requirements, I would

- **Add a circuit breaker** per provider so a down provider isn't hammered.
- **Add provider failover** (primary and backup per channel).
- **Add delivery receipts** for SMS and email.
- **Keep at-least-once with idempotency** rather than chasing distributed transactions (2PC, Saga), which is what real systems use.

## Performance

> Numbers to be filled in after load testing (Locust / k6).

| Scenario | Workers | Jobs | Throughput (jobs/s) | p95 enqueue latency | Duplicate claims |
|:---|:---:|:---:|:---:|:---:|:---:|
| Baseline | 1 | _TBD_ | _TBD_ | _TBD_ | 0 |
| Scaled | 5 | _TBD_ | _TBD_ | _TBD_ | 0 |
| Scaled | 10 | _TBD_ | _TBD_ | _TBD_ | 0 |

## Testing

```bash
pytest -v
pytest --cov=app --cov-report=term-missing
```

22 tests, 75% coverage. They cover:

- API endpoints (create, get, 404, validation)
- Idempotency (same key, different key, no key)
- Queue concurrency (5 parallel workers, zero duplicate claims)
- Retry backoff math
- Error classification (retryable vs terminal)
- HMAC webhook signing
- Worker processing logic

## Running Locally

```bash
# 1. Configure environment
cp .env.example .env

# 2. Start Postgres
docker compose up -d

# 3. Apply migrations
docker compose exec api alembic upgrade head

# 4. Run the API
uvicorn app.main:app --reload --port 8001

# 5. In another terminal, run the worker
python -m app.workers.worker
```

Interactive docs are at `http://localhost:8001/docs`.

## API Endpoints

| Method | Path | Description | Auth |
|:---|:---|:---|:---|
| POST | `/api/v1/notifications/` | Create a notification | No |
| GET | `/api/v1/notifications/{id}` | Get a notification | No |
| GET | `/metrics` | Prometheus metrics | No |
| GET | `/health` | Health check | No |

### Example

```bash
curl -X POST http://localhost:8001/api/v1/notifications/ \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: my-unique-key" \
  -d '{
    "channel": "email",
    "recipient": "test@example.com",
    "subject": "Hello",
    "body": "This is a test"
  }'
```

## Project Structure

```text
notification-service/
├── app/
│   ├── api/v1/          # HTTP endpoints
│   ├── core/            # Config, exceptions, handlers, logging, metrics
│   ├── db/              # Database connections
│   ├── models/          # SQLAlchemy models
│   ├── schemas/         # Pydantic schemas
│   ├── services/
│   │   ├── queue.py     # Atomic claim logic
│   │   ├── retry.py     # Backoff calculator
│   │   └── senders/     # Channel senders (Strategy pattern)
│   └── workers/         # Worker loop + reaper
├── alembic/             # Database migrations
├── tests/               # Test suite
├── compose.yaml
└── requirements.txt
```

## Roadmap

- [ ] Deploy to a public URL
- [ ] CI with GitHub Actions (ruff, mypy, pytest)
- [ ] Load testing with documented throughput numbers
- [ ] Grafana dashboard on top of the Prometheus metrics
- [ ] Rate limiting per recipient and per provider
- [ ] Notification preferences (quiet hours, channel opt-in)
- [ ] Template engine (versioned content as data)
- [ ] Semantic event API (`POST /events` expands to notifications)
- [ ] Provider failover (primary and backup per channel)
- [ ] Circuit breaker per provider

## Author

**Malom Mwiti Mutuma** · [GitHub](https://github.com/malom489) · [LinkedIn](https://linkedin.com/in/malom-mwiti)

## License

MIT
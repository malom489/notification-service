# Notification Service

A production-grade notification service that reliably delivers messages across email, SMS, and webhooks—with retries, idempotency, and full audit trails.

## Why I Built This

I wanted to understand what actually happens when a system "sends a notification." The naive answer is "call an SMTP client and hope for the best." The real answer involves queues, retries, idempotency, failure classification, and the kind of operational thinking that most tutorials skip.

This project is my attempt to build the real version—not the tutorial version.
─────────────────────────────────────────────────────────┐
│ CLIENT │
│ POST /api/v1/notifications │
│ Idempotency-Key: <uuid> │
└──────────────────────────┬──────────────────────────────┘
│
▼
┌─────────────────────────────────────────────────────────┐
│ FASTAPI (API) │
│ 1. Validate request │
│ 2. Check idempotency key │
│ 3. Store Notification (status=pending) │
│ 4. Return 202 + notification_id │
└──────────────────────────┬──────────────────────────────┘
│
▼
┌─────────────────────────────────────────────────────────┐
│ POSTGRES (Queue) │
│ SELECT ... FOR UPDATE SKIP LOCKED │
└──────────────────────────┬──────────────────────────────┘
│
▼
┌─────────────────────────────────────────────────────────┐
│ WORKER (Python) │
│ 1. Claim notification (atomic) │
│ 2. Update status=processing │
│ 3. Select channel sender (Strategy pattern) │
│ 4. Attempt delivery │
│ 5. Log attempt, update status │
│ 6. On failure: retry with backoff or send to DLQ │
└─────────────────────────────────────────────────────────┘

## Design Decisions

### Why Postgres as the queue, not Celery + Redis

For moderate scale, PostgreSQL's `SELECT ... FOR UPDATE SKIP LOCKED` is genuinely production-viable. It provides:
- Atomic job claiming (no two workers get the same job)
- Built-in durability (transactions, WAL)
- No extra infrastructure to run or monitor
- Full SQL visibility for debugging

Celery + Redis would be faster at higher scale, but it adds a component to manage. I chose Postgres first because it teaches the queue pattern explicitly—nothing is hidden behind a library. For the trade-off analysis and when I'd switch, see the "Trade-offs I Considered" section.

### Why a custom worker, not Celery

Celery is the standard answer. It's also a black box. By writing the worker loop myself, I had to solve:
- Job claiming (race conditions between workers)
- Visibility timeout (what if a worker crashes mid-job?)
- Retry scheduling (exponential backoff)
- Dead-letter queue management

These are the actual problems that any queue solves. Using Celery would have hidden them. Building them made me understand what a queue *is*.

### Why delivery_attempts is a separate table

A notification can be attempted multiple times—success on the 3rd try after two timeouts is normal. Storing a single "attempts" counter on the notification row loses the story. A separate `delivery_attempts` table captures:
- When each attempt happened
- What the specific error was
- Whether it was retryable

This is what makes the system debuggable at 2am. "Why did notification 42 fail?" has a full answer.

### Why idempotency keys are client-supplied

A network timeout on the client side doesn't mean the request failed—it might have been processed. Without idempotency, the client retries and the user gets two emails. With idempotency, the client sends the same `Idempotency-Key` on retry, and the server returns the original result without re-processing.

This is how Stripe, Square, and every serious payment API work. It's also how you learn that "exactly once" delivery is a lie—but "exactly once *effect*" is achievable.

### Why status is an enum state machine

A notification moves through a defined set of states:

pending → processing → sent
↓
failed → (retry) → processing
↓
DLQ (after max attempts)
Using a Python enum (not a string) prevents invalid states and makes the transitions explicit.

### Why channels use the Strategy pattern

The worker doesn't know about email, SMS, or webhooks. It calls `sender.send(notification)`. The specific sender is selected by channel type. This means adding a new channel (Slack, push notifications) touches exactly one file—not the worker, not the API.

## Trade-offs I Considered

### At 100x scale, I would

- **Switch to Redis or RabbitMQ** for the queue. Postgres `SKIP LOCKED` is fine to ~1000 jobs/sec; beyond that, Redis lists or RabbitMQ's persistent queues are faster.
- **Add worker autoscaling.** Currently workers run at fixed capacity.
- **Partition the notifications table** by created_at for query performance.
- **Move to a managed queue** (SQS, Google Pub/Sub) to eliminate the ops burden.

### At higher reliability requirements, I would

- **Add a circuit breaker** per channel provider. If SendGrid is down, stop hammering it.
- **Add provider failover.** Primary + backup email providers.
- **Add delivery receipts** for SMS and email (read receipts via provider webhooks).
- **Add exactly-once delivery** using a distributed transaction (2PC or Saga pattern). Currently we have "at-least-once with idempotency"—which is what real systems actually use.

## Testing

```bash
pytest -v
pytest --cov=app --cov-report=term-missing
docker compose up -d
docker compose exec api alembic upgrade head
uvicorn app.main:app --reload
□ Rate limiting per recipient and per provider
□ Notification preferences (quiet hours, channel opt-in)
□ Template engine (content as data, versioned)
□ Semantic event API (POST /events → expands to notifications)
□ Prometheus metrics + Grafana dashboard
□ Provider failover (primary + backup for each channel)
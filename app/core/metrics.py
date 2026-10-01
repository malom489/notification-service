"""In-memory metrics registry (Prometheus-compatible text format)."""

import threading
from collections import defaultdict


class Metrics:
    """Thread-safe in-memory counter and gauge registry."""

    def __init__(self):
        self._lock = threading.Lock()
        self._counters: dict[str, int] = defaultdict(int)
        self._gauges: dict[str, float] = {}

    def increment(self, name: str, labels: dict | None = None, value: int = 1) -> None:
        key = self._key(name, labels)
        with self._lock:
            self._counters[key] += value

    def set_gauge(self, name: str, value: float, labels: dict | None = None) -> None:
        key = self._key(name, labels)
        with self._lock:
            self._gauges[key] = value

    def render(self) -> str:
        """Render Prometheus text format."""
        lines = []
        with self._lock:
            for key, value in self._counters.items():
                lines.append(f"{key} {value}")
            for key, value in self._gauges.items():
                lines.append(f"{key} {value}")
        return "\n".join(lines) + "\n"

    @staticmethod
    def _key(name: str, labels: dict | None) -> str:
        if not labels:
            return name
        label_str = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"


# Global singleton
metrics = Metrics()

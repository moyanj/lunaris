from __future__ import annotations

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest


class MasterMetrics:
    def __init__(self) -> None:
        self.registry = CollectorRegistry()
        self.tasks_submitted_total = Counter(
            "lunaris_tasks_submitted_total",
            "Total number of submitted tasks",
            registry=self.registry,
        )
        self.task_results_total = Counter(
            "lunaris_task_results_total",
            "Total number of terminal task results by status",
            labelnames=("status",),
            registry=self.registry,
        )
        self.task_retries_total = Counter(
            "lunaris_task_retries_total",
            "Total number of scheduled task retries",
            registry=self.registry,
        )
        self.worker_registrations_total = Counter(
            "lunaris_worker_registrations_total",
            "Total number of worker registrations",
            registry=self.registry,
        )
        self.worker_disconnects_total = Counter(
            "lunaris_worker_disconnects_total",
            "Total number of worker removals by status",
            labelnames=("status",),
            registry=self.registry,
        )
        self.task_execution_ms = Histogram(
            "lunaris_task_execution_ms",
            "Observed task execution time in milliseconds",
            buckets=(1, 5, 10, 25, 50, 100, 250, 500, 1000, 5000, 10000, 30000, 60000),
            registry=self.registry,
        )
        self.connected_workers = Gauge(
            "lunaris_connected_workers",
            "Current number of connected workers",
            registry=self.registry,
        )
        self.task_queue_size = Gauge(
            "lunaris_task_queue_size",
            "Current queue size",
            registry=self.registry,
        )
        self.running_tasks = Gauge(
            "lunaris_running_tasks",
            "Current number of running tasks",
            registry=self.registry,
        )
        self.tasks_by_status = Gauge(
            "lunaris_tasks_by_status",
            "Current number of tasks by status",
            labelnames=("status",),
            registry=self.registry,
        )

    def render_latest(self) -> bytes:
        return generate_latest(self.registry)


# Collector DNP3 (Windows-first Starter)

This service is intentionally separated from the central backend.

- Python pinned to 3.10
- Runs as standalone process/service on Windows in initial phase
- Pushes telemetry to central backend endpoint
- Keeps Linux migration path open by isolating DNP3 adapter

# Master Module - FastAPI Task Scheduler

**Parent:** See root AGENTS.md for project overview

## OVERVIEW

FastAPI master node: task scheduling, worker management, WebSocket endpoints for client/worker communication.

## WHERE TO LOOK

| Task | File | Key Symbols |
|------|------|-------------|
| Add REST endpoint | `api.py` | `@app.get/@app.websocket`, `require_client_token` |
| Modify task queue | `manager.py:154` | `TaskManager.add_task`, `PriorityQueue` |
| Worker load balancing | `manager.py:97` | `WorkerManager.get_available_worker`, `available_slots` |
| Task retry logic | `manager.py:200` | `TaskManager.put_result`, `failed_count` |
| WebSocket task dispatch | `web_app.py` | `distribute_tasks`, `worker websocket` |
| Heartbeat monitoring | `web_app.py` | `check_heartbeat`, 20s timeout |
| Auth token validation | `api.py:17` | `require_client_token`, `secrets.compare_digest` |
| Data models | `model.py` | `Task`, `TaskStatus` enum |

## CONVENTIONS

### FastAPI Patterns
- **Dependency injection**: `AppState = Depends(get_app_state)` for shared state
- **Token auth**: All endpoints use `require_client_token` via `Depends`
- **Response wrapper**: `Rest(msg, code, data)` for consistent JSON responses

### Async Background Tasks
- `check_heartbeat()` - removes workers after 20s silence
- `distribute_tasks()` - assigns tasks to available workers via `asyncio.Condition`

### State Management
- `AppState` encapsulates: `worker_manager`, `task_manager`, `client_token`, `worker_token`, execution limits
- Module-level singleton: `id_gen = IDGenerator(0)` in `__init__.py`

## ANTI-PATTERNS (THIS MODULE)

1. **Direct Task manipulation**: Don't modify `Task` fields after creation - use `assign_to_worker()` etc.
2. **Skip worker load check**: Always check `worker.available_slots` before dispatch
3. **Hard-code tokens**: Use `state.client_token` / `state.worker_token` from AppState
4. **Manual heartbeat updates**: Only `WorkerManager.handle_heartbeat()` should update `last_heartbeat`
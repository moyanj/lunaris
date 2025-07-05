from fastapi import APIRouter, Request, Depends
from lunaris.master.web_app import get_app_state, AppState

app = APIRouter()


@app.get("/num_worker")
async def num_worker(request: Request, state: AppState = Depends(get_app_state)):
    return {"num_worker": len(state.worker_manager.workers)}

from lunaris.worker.main import Worker
import asyncio

w = Worker("ws://127.0.0.1:8000/worker")
asyncio.run(w.run())

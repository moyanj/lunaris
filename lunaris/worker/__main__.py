import asyncio
import os

from lunaris.worker.main import Worker


async def main():
    worker = Worker("ws://127.0.0.1:8000/worker", os.environ.get("WORKER_TOKEN", ""))
    try:
        await worker.run()
    except KeyboardInterrupt:
        await worker.shutdown()


asyncio.run(main())

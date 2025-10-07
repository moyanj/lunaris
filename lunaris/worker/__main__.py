from lunaris.worker.main import Worker
import asyncio
import os


async def main():
    worker = Worker("ws://127.0.0.1:8000/worker", os.environ.get("WORKER_TOKEN", ""))
    try:
        await worker.run()
    except KeyboardInterrupt:
        await worker.shutdown()


asyncio.run(main())

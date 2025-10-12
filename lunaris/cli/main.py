import argparse
import asyncio
import os
from lunaris.worker.main import Worker
from lunaris.master.web_app import app as master_app
import uvicorn
import sys

try:
    import uvloop
except ImportError:
    pass


async def main():
    parser = argparse.ArgumentParser(description="Lunaris Distributed WASM Executor")
    subparsers = parser.add_subparsers(dest="role", help="Run as master or worker")

    # Master 参数
    master_parser = subparsers.add_parser("master", help="Run as master node")
    master_parser.add_argument("--host", default="127.0.0.1", help="Host to bind")
    master_parser.add_argument("--port", type=int, default=8000, help="Port to bind")

    # Worker 参数
    worker_parser = subparsers.add_parser("worker", help="Run as worker node")
    worker_parser.add_argument("--master", required=True, help="Master address")
    worker_parser.add_argument("--name", help="Worker name")
    worker_parser.add_argument("--concurrency", type=int, help="Max concurrent tasks")
    worker_parser.add_argument(
        "--token",
        help="Worker token",
        type=str,
        default=os.environ.get("WORKER_TOKEN", ""),
    )

    args = parser.parse_args()

    try:
        if args.role == "master":
            await run_master(args)
        elif args.role == "worker":
            await run_worker(args)
        else:
            parser.print_help()
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        import traceback

        traceback.print_exc()
        sys.exit(1)


async def run_master(args):  # Changed to async function
    """运行Master节点"""
    config = uvicorn.Config(
        master_app,
        host=args.host,
        port=args.port,
        workers=1,
        log_config=None,
        log_level="error",
    )
    server = uvicorn.Server(config)
    try:
        await server.serve()  # Use serve() instead of run()
    except KeyboardInterrupt:
        pass
    except asyncio.CancelledError:
        pass


async def run_worker(args):
    """运行Worker节点"""

    worker = Worker(
        master_uri=args.master,
        token=args.token,
        name=args.name,
        max_concurrency=args.concurrency,
    )

    try:
        await worker.run()
    except:
        pass
    finally:
        await worker.shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)

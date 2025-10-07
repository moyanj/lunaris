import argparse
import asyncio
import os
from lunaris.master.web_app import app as master_app
from lunaris.worker.main import Worker
import uvicorn


def main():
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

    if args.role == "master":
        uvicorn.run(master_app, host=args.host, port=args.port)
    elif args.role == "worker":
        worker = Worker(
            master_uri=args.master,
            token=args.token,
            name=args.name,
            max_concurrency=args.concurrency,
        )
        asyncio.run(worker.run())
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

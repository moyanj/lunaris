import argparse
import asyncio
import os
from lunaris.worker.main import Worker
from lunaris.master.web_app import app as master_app
from lunaris.runtime import ExecutionLimits
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
    master_parser.add_argument("--default-max-fuel", type=int, default=0)
    master_parser.add_argument("--default-max-memory-bytes", type=int, default=0)
    master_parser.add_argument("--default-max-module-bytes", type=int, default=0)
    master_parser.add_argument("--max-fuel", type=int, default=0)
    master_parser.add_argument("--max-memory-bytes", type=int, default=0)
    master_parser.add_argument("--max-module-bytes", type=int, default=0)

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
    worker_parser.add_argument("--default-max-fuel", type=int, default=0)
    worker_parser.add_argument("--default-max-memory-bytes", type=int, default=0)
    worker_parser.add_argument("--default-max-module-bytes", type=int, default=0)
    worker_parser.add_argument("--max-fuel", type=int, default=0)
    worker_parser.add_argument("--max-memory-bytes", type=int, default=0)
    worker_parser.add_argument("--max-module-bytes", type=int, default=0)

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
    master_app.state.default_execution_limits = _default_limits_from_args(args)
    master_app.state.max_execution_limits = _max_limits_from_args(args)
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
        default_execution_limits=_default_limits_from_args(args),
        max_execution_limits=_max_limits_from_args(args),
    )

    try:
        await worker.run()
    except:
        pass
    finally:
        await worker.shutdown()


def _default_limits_from_args(args) -> ExecutionLimits:
    return ExecutionLimits(
        max_fuel=args.default_max_fuel,
        max_memory_bytes=args.default_max_memory_bytes,
        max_module_bytes=args.default_max_module_bytes,
    )


def _max_limits_from_args(args) -> ExecutionLimits:
    return ExecutionLimits(
        max_fuel=args.max_fuel,
        max_memory_bytes=args.max_memory_bytes,
        max_module_bytes=args.max_module_bytes,
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)

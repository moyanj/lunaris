from lunaris.cli.main import main
import asyncio
import sys

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)

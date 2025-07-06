import sys
from loguru import logger

logger.remove()
console_format = (
    "WORKER | "
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<level>{message}</level>"
)
logger.add(
    sys.stdout,
    level="INFO",  # 控制台只显示INFO及以上级别
    format=console_format,
    colorize=True,
    enqueue=True,
)

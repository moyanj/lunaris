import sys
from loguru import logger
from lunaris.utils import IDGenerator


def init_logger():
    logger.remove()
    console_format = (
        "MASTER | "
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<level>{message}</level>"
    )
    logger.add(
        sys.stdout,
        level="DEBUG",  # 控制台只显示INFO及以上级别
        format=console_format,
        colorize=True,
        enqueue=True,
    )


id_gen = IDGenerator(0)

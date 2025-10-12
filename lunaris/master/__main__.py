import uvicorn
from lunaris.master.web_app import app
from lunaris.master import init_logger
from loguru import logger

if __name__ == "__main__":
    host = "0.0.0.0"
    port = 8000
    logger.info(f"Master running on http://{host}:{port}")
    uvicorn.run(
        "lunaris.master.web_app:app", host=host, port=port, workers=1, log_level="error"
    )

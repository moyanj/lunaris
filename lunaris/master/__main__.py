import uvicorn
from lunaris.master.web_app import app
from loguru import logger

if __name__ == "__main__":
    host = "0.0.0.0"
    port = 8000
    logger.info(f"Master running on http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="critical")

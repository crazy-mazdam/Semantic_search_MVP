import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parents[2] / "data" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "rag_app.log"

def get_logger(name="rag_app"):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # Rotating handler: new file daily, keep 14 days
    handler = TimedRotatingFileHandler(LOG_FILE, when="midnight", interval=1, backupCount=14, encoding="utf-8")
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # Console output too
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)

    return logger

# Example usage:
if __name__ == "__main__":
    log = get_logger()
    log.info("Logging initialized successfully")

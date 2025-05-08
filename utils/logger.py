import logging
from logging.handlers import RotatingFileHandler
import queue

log_queue = queue.Queue()

class QueueHandler(logging.Handler):
    def emit(self, record):
        log_entry = self.format(record)
        log_queue.put(log_entry)

def get_logger(name: str):
    """Set up and return a logger instance."""
    logger = logging.getLogger(name)

    if not logger.hasHandlers():
        logger.setLevel(logging.INFO)

        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

        file_handler = RotatingFileHandler("app.log", maxBytes=5 * 1024 * 1024, backupCount=5)
        file_handler.setFormatter(formatter)

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)

        queue_handler = QueueHandler()
        queue_handler.setFormatter(formatter)

        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        logger.addHandler(queue_handler)

    return logger

def flush_log_file():
    """Force flush log file handlers so logs are written before reading."""
    for handler in logging.getLogger().handlers:
        if hasattr(handler, 'flush'):
            handler.flush()

import logging
import os
from logging.handlers import RotatingFileHandler

# Create logs directory if not exists
log_dir = "logs"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)


# Helper function to configure a logger
def setup_logger(name, log_file, level):
    """Configure and return a logger."""
    log_path = os.path.join(log_dir, log_file)
    handler = RotatingFileHandler(log_path, maxBytes=500 * 1024 * 1024, backupCount=3)
    handler.setLevel(level)

    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')
    handler.setFormatter(formatter)

    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(handler)
    logger.propagate = False  # Prevent duplicate logs

    return logger

master_logger = setup_logger("master_logger", "all_logs.log", logging.DEBUG)

logging.basicConfig(level=logging.INFO)
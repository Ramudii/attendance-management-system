"""
Logging Configuration Module
Author: Member 1 - Project Lead
"""

import logging
import sys
import os
from datetime import datetime


def setup_logger(name, log_file=None, level=logging.INFO):
    """
    Setup logger with console and file handlers
    
    Args:
        name: Logger name
        log_file: Path to log file (optional)
        level: Logging level
        
    Returns:
        logging.Logger: Configured logger
    """
    # Create logs directory if it doesn't exist
    os.makedirs('logs', exist_ok=True)
    
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Avoid duplicate handlers
    if logger.hasHandlers():
        logger.handlers.clear()

    # Don't pass records to the root logger as well, otherwise anything that
    # calls logging.basicConfig() makes every message appear twice.
    logger.propagate = False

    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler (outputs to terminal)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler (outputs to log file)
    if log_file is None:
        timestamp = datetime.now().strftime('%Y%m%d')
        log_file = f"logs/sams_{timestamp}.log"
    
    try:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        logger.warning(f"Could not create file handler: {e}")
    
    return logger


def get_logger(name):
    """
    Get a logger instance
    
    Args:
        name: Logger name
        
    Returns:
        logging.Logger: Logger instance
    """
    return setup_logger(name)


# Test the logger (runs when file is executed directly)
if __name__ == "__main__":
    logger = setup_logger('test', level=logging.DEBUG)
    logger.info("Testing logger setup")
    logger.debug("Debug message")
    logger.warning("Warning message")
    logger.error("Error message")
    print("\n✅ Logger test complete! Check logs directory for log file.")
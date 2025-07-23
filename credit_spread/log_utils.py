from functools import wraps
from logzero import logger

def log_function_entry_exit(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        logger.info(f"Entering: {func.__name__}()")
        result = func(*args, **kwargs)
        logger.info(f"Exiting: {func.__name__}()")
        return result
    return wrapper

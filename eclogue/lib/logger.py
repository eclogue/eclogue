import logging
import logging.config


def get_logger(name='eclogue'):
    log_obj = logging.getLogger(name)

    return log_obj


logger = get_logger()

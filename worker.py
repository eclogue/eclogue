from eclogue.celery import celery
from eclogue.lib.logger import logger

if __name__ == '__main__':
    logger.info('start worker')
    celery.worker_main()


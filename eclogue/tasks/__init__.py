from tasktiger import TaskTiger
from eclogue.redis import redis_client
from eclogue.config import config
from eclogue.lib.logger import get_logger
task_cfg = config.task


logger = get_logger('console')
tiger = TaskTiger(connection=redis_client, config={
    'REDIS_PREFIX': 'ece',
    'ALWAYS_EAGER': task_cfg.get('always_eager'),
}, setup_structlog=True)

import sys
import importlib

import logging.config
from eclogue.config import config
from eclogue.tasks.dispatch import tiger

sys.modules['ansible.utils.display'] = importlib.import_module('eclogue.ansible.display')

# logging.config.dictConfig(config.logging)

if __name__ == "__main__":
    tiger.run_worker()



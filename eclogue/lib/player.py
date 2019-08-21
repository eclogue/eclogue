import logging
import os
from collections import namedtuple
from tempfile import NamedTemporaryFile
from ansible.errors import AnsibleError
from ansible.executor.task_queue_manager import TaskQueueManager
from ansible.inventory.manager import InventoryManager
from ansible.parsing.dataloader import DataLoader
from ansible.playbook.play import Play
from ansible.plugins.callback import CallbackBase
from ansible.vars.manager import VariableManager

from eclogue.config import config
from eclogue.ansible.runer import AdHocRunner


def setup(credential, hosts, options):
    """
    ansible adhoc setup

    :param credential:
    :param options:
    :return: AdHocRunner
    """
    print(credential)
    with NamedTemporaryFile('w+t', delete=True) as fd:
        fd.write(credential)
        fd.seek(0)
        options['private_key_file'] = fd.name
        runner = AdHocRunner(hosts, options=options)
        tasks = [
            {
                'action': {
                    'module': 'setup'
                }
            }
        ]
        runner.run('all', tasks=tasks)
        return runner

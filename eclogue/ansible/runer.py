import json
import os
import ansible.constants as C
from collections import namedtuple, Iterable
from ansible.executor.playbook_executor import PlaybookExecutor
from ansible.playbook.block import Block
from ansible.errors import AnsibleError
# from ansible.plugins.callback.json import CallbackModule
# from ansible.plugins.callback.json import CallbackModule
from ansible.vars.manager import VariableManager
from ansible.parsing.dataloader import DataLoader
from ansible.utils.display import Display
from ansible.playbook.play import Play
from ansible.executor.task_queue_manager import TaskQueueManager
from eclogue.ansible.inventory import HostsManager
from ansible import context
from ansible.utils.context_objects import CLIArgs
from eclogue.ansible.plugins.callback import CallbackModule

C.HOST_KEY_CHECKING = False
C.ANSIBLE_NOCOLOR = True
display = Display()


def get_default_options(name):
    pb_options = {
        'listtasks': None,
        'start_at_task': None,
        'skip_tags': [],
        'tags': [],
        'step': None,
        'force_handlers': False,
        'flush_cache': False,
        'listtags': False,
    }

    adhoc_options = {
        "poll_interval": 15,
        "module_name": '',
        "one_line": False,
        "tree": False,
        "module_args": '',
        "seconds": 0
    }
    # vault_pass 是 eclogue 特有的
    common_options = {
        'listhosts': None,
        'diff': False,
        'verbosity': 0,
        'extra_vars': [],
        'ask_pass': False,
        'ask_su_pass': False,
        'connection': 'smart',
        'become_ask_pass': False,
        'sudo': False,
        'subset': None,
        'ask_sudo_pass': False,
        'become': False,
        'check': False,
        'vault_ids': [],
        'su': False,
        'private_key_file': None,
        'module_path': None,
        'become_user': '',
        'become_method': '',
        'inventory': [],
        'syntax': None,
        'forks': 5,
        'remote_user': None,
        'ssh_extra_args': '',
        'su_user': None,
        'sudo_user': None,
        'scp_extra_args': '',
        'vault_password_files': [],
        'sftp_extra_args': '',
        'timeout': 10,
        'ask_vault_pass': False,
        'ssh_common_args': '',
        'basedir': '',
        'vault_pass': None,
        'limit': None,
    }
    if name == 'playbook':
        common_options.update(pb_options)
    else:
        common_options.update(adhoc_options)

    return common_options


class AdHocRunner(object):
    """
    This is a General object for parallel execute modules.
    """
    def __init__(self, resource, options, name='adhoc', callback=None, job_id=None):
        if type(resource) == dict:
            self.resource = json.dumps(resource)
        else:
            self.resource = resource

        self.job_id = job_id
        self.display = Display()
        self.inventory = None
        self.name = name
        self.variable_manager = None
        self.passwords = None
        self.callback = callback or CallbackModule(job_id=job_id)
        self.results_raw = {}
        self.loader = DataLoader()
        self.options = None
        self.get_options(options, name)
        context.CLIARGS = CLIArgs(self.options)
        self.passwords = options.get('vault_pass') or {}
        self.inventory = HostsManager(loader=self.loader, sources=self.resource)
        self.variable_manager = VariableManager(loader=self.loader, inventory=self.inventory)
        verbosity = options.get('verbosity')
        display.verbosity = verbosity

    def get_options(self, options, name=None):
        self.options = get_default_options(name)
        self.options.update(options)

    def run(self, pattern, tasks, gather_facts='no'):
        """
        ansible adhoc 模式运行任务
        host_list: host 列表文件或者带逗号字符
        :param pattern:
        :param tasks:
        :param gather_facts:
        :return:
        """

        tasks = self.load_tasks(tasks)
        # tasks = [dict(action=dict(module='setup'))]
        # print(tasks)

        # create play with tasks
        play_source = dict(
            name="Ansible adhoc",
            hosts=pattern,
            gather_facts=gather_facts,
            tasks=tasks
        )
        play = Play().load(play_source, variable_manager=self.variable_manager, loader=self.loader)
        # actually run it
        tqm = None
        try:
            tqm = TaskQueueManager(
                inventory=self.inventory,
                variable_manager=self.variable_manager,
                loader=self.loader,
                passwords=self.passwords,
                stdout_callback=self.callback,
            )
            # tqm._stdout_callback = self.callback
            tqm.run(play)
            # print(self.callback.d)
        finally:
            if tqm is not None:
                tqm.cleanup()

    def load_tasks(self, tasks):
        for task in tasks:
            module_name = task['action'].get('module')
            args = task['action'].get('args')
            if module_name in C.MODULE_REQUIRE_ARGS and not args:
                err = "No argument passed to '%s' module." % module_name
                raise AnsibleError(err)
        return tasks

    def get_result(self):
        return self.callback.dumper
        self.results_raw = {'success': {}, 'failed': {}, 'unreachable': {}}
        for host, result in self.callback.host_ok.items():
            self.results_raw['success'][host] = result._result

        for host, result in self.callback.host_failed.items():
            self.results_raw['failed'][host] = result._result

        for host, result in self.callback.host_unreachable.items():
            self.results_raw['unreachable'][host] = result._result['msg']

        return self.results_raw


class PlayBookRunner(AdHocRunner):
    """
    This is a General object for parallel execute modules.
    """

    def __init__(self, resource, options, name='playbook', callback=None, job_id=None):
        super().__init__(resource, options=options, name=name, callback=callback, job_id=job_id)
        self.tasks = set()
        self.tags = set()

    def run(self, playbooks, gather_facts='no'):
        """
        ansible playbook 模式运行任务
        """
        # C.DEFAULT_ROLES_PATH = self.options.roles_path

        loader, inventory, variable_manager = self._play_prereqs(
            self.options)
        playbooks = playbooks if type(playbooks) == list else [playbooks]
        executor = PlaybookExecutor(
            playbooks=playbooks,
            inventory=inventory,
            variable_manager=variable_manager,
            loader=loader,
            passwords=self.passwords
        )
        if executor._tqm and self.callback:
            executor._tqm._stdout_callback = self.callback
        try:
            results = executor.run()
            if not isinstance(results, Iterable):
                return self.callback
            for p in results:
                for idx, play in enumerate(p['plays']):
                    if play._included_path is not None:
                        loader.set_basedir(play._included_path)
                    else:
                        pb_dir = os.path.realpath(os.path.dirname(p['playbook']))
                        loader.set_basedir(pb_dir)
                    if self.options['listtags'] or self.options['listtasks']:
                        pass

                        all_vars = variable_manager.get_vars()
                        for block in play.compile():
                            block = block.filter_tagged_tasks(all_vars)
                            if not block.has_tasks():
                                continue
                            self._process_block(block)

        except AnsibleError as e:
            executor._tqm.cleanup()
            self.loader.cleanup_all_tmp_files()
            raise e

    def _process_block(self, b):
        for task in b.block:
            if isinstance(task, Block):
                return self._process_block(task)
            if task.action == 'meta':
                continue
            self.tags.update(task.tags)
            if self.options.get('listtasks'):
                if task.name:
                    self.tasks.add(task.name)

    def load_tasks(self, tasks):
        for task in tasks:
            module_name = task['action'].get('args')
            args = task['action']['module']
            if module_name in C.MODULE_REQUIRE_ARGS and not args:
                err = "No argument passed to '%s' module." % module_name
                raise AnsibleError(err)
        return tasks

    def get_result(self):
        self.results_raw = {'success': {}, 'failed': {}, 'unreachable': {}}
        for host, result in self.callback.host_ok.items():
            self.results_raw['success'][host] = result._result

        for host, result in self.callback.host_failed.items():
            self.results_raw['failed'][host] = result._result

        for host, result in self.callback.host_unreachable.items():
            self.results_raw['unreachable'][host] = result._result['msg']

        return self.results_raw

    def dump_result(self):
        return self.callback.dumper

    def _play_prereqs(self, options):

        loader = DataLoader()
        basedir = getattr(options, 'basedir', False)
        if basedir:
            loader.set_basedir(basedir)

        inventory = self.inventory
        variable_manager = VariableManager(loader=loader, inventory=inventory)

        if hasattr(options, 'basedir'):
            if options.basedir:
                variable_manager.safe_basedir = True
        else:
            variable_manager.safe_basedir = True

        # load vars from cli options
        # variable_manager._extra_vars = load_extra_vars(loader=loader)
        # variable_manager.options_vars = load_options_vars('2.8.4')

        return loader, inventory, variable_manager


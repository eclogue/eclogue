import json
import ansible.constants as C
from collections import namedtuple, Iterable
from ansible.executor.playbook_executor import PlaybookExecutor
from ansible.playbook.play_context import PlayContext
from ansible.playbook.block import Block
from ansible.errors import AnsibleError
from ansible.plugins.callback import CallbackBase
from ansible.vars.manager import VariableManager
from ansible.parsing.dataloader import DataLoader
from ansible.utils.vars import load_extra_vars, load_options_vars
from ansible.playbook.play import Play
from ansible.executor.task_queue_manager import TaskQueueManager
from eclogue.ansible.inventory import HostsManager
from eclogue.ansible.display import Display, logger


C.HOST_KEY_CHECKING = False
display = Display()


def get_default_options(type):
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
    if type == 'playbook':
        common_options.update(pb_options)
    else:
        common_options.update(adhoc_options)
    Options = namedtuple('Options', sorted(common_options))
    options = Options(**common_options)
    return options


class AdHocRunner(object):
    """
    This is a General object for parallel execute modules.
    """
    def __init__(self, resource, options, name='adhoc'):
        if type(resource) == dict:
            self.resource = json.dumps(resource)
        else:
            self.resource = resource
        self.inventory = None
        self.name = name
        self.variable_manager = None
        self.passwords = None
        self.callback = ResultsCollector()
        self.results_raw = {}
        self.loader = DataLoader()
        self.options = self.get_options(options, name)
        self.passwords = options.get('vault_pass') or {}
        self.inventory = HostsManager(loader=self.loader, sources=self.resource)
        self.variable_manager = VariableManager(loader=self.loader, inventory=self.inventory)

    def get_options(self, options, name=None):
        self.options = get_default_options(name)
        for k, v in options.items():
            if not hasattr(self.options, k):
                continue
            item = {k: v}
            self.options = self.options._replace(**item)

        return self.options

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
                options=self.options,
                passwords=self.passwords,
                stdout_callback=self.callback,
            )
            # tqm._stdout_callback = self.callback
            tqm.run(play)
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

    def __init__(self, resource, options, name='playbook'):
        super().__init__(resource, options=options, name=name)
        self.tasks = set()
        self.tags = set()

    def run(self, playbooks, gather_facts='no'):
        """
        ansible playbook 模式运行任务
        """
        # C.DEFAULT_ROLES_PATH = self.options.roles_path

        loader, inventory, variable_manager = self._play_prereqs(self.options)
        playbooks = playbooks if type(playbooks) == list else [playbooks]
        executor = PlaybookExecutor(
            playbooks=playbooks,
            inventory=inventory,
            variable_manager=variable_manager,
            loader=loader,
            options=self.options,
            passwords=self.passwords
        )
        if executor._tqm:
            executor._tqm._stdout_callback = self.callback
        try:
            results = executor.run()
            if not isinstance(results, Iterable):
                return self.callback
            for p in results:
                for idx, play in enumerate(p['plays']):
                    play_context = PlayContext(play=play, options=self.options)
                    all_vars = variable_manager.get_vars(play=play)
                    for block in play.compile():
                        block = block.filter_tagged_tasks(play_context, all_vars)
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
            if self.options.listtasks:
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
        variable_manager.extra_vars = load_extra_vars(loader=loader, options=options)
        variable_manager.options_vars = load_options_vars(options, '2.7.4')

        return loader, inventory, variable_manager


class ResultsCollector(CallbackBase):

    def __init__(self):
        super(ResultsCollector, self).__init__()
        self._display = Display()
        self.host_ok = {}
        self.host_unreachable = {}
        self.host_failed = {}
        # self.formatter = FormatCollector()

    def v2_runner_on_unreachable(self, result):
        super(ResultsCollector, self).v2_runner_on_unreachable(result)
        self.host_unreachable[result._host.get_name()] = result
        # self.formatter.v2_runner_on_unreachable(result)

    def v2_runner_on_ok(self, result, *args, **kwargs):
        super(ResultsCollector, self).v2_runner_on_ok(result)
        self.host_ok[result._host.get_name()] = result
        # self.formatter.v2_runner_on_ok(result)

    def v2_runner_on_failed(self, result, *args, **kwargs):
        super(ResultsCollector, self).v2_runner_on_failed(result)
        self.host_failed[result._host.get_name()] = result
        # self.formatter.v2_runner_on_failed(result)

    def get_result(self):
        return self._dump_results()


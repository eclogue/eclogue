import ansible.constants as C
from ansible.plugins.callback.default import CallbackModule
from ansible.playbook.task_include import TaskInclude
from ansible.utils.display import Display


class FormatCollector(CallbackModule):
    def __init__(self, display=None, options=None):
        super(FormatCollector, self).__init__(display=display, options=options)
        self._display = Display

    def v2_runner_on_failed(self, result, ignore_errors=False):
        delegated_vars = result._result.get('_ansible_delegated_vars', None)
        self._clean_results(result._result, result._task.action)

        if self._last_task_banner != result._task._uuid:
            self._print_task_banner(result._task)

        self._handle_exception(result._result, use_stderr=self.display_failed_stderr)
        self._handle_warnings(result._result)

        if result._task.loop and 'results' in result._result:
            self._process_items(result)

        else:
            if delegated_vars:
                self._display.display(
                    "fatal: [%s -> %s]: FAILED! => %s" % (result._host.get_name(),
                                                          delegated_vars['ansible_host'],
                                                          self._dump_results(result._result)),
                    color=C.COLOR_ERROR,
                    stderr=self.display_failed_stderr)
            else:
                self._display.display(
                    "fatal: [%s]: FAILED! => %s" % (result._host.get_name(), self._dump_results(result._result)),
                    color=C.COLOR_ERROR, stderr=self.display_failed_stderr)

        if ignore_errors:
            self._display.display("...ignoring", color=C.COLOR_SKIP)

    def v2_runner_on_ok(self, result):
        delegated_vars = result._result.get('_ansible_delegated_vars', None)
        if isinstance(result._task, TaskInclude):
            return

        elif result._result.get('changed', False):
            if self._last_task_banner != result._task._uuid:
                self._print_task_banner(result._task)

            if delegated_vars:
                msg = "changed: [%s -> %s]" % (result._host.get_name(), delegated_vars['ansible_host'])
            else:
                msg = "changed: [%s]" % result._host.get_name()
            color = C.COLOR_CHANGED
        else:
            if not self.display_ok_hosts:
                return

            if self._last_task_banner != result._task._uuid:
                self._print_task_banner(result._task)

            if delegated_vars:
                msg = "ok: [%s -> %s]" % (result._host.get_name(), delegated_vars['ansible_host'])
            else:
                msg = "ok: [%s]" % result._host.get_name()
            color = C.COLOR_OK

        self._handle_warnings(result._result)

        if result._task.loop and 'results' in result._result:
            self._process_items(result)
        else:
            self._clean_results(result._result, result._task.action)

            if (
                self._display.verbosity > 0 or '_ansible_verbose_always' in result._result) and '_ansible_verbose_override' not in result._result:
                msg += " => %s" % (self._dump_results(result._result),)
            self._display.display(msg, color=color)

    def v2_runner_on_skipped(self, result):

        if self.display_skipped_hosts:

            self._clean_results(result._result, result._task.action)

            if self._last_task_banner != result._task._uuid:
                self._print_task_banner(result._task)

            if result._task.loop and 'results' in result._result:
                self._process_items(result)
            else:
                msg = "skipping: [%s]" % result._host.get_name()
                if (
                    self._display.verbosity > 0 or '_ansible_verbose_always' in result._result) and '_ansible_verbose_override' not in result._result:
                    msg += " => %s" % self._dump_results(result._result)
                self._display.display(msg, color=C.COLOR_SKIP)

    def v2_runner_on_unreachable(self, result):
        if self._last_task_banner != result._task._uuid:
            self._print_task_banner(result._task)

        delegated_vars = result._result.get('_ansible_delegated_vars', None)
        if delegated_vars:
            self._display.display(
                "fatal: [%s -> %s]: UNREACHABLE! => %s" % (result._host.get_name(), delegated_vars['ansible_host'],
                                                           self._dump_results(result._result)),
                color=C.COLOR_UNREACHABLE)
        else:
            self._display.display(
                "fatal: [%s]: UNREACHABLE! => %s" % (result._host.get_name(), self._dump_results(result._result)),
                color=C.COLOR_UNREACHABLE)

    def v2_playbook_on_no_hosts_matched(self):
        self._display.display("skipping: no hosts matched", color=C.COLOR_SKIP)

    def v2_playbook_on_no_hosts_remaining(self):
        self._display.banner("NO MORE HOSTS LEFT")

    def v2_playbook_on_task_start(self, task, is_conditional):
        self._task_start(task, prefix='TASK')

import json
import datetime
from bson import ObjectId
import ansible.constants as C
from ansible.utils.display import Display
from ansible.plugins.callback import CallbackBase
from eclogue.model import db
from eclogue.notification.notify import Notify


class CallbackModule(CallbackBase):

    def __init__(self, display=None, job_id=None):
        display = display or Display()
        super(CallbackModule, self).__init__(display=display)
        self._display = display
        self.job_id = job_id
        self.job = self.get_job()
        self.host_ok = {}
        self.host_unreachable = {}
        self.host_failed = {}
        self.dumper = {}

    def get_job(self):
        job = db.collection('jobs').find_one({'_id': ObjectId(self.job_id)})

        return job

    def command_generic_msg(self, host, result, caption):
        """
        output the result of a command run
        :param host:
        :param result:
        :param caption:
        :return: str
        """

        buf = "%s | %s | rc=%s >>\n" % (host, caption, result.get('rc', -1))
        buf += result.get('stdout', '')
        buf += result.get('stderr', '')
        buf += result.get('msg', '')

        return buf + "\n"

    def v2_runner_on_unreachable(self, result):
        # super(CallbackModule, self).v2_runner_on_unreachable(result)
        self._display.display("%s | UNREACHABLE! => %s"
                              % (result._host.get_name(), self._dump_results(result._result, indent=4)), color=None)

        hostname = result._host.get_name()
        vars = result._host.get_vars()
        ansible_ssh_host = vars.get('ansible_ssh_host')
        if ansible_ssh_host:
            update = {
                '$set': {
                    'state': 'unreachable',
                    'updated_at': datetime.datetime.now()
                }
            }
            db.collection('machines').update_one({'ansible_ssh_host': ansible_ssh_host}, update=update)

        self.host_unreachable[hostname] = result
        # self.formatter.v2_runner_on_unreachable(result)
        dumper = self.get_result(result)
        dumper.update({'state': 'unreachable'})
        self.dumper[hostname] = dumper
        notification = 'ansible run on unreachable, host:{}, job:{}'.format(hostname, self.job.get('name'))
        self.notify(notification)

    def v2_runner_on_ok(self, result, *args, **kwargs):
        # super(CallbackBase, self).v2_runner_on_ok(result)
        self._clean_results(result._result, result._task.action)

        self._handle_warnings(result._result)

        if result._result.get('changed', False):
            state = 'CHANGED'
        else:
            state = 'SUCCESS'

        if result._task.action in C.MODULE_NO_JSON and 'ansible_job_id' not in result._result:
            self._display.display(self.command_generic_msg(result._host.get_name(), result._result, state),
                                  color=None)
        else:
            self._display.display(
                "[ok]%s | %s => %s" % (result._host.get_name(), state, self._dump_results(result._result, indent=4)),
                color=None)

        hostname = result._host.get_name()
        vars = result._host.get_vars()
        ansible_ssh_host = vars.get('ansible_ssh_host')
        if ansible_ssh_host:
            record = db.collection('machines').find_one({'ansible_ssh_host': ansible_ssh_host})
            if record and record.get('state') != 'active':
                update = {
                    '$set': {
                        'state': 'active',
                        'updated_at': datetime.datetime.now()
                    }
                }
                db.collection('machines').update_one({'ansible_ssh_host': ansible_ssh_host}, update=update)

        self.host_ok[hostname] = result
        dumper = self.get_result(result)
        dumper.update({'state': 'success'})
        self.dumper[hostname] = dumper
        # self.formatter.v2_runner_on_ok(result)

    def v2_runner_on_failed(self, result, *args, **kwargs):
        # minimal handler
        self._handle_exception(result._result)
        self._handle_warnings(result._result)
        if result._task.action in C.MODULE_NO_JSON and 'module_stderr' not in result._result:
            self._display.display(self.command_generic_msg(result._host.get_name(), result._result, "FAILED"),
                                  color=None)
        else:
            self._display.display(
                "[failed]%s | FAILED! => %s" % (result._host.get_name(), self._dump_results(result._result, indent=4)),
                color=None)

        hostname = result._host.get_name()
        self.host_failed[hostname] = result
        dumper = self.get_result(result)
        dumper.update({'state': 'failed'})
        self.dumper[hostname] = dumper
        notification = 'ansible run on failed, host:{}, job:{}'.format(hostname, self.job.get('name'))
        self.notify(notification)


    def v2_on_file_diff(self, result):
        if 'diff' in result._result and result._result['diff']:
            self._display.display(self._get_diff(result._result['diff']))

    def v2_runner_on_skipped(self, result):
        self._display.display("%s | SKIPPED" % (result._host.get_name()), color=None)

    def get_result(self, result):
        return json.loads(self._dump_results(result._result))

    def notify(self, message):
        job = self.job
        if job:
            notify = Notify()
            users = self.job.get('maintainer') or []
            for username in users:
                user = db.collection('users').find_one({'username': username})
                if not user:
                    continue

                notify.dispatch(str(user.get('_id')), msg_type='task', content=message)

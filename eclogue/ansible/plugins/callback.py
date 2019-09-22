import json
import datetime
from ansible.plugins.callback import CallbackBase
from eclogue.ansible.display import Display as ECDisplay
from ansible.utils.display import Display
from eclogue.model import db


class CallbackModule(CallbackBase):

    def __init__(self, display=None):
        display = display or ECDisplay()
        super(CallbackModule, self).__init__(display=display)
        self._display =display
        self.host_ok = {}
        self.host_unreachable = {}
        self.host_failed = {}
        self.dumper = {}

    def v2_runner_on_unreachable(self, result):
        # super(CallbackModule, self).v2_runner_on_unreachable(result)
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
        print(dumper)

    def v2_runner_on_ok(self, result, *args, **kwargs):
        # super(CallbackBase, self).v2_runner_on_ok(result)
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
        # super(CallbackModule, self).v2_runner_on_failed(result)
        hostname = result._host.get_name()
        self.host_failed[hostname] = result
        dumper = self.get_result(result)
        dumper.update({'state': 'failed'})
        self.dumper[hostname] = dumper
        # self.formatter.v2_runner_on_failed(result)

    def get_result(self, result):
        return json.loads(self._dump_results(result._result))

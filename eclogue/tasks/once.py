import uuid
import time
import sys
import json

from eclogue.ansible.runer import PlayBookRunner, AdHocRunner
from tasktiger import Task
from eclogue.tasks.reporter import Reporter
from eclogue.models.perform import Perform
from eclogue.tasks import tiger
from eclogue.lib.logger import get_logger
from eclogue.utils import md5
from eclogue.lib.helper import parse_cmdb_inventory
from eclogue.lib.credential import get_credential_content_by_id
from tempfile import NamedTemporaryFile

logger = get_logger('console')


def dispatch(payload):
    hosts = payload.get('inventory')
    tasks = payload.get('tasks')
    if not hosts or not tasks:
        return None
    uid = md5(str(json.dumps(payload)))
    username = payload.get('username')
    run_id = payload.get('req_id') or str(uuid.uuid4())
    params = [run_id, payload]
    queue_name = 'book_runtime'
    func = run
    task = Task(tiger, func=func, args=params, queue=queue_name,
                unique=True, lock=True, lock_key=uid)
    run_record = {
        'uid': uid,
        'run_id': run_id,
        'run_by': username,
        'options': payload,
        'result': '',
        'state': 'pending',
        'created_at': time.time(),
        'updated_at': time.time(),
    }
    result = Perform.insert_one(run_record)
    task.delay()

    return result.inserted_id


def run(run_id, payload):
    perform = Perform.find_one({'run_id': run_id})
    start_at = time.time()
    state = 'progressing'
    result = ''
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    sys.stderr = sys.stdout = temp_stdout = Reporter(run_id)
    try:
        run_type = payload.get('run_type')
        inventory = payload.get('inventory')
        inventory = parse_cmdb_inventory(inventory)
        private_key = payload.get('private_key')
        entry = payload.get('entry')
        options = payload.get('options')
        tasks = payload.get('tasks')
        if run_type == 'adhoc':
            with NamedTemporaryFile('w+t', delete=True) as fd:
                if private_key:
                    key_text = get_credential_content_by_id(private_key, 'private_key')
                    if not key_text:
                        raise Exception('invalid private_key')
                    fd.write(key_text)
                    fd.seek(0)
                    options['private_key'] = fd.name
                runner = AdHocRunner(inventory, options=options)
                runner.run('all', tasks)
                result = runner.format_result()
                state = 'finish'
        else:
            with NamedTemporaryFile('w+t', delete=True) as fd:
                if private_key:
                    key_text = get_credential_content_by_id(private_key, 'private_key')
                    if not key_text:
                        raise Exception('invalid private_key')
                    fd.write(key_text)
                    fd.seek(0)
                    options['private_key'] = fd.name

                with NamedTemporaryFile('w+t', delete=True) as fh:
                    fh.write(entry)
                    fh.seek(0)
                    runner = PlayBookRunner(inventory, options)
                    runner.run(fh.name)
                    result = runner.format_result()
                    state = 'finish'
    except Exception as err:
        result = str(err)
        extra = {'run_id': run_id}
        logger.error('run task with exception: {}'.format(result), extra=extra)
        state = 'error'
        raise err

    finally:
        content = temp_stdout.getvalue()
        temp_stdout.close(True)
        sys.stdout = old_stdout
        sys.stderr = old_stderr
        finish_at = time.time()
        update = {
            '$set': {
                'start_at': start_at,
                'finish_at': finish_at,
                'state': state,
                'duration': finish_at - start_at,
                'result': str(result),
                'trace': content,
            }
        }
        Perform.update_one({'_id': perform['_id']}, update=update);

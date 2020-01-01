import uuid
import time
import sys
import os
from optparse import OptionParser

from eclogue.lib.workspace import Workspace
from eclogue.models.book import Book
from eclogue.vcs.versioncontrol import GitDownload
from eclogue.ansible.runer import PlayBookRunner, AdHocRunner
from tasktiger import TaskTiger, Task
from eclogue.tasks.reporter import Reporter
from eclogue.models.perform import Perform
from eclogue.tasks import tiger
from eclogue.lib.logger import get_logger

logger = get_logger('console')


def dispatch(book_id, entry, options):
    book = Book.find_by_id(book_id)
    if not book:
        return False

    username = options.get('username')
    run_id = str(uuid.uuid4())
    params = [book_id, run_id]
    args = options.get('args')
    if not args or not entry:
        return False

    queue_name = 'book_runtime'
    func = run
    task = Task(tiger, func=func, args=params, kwargs=options, queue=queue_name,
                unique=True, lock=True, lock_key=book_id)
    run_record = {
        'book_id': book_id,
        'run_id': run_id,
        'run_by': username,
        'args': args,
        'result': '',
        'state': 'pending',
        'created_at': 1,
        'updated_at': 2,
    }
    Perform.insert_one(run_record)
    task.delay()


def run(book_id, run_id, options):
    perform = Perform.find_by_id(run_id)
    if not perform:
        return False

    book = Book.find_by_id(book_id)
    if not book:
        return False

    start_at = time.time()
    state = 'progressing'
    result = ''
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    sys.stderr = sys.stdout = temp_stdout = Reporter(run_id)
    try:
        wk = Workspace()
        if book.repo == 'git':
            vcs = GitDownload(book.get('repo_options'))
            dest = vcs.install()
            # @todo

        book_name = book.get('name')
        dest = wk.load_book_from_db(book_name, build_id=run_id)

        inventory = os.path.join(dest, options['inventory'])
        entry = os.path.join(dest, options['entry'])
        args = options['args']
        runner = PlayBookRunner(inventory, args)
        runner.run([entry])
        result = runner.get_result()
        state = 'finish'
    except Exception as err:
        result = str(err)
        extra = {'run_id': run_id}
        logger.error('run task with exception: {}'.format(result), extra=extra)
        state = 'error'

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
                'result': result,
                'trace': content,
            }
        }
        Perform.update_one({'_id': perform['_id']}, update=update);

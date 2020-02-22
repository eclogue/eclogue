import uuid
import time
import os
import sys

from eclogue.models.book import Book
from eclogue.vcs.versioncontrol import GitDownload
from eclogue.ansible.runer import PlayBookRunner, AdHocRunner
from tasktiger import Task
from eclogue.tasks.reporter import Reporter
from eclogue.models.perform import Perform
from eclogue.tasks import tiger
from eclogue.lib.logger import get_logger
from eclogue.lib.builder import build_book_from_db
from eclogue.ansible.host import parser_inventory



logger = get_logger('console')


def dispatch(book_id, entry, payload):
    book = Book.find_by_id(book_id)
    if not book:
        return False

    options = payload.get('options')
    username = payload.get('username')
    run_id = payload.get('req_id') or str(uuid.uuid4())
    params = [book_id, run_id]
    options = payload.get('options')
    if not entry:
        return False

    queue_name = 'book_runtime'
    func = run
    task = Task(tiger, func=func, args=params, kwargs=options, queue=queue_name,
                unique=True, lock=True, lock_key=book_id)
    run_record = {
        'book_id': book_id,
        'run_id': run_id,
        'run_by': username,
        'options': options,
        'result': '',
        'state': 'pending',
        'created_at': 1,
        'updated_at': 2,
    }
    result = Perform.insert_one(run_record)
    task.delay()

    return result.inserted_id


def run(book_id, run_id, **options):
    perform = Perform.find_one({'run_id': run_id})
    book = Book.find_by_id(book_id)
    start_at = time.time()
    state = 'progressing'
    result = ''
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    sys.stderr = sys.stdout = temp_stdout = Reporter(run_id)
    try:
        if book.get('repo') == 'git':
            vcs = GitDownload(book.get('repo_options'))
            install_path = vcs.install()
            # @todo

        book_name = book.get('name')
        with build_book_from_db(book_name, build_id=run_id) as dest:
            if not dest:
                result = 'install book failed'
                logger.warning(result)
                state = 'finish'
            else:
                inventory = os.path.join(dest, options['inventory'])
                entry = os.path.join(dest, options['entry'].pop())
                options['tags'] = options['tags'].split(',')
                options['basedir'] = dest
                runner = PlayBookRunner(inventory, options)
                runner.run([entry])
                result = runner.get_result()
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

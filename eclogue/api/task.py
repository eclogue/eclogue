import yaml
import json
import time
from datetime import datetime, date, timedelta
from bson import ObjectId
from flask import jsonify, request
from eclogue.model import db
from eclogue.tasks.dispatch import tiger
from tasktiger import Task
from tasktiger._internal import ERROR, ACTIVE, QUEUED, SCHEDULED
from tasktiger.exceptions import TaskNotFound
from eclogue.middleware import jwt_required, login_user
from eclogue.models.job import Job
from eclogue.scheduler import scheduler
from eclogue.lib.logger import logger


@jwt_required
def monitor():
    """
    :return: json response
    """
    queue_stats = tiger.get_queue_stats()
    print(queue_stats)
    sorted_stats = sorted(queue_stats.items(), key=lambda k: k[0])
    queues = dict()
    for queue, stats in sorted_stats:
        queue_list = queue.split('.')
        if len(queue_list) == 2:
            queue_base, job_id = queue_list
            job = db.collection('jobs').find_one({'_id': ObjectId(job_id)})
            job_name = job.get('name') if job else None
        else:
            queue_base = queue_list[0]
            job_id = None
            job_name = None
        # job = db.collection('jobs').find_one({'_id': ObjectId(job_id)})
        if queue_base not in queues:
            queues[queue_base] = []

        queues[queue_base].append({
            'queue': queue,
            'job_id': job_id,
            'job_name': job_name,
            'stats': stats,
            'total': tiger.get_total_queue_size(queue),
            'lock': tiger.get_queue_system_lock(queue)
        })

    schedule_jobs = scheduler.get_jobs()
    schedules = []
    for job in schedule_jobs:
        stats = job.__getstate__()
        item = {}
        for field, value in stats.items():
            item[field] = str(value)
        schedules.append(item)

    # today = date.today()
    # today = datetime.combine(today, datetime.min.time())
    # tomorrow = date.today() + timedelta(days=1)
    # tomorrow = datetime.combine(tomorrow, datetime.min.time())
    # print(time.mktime(today.timetuple()), today)
    histogram = db.collection('tasks').aggregate([
        {
            '$match': {
                'created_at': {
                    '$gte': time.time() - 86400 * 7,
                    '$lte': time.time()
                },
            }
        },
        {
            '$group': {
                '_id': {
                    'interval': {
                        '$subtract': [
                            {'$divide': ['$created_at', 3600]},
                            {'$mod': [{'$divide': ['$created_at', 3600]}, 1]}
                        ]
                    },
                    'state': '$state',
                },
                'count': {
                    '$sum': 1
                }
            }
        },
    ])

    task_histogram = {}
    for item in histogram:
        print(item)
        primary = item['_id']
        state = primary.get('state')
        interval = 3600 * primary.get('interval')
        if not task_histogram.get(interval):
            task_histogram[interval] = {
                'date': interval,
                'error': 0,
                'finish': 0,
                'queued': 0,
            }

        task_histogram[interval].update({
            state: item.get('count')
        })

    task_state_pies = db.collection('tasks').aggregate([
        {
            '$match': {
                'created_at': {
                    '$gte': time.time() - 86400 * 7,
                    '$lte': time.time()
                },
            }
        },
        {
            '$group': {
                '_id': {
                    'state': '$state',
                },
                'count': {
                    '$sum': 1
                }
            }
        }
    ])

    task_state_pies = list(task_state_pies)
    for item in task_state_pies:
        item['state'] = item['_id']['state']

    task_pies = {
        'jobType': [
            {
                'name': 'adhoc',
                'count': db.collection('jobs').count({'type': 'adhoc'})
            },
            {
                'name': 'playbook',
                'count': db.collection('jobs').count({'type': 'playbook'})
            }
        ],
        'runType': [
            {
                'name': 'schedule',
                'count': db.collection('jobs').count({'template.schedule': {'$exists': True}})
            },
            {
                'name': 'trigger',
                'count': db.collection('jobs').count({'template.runType': {'$exists': False}})
            }
        ],
    }

    return jsonify({
        'message': 'ok',
        'code': 0,
        'data': {
            'queues': queues,
            'taskHistogram': list(task_histogram.values()),
            'taskPies': task_pies,
            'taskStatePies': task_state_pies,
            'schedule': schedules,
        },
        # 'schedule': schedules
    })


@jwt_required
def get_job_tasks(_id):
    query = request.args
    job = db.collection('tasks').find_one({'_id': ObjectId(_id)})
    if not job:
        return jsonify({
            'message': 'job not found',
            'code': 194040
        }), 404

    status = query.get('status')
    page = int(query.get('page', 1))
    size = int(query.get('size', 25))
    offset = (page - 1) * size
    where = {
        'job_id': _id,
    }

    if status:
        where['status'] = status

    cursor = db.collection('tasks').find(where, limit=size, skip=offset)
    total = cursor.count()

    return jsonify({
        'message': 'ok',
        'code': 0,
        'data': {
            'list': list(cursor),
            'total': total,
            'page': page,
            'pageSize': size
        }
    })


@jwt_required
def get_queue_tasks():
    query = request.args
    queue = query.get('queue')
    state = query.get('state')
    page = int(query.get('page', 1))
    size = int(query.get('pageSize', 500))
    offset = (page - 1) * size
    if not queue or not state:
        return jsonify({
            'message': 'invalid params',
            'code': 194000
        }), 400

    n, tasks = Task.tasks_from_queue(tiger, queue, state, skip=offset, limit=size, load_executions=1)
    bucket = []
    for task in tasks:
        data = task.data.copy()

        del data['args']
        record = db.collection('tasks').find_one({'t_id': task.id})
        if record:
            job_record = db.collection('jobs').find_one({'_id': ObjectId(record['job_id'])})
            if job_record:
                data['job_name'] = job_record.get('name')

            data['state'] = record.get('state')
            data['result'] = record['result']
        else:
            data['job_name'] = 'default'
        data['executions'] = task.executions

        bucket.append(data)

    return jsonify({
        'message': 'ok',
        'code': 0,
        'data': {
            'list': bucket,
            'total': n,
        }
    })


@jwt_required
def get_task_history():
    query = request.args or {}
    page = int(query.get('page', 1))
    size = int(query.get('pageSize', 50))
    skip = (page - 1) * size
    keyword = query.get('keyword')
    where = {}
    if keyword:
        where['name'] = keyword

    cursor = db.collection('tasks').find(where, skip=skip, limit=size)
    total = cursor.count()
    tasks = []
    job = Job()
    for task in cursor:
        job_id = task.get('job_id')
        if not job_id:
            continue

        task['job'] = job.find_by_id(job_id)
        tasks.append(task)

    return jsonify({
        'message': 'ok',
        'code': 0,
        'data': {
            'list': tasks,
            'total': total,
            'page': page,
            'pageSize': size,
        }
    })


@jwt_required
def retry(_id, state):
    record = db.collection('tasks').find_one({'_id': ObjectId(_id)})
    if not record:
        return jsonify({
            'message': 'task not found',
            'code': 194041
        }), 404

    task_id = record.get('t_id')
    queue = record.get('queue')
    try:
        task = Task.from_id(tiger, queue, state, task_id)
        task.retry()
        db.collection('tasks').update_one({'_id': record['_id']}, {'$set': {
            'updated_at': datetime.now(),
            'state': state,
        }})
        extra = {
            'queue': queue,
            'task_id': task_id,
            'from_state': state,
            'to_state': QUEUED
        }
        logger.info('retry task', extra=extra)
    except TaskNotFound:
        return jsonify({
            'message': 'invalid task',
            'code': 104044
        }), 404

    return jsonify({
        'message': 'ok',
        'code': 0,
    })


@jwt_required
def cancel(_id, state):
    print(_id, state)

    record = db.collection('tasks').find_one({'_id': ObjectId(_id)})
    if not record:
        return jsonify({
            'message': 'task not found',
            'code': 194041
        }), 404

    task_id = record.get('t_id')
    queue = record.get('queue')
    try:
        task = Task.from_id(tiger, queue, state, task_id)
        task.cancel()
        db.collection('tasks').update_one({'_id': record['_id']}, {'$set': {
            'updated_at': datetime.now(),
            'state': 'cancel',
        }})
        extra = {
            'queue': queue,
            'task_id': task_id,
            'from_state': state,
            'to_state': None
        }
        logger.info('cancel task', extra=extra)
    except TaskNotFound:
        return jsonify({
            'message': 'invalid task',
            'code': 104044
        }), 404

    return jsonify({
        'message': 'ok',
        'code': 0,
    })


@jwt_required
def delete_task(_id, state):
    record = db.collection('tasks').find_one({'t_id': _id})
    if not record:
        return jsonify({
            'message': 'task not found',
            'code': 194041
        }), 404

    task_id = record.get('t_id')
    queue = record.get('queue')
    try:
        task = Task.from_id(tiger, queue, state, task_id)
        task._move(from_state=state)
        db.collection('tasks').update_one({'_id': record['_id']}, {'$set': {
            'updated_at': datetime.now(),
            'state': 'delete',
        }})
        extra = {
            'queue': queue,
            'task_id': task_id,
            'from_state': state,
            'to_state': None
        }
        logger.info('cancel task', extra=extra)
    except TaskNotFound:
        return jsonify({
            'message': 'invalid task',
            'code': 104044
        }), 404

    return jsonify({
        'message': 'ok',
        'code': 0,
    })


def pause_queue():
    """
    @todo
    :return:
    """
    pass


def task_logs(_id):
    if not ObjectId.is_valid(_id):
        return jsonify({
            'message': 'invalid id',
            'code': 104000
        }), 400

    query = request.args
    page = int(query.get('page', 1))
    limit = 1000
    skip = (page - 1) * limit
    obj_id = ObjectId(_id)
    record = db.collection('tasks').find_one({'_id': obj_id})
    if not record:
        return jsonify({
            'message': 'record not found',
            'code': 104040
        }), 404

    task_id = str(record.get('_id'))
    logs = db.collection('logs').find({'task_id': task_id}, skip=skip, limit=limit)
    total = logs.count()
    records = []
    for log in logs:
        hostname = log.get('hostname')
        level = log.get('level')
        message = log.get('message')
        timestamp = log.get('timestamp')
        line_format = '{0}[{1}]{2}\n[{3}]\n'.format(timestamp, hostname, level, message)
        records.append(line_format)

    return jsonify({
        'message': 'ok',
        'code': 0,
        'data': {
            'list': records,
            'total': total,
            'page': page,
            'pageSize': limit,
            'state': record.get('state')
        }
    })


@jwt_required
def get_schedule_task(_id):
    schedule = scheduler.get_job(job_id=_id)
    if not schedule or not hasattr(schedule, '__getstate__'):
        return jsonify({
            'message': 'record not found',
            'code': 104040
        }), 404

    result = {}
    for key, value in schedule.__getstate__().items():
        result[key] = str(value)

    return jsonify({
        'message': 'ok',
        'code': 0,
        'data': result,
    })


@jwt_required
def pause_schedule(job_id):
    job = scheduler.get_job(job_id)
    if not job:
        return jsonify({
            'message': 'record not found',
            'code': 104040,
        }), 404

    job.pause()

    return jsonify({
        'message': 'ok',
        'code': 0,
    })


@jwt_required
def resume_schedule(job_id):
    job = scheduler.get_job(job_id)
    if not job:
        return jsonify({
            'message': 'record not found',
            'code': 104040,
        }), 404

    job.resume()

    return jsonify({
        'message': 'ok',
        'code': 0,
    })


@jwt_required
def remove_schedule(job_id):
    job = scheduler.get_job(job_id)
    if not job:
        return jsonify({
            'message': 'record not found',
            'code': 104040,
        }), 404

    job.remove()

    return jsonify({
        'message': 'ok',
        'code': 0,
    })


@jwt_required
def reschedule_schedule(job_id):
    payload = request.get_json() or {}
    reschedule = payload.get('reschedule')
    if reschedule:
        return jsonify({
            'message': 'invalid schedule params',
            'code': 104004
        }), 400

    job = scheduler.get_job(job_id)
    if not job:
        return jsonify({
            'message': 'record not found',
            'code': 104040,
        }), 404

    job.reschedule()

    return jsonify({
        'message': 'ok',
        'code': 0,
    })


@jwt_required
def modify_schedule(job_id):
    """
    @todo check changed params
    :param job_id:
    :return:
    """
    payload = request.get_json() or {}
    change = payload.get('change')
    if change:
        return jsonify({
            'message': 'invalid schedule params',
            'code': 104004
        }), 400

    job = scheduler.get_job(job_id)
    if not job:
        return jsonify({
            'message': 'record not found',
            'code': 104040,
        }), 404

    job.modify(change)

    return jsonify({
        'message': 'ok',
        'code': 0,
    })

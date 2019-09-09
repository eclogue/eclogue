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
from eclogue.middleware import jwt_required, login_user
from eclogue.models.job import Job
from eclogue.scheduler import scheduler


@jwt_required
def monitor():
    """
    :return: json response
    """
    queue_stats = tiger.get_queue_stats()
    print(queue_stats)
    sorted_stats = sorted(queue_stats.items(), key=lambda k: k[0])
    groups = dict()
    for queue, stats in sorted_stats:
        print('>>??', queue, stats)
        queue_list = queue.split('#')
        if len(queue_list) == 2:
            queue_base, job_id = queue_list
            job = db.collection('jobs').find_one({'_id': ObjectId(job_id)})
            job_name = job.get('name') if job else None
        else:
            queue_base = queue_list[0]
            job_id = None
            job_name = None
        # job = db.collection('jobs').find_one({'_id': ObjectId(job_id)})
        if queue_base not in groups:
            groups[queue_base] = []
        groups[queue_base].append({
            'queue': queue,
            'job_id': job_id,
            'job_name': job_name,
            'stats': stats,
            'total': tiger.get_total_queue_size(queue),
            'lock': tiger.get_queue_system_lock(queue)
        })

    schedule_jobs = scheduler.get_jobs()
    # print('schedule===', schedule_jobs)
    schedules = []
    for job in schedule_jobs:
        stats = job.__getstate__()
        item = {}
        for field, value in stats.items():
            item[field] = str(value)
        schedules.append(item)

    today = date.today()
    today = datetime.combine(today, datetime.min.time())
    tomorrow = date.today() + timedelta(days=1)
    tomorrow = datetime.combine(tomorrow, datetime.min.time())
    print(today, tomorrow)
    integram = db.collection('tasks').aggregate([
        {
            '$match': {
                'created_at': {
                    '$gte': today,
                    '$lte': tomorrow
                },
            }
        },
        # {
        #     '$group': {
        #         # '_id': {
        #         #     # "$subtract": [
        #         #     #     {"$subtract": ["$created_at", datetime.datetime.strptime('1970-01-01', "%Y-%m-%d").time()]},
        #         #     #     {"$mod": [
        #         #     #         {"$subtract": ["$created", datetime.datetime.strptime('1970-01-01', "%Y-%m-%d").time()]},
        #         #     #         1000 * 60 * 30
        #         #     #     ]
        #         #     #     }
        #         #     # ]
        #         #     # 'month': '$month',
        #         #     # 'minutes': '$minutes',
        #         #     # 'year': '$year',
        #         #     'timestamp': '$created_at'
        #         #
        #         # },
        #         '_id': {
        #             'hour': '$hour'
        #         },
        #         'count': {
        #             '$sum': 1
        #         }
        #     },
        # },
        {
            '$group': {
                '_id': {
                    "$subtract": [
                        {"$subtract": ['$created_at', 1]},
                        {"$mod": [
                            {"$subtract": ['$created_at', 1]},
                            1000 * 60 * 30
                        ]}
                    ]
                }
            }
        },
        # {
        #     '$project': {
        #         '_id': 1,
        #         'month': {'$month': '$created_at'},
        #         # 'hour': {'$hour': '$created_at'},
        #         # 'minutes': {'$minute': '$created_at'},
        #         'count': 1,
        #     }
        # }
        # {
        #     '$project': {
        #         '_id': 1,
        #         'created_at': 1,
        #         'job_id': 1,
        #         'state': 1,
        #         # 'timestamp': {'$multiply': ['$created_at', 1000]},
        #
        #     }
        # }
    ])

    print('iiiiiii', list(integram))

    return jsonify({
        'message': 'ok',
        'code': 0,
        'data': groups,
        'schedule': schedules
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
        data = task.data
        print('---->', data)

        del data['args']
        record = db.collection('tasks').find_one({'t_id': task.id})
        if record:
            data['state'] = record.get('state')
            data['job_name'] = record.get('name')
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
    task = Task.from_id(tiger, queue, state, task_id)
    task.cancel()

    return jsonify({
        'message': 'ok',
        'code': 0,
    })


@jwt_required
def cancel(_id, state):
    record = db.collection('tasks').find_one({'_id': ObjectId(_id)})
    if not record:
        return jsonify({
            'message': 'task not found',
            'code': 194041
        }), 404

    task_id = record.get('t_id')
    queue = record.get('queue')
    task = Task.from_id(tiger, queue, state, task_id)
    task.cancel()

    return jsonify({
        'message': 'ok',
        'code': 0,
    })


def pause_queue():
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

import datetime

from flask import request, jsonify
from eclogue.model import db
from eclogue.scheduler import scheduler
from eclogue.tasks.dispatch import tiger
from eclogue.models.host import Host
from eclogue.models.task import task_model
from eclogue.models.book import book
from eclogue.middleware import jwt_required


@jwt_required
def dashboard():
    hosts = Host().collection.aggregate([{
        '$group': {
            '_id': '$state',
            'count': {
                '$sum': 1
            }
        }
    }])
    apps = db.collection('apps').aggregate([
        {
            '$group': {
                '_id': '$type',
                'count': {
                    '$sum': 1
                }
            },
        },
    ])
    jobs = db.collection('jobs').aggregate([
        {
            '$group': {
                '_id': '$type',
                'count': {
                    '$sum': 1
                }
            },
        },
    ])
    state_pies = task_model.state_pies()
    histogram = task_model.histogram()
    playbooks = book.collection.aggregate([{
        '$group': {
            '_id': '$status',
            'count': {
                '$sum': 1
            }
        }
    }])
    config_count = db.collection('configurations').count()
    duration = task_model.duration()
    run_number_pies = task_model.job_run_pies()

    return jsonify({
        'message': 'ok',
        'code': 0,
        'data': {
            'apps': list(apps),
            'hosts': list(hosts),
            'jobs': list(jobs),
            'taskPies': state_pies,
            'taskHistogram': list(histogram),
            'playbooks': list(playbooks),
            'config': config_count,
            'jobDuration': duration,
            'jobRunPies': run_number_pies,
        }
    })

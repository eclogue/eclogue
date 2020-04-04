from uuid import uuid4
from eclogue.models.host import Host
from eclogue.ansible.runer import AdHocRunner
from eclogue.lib.logger import logger
from apscheduler.schedulers.gevent import GeventScheduler


def ansible_inventory_patrol():
    uuid = str(uuid4())
    logger.info('start check ansible inventory', extra={'uuid': uuid})
    where = {
        'state': 'active',
        'status': {
            '$ne': -1
        }
    }
    page = 1
    limit = 50
    while True:
        skip = (page - 1) * limit
        records = Host.find(where, skip=skip, limit=limit)
        records = list(records)
        if not records:
            break

        try:
            inventory = _pack_inventory(records)
            if not inventory:
                continue

            tasks = [{
                'action': {
                    'module': 'ping',
                }
            }]
            options = {}
            runner = AdHocRunner(inventory, options)
            runner.run(pattern='all', tasks=tasks)
        except Exception as e:
            logger.error('ansible inventory patrol catch exception: {}'.format(str(e)))
        finally:
            page += 1

    logger.info('finish check ansible inventory', extra={'uuid': uuid})


def _pack_inventory(records):
    inventory = {
        'patrol': {}
    }
    hosts = {}
    for record in records:
        ssh_host = record.get('ansible_ssh_host')
        ssh_user = record.get('ansible_ssh_user', 'root')
        if not ssh_host or not ssh_user:
            Host.update_one({'_id': record['_id']}, {'$set': {'state': 'unreachable'}})
            continue

        hosts[record['node_name']] = {
            'ansible_ssh_host': ssh_host,
            'ansible_ssh_user': ssh_user,
            'ansible_ssh_port': record.get('ansible_ssh_port') or 22,
        }

    inventory['patrol'] = {
        'hosts': hosts
    }

    return inventory


def register_schedule(minutes=0):
    minutes = minutes or 60
    scheduler = GeventScheduler()
    func = ansible_inventory_patrol
    name = func.__name__
    job_id = '5db150f3e3f7e0677091329f'
    if scheduler.state != 1:
        scheduler.start()
    job = scheduler.get_job(job_id=job_id)
    if not job:
        scheduler.add_job(func=func, trigger='interval', minutes=minutes, name=name, id=job_id)


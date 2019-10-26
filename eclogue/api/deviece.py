import hashlib
import os
import pprint
import stat
import time

from bson import ObjectId
from flask import current_app, jsonify, request
from eclogue.middleware import login_user, jwt_required
from eclogue.model import db


@jwt_required
def explore():
    # user = login_user
    payload = request.get_json()
    if not payload:
        return jsonify({
            'message': 'illegal param',
            'code': 104000
        }), 400
    if not payload.get('hosts'):
        return jsonify({
            'message': 'invalid hosts',
            'code': 104000
        }), 400

    hosts = ','.join(payload['hosts']) + ','
    tasks = [{
        'action': {
            'module': 'setup',
        },
    }]
    private_key_file = '~/.ssh/id_rsa'
    # player.run(hosts, tasks)
    # result = player.get_result()
    # print(hosts, result)

    # if not user.get('admin'):
    #     return jsonify({
    #         'message': 'admin required',
    #         'code': 104010
    #     }), 401

    return jsonify({
        'message': 'ok',
        'code': 0,
        # 'data': result
    })


@jwt_required
def add_hosts():
    user = login_user
    params = request.get_json()
    if not params:
        return jsonify({
            'message': 'illegal param',
            'code': 104000
        }), 400

    ip = params.get('ip')
    if not ip:
        return jsonify({
            'message': 'illegal ip',
            'code': 104001
        }), 400

    group_name = params.get('group')
    hostname = params.get('hostname', ip)
    check = db.collection('groups').find_one({'name': group_name})
    if not check:
        group = {
            'name': group_name,
            'username': user['username'],
            'comment': '',
            'created_at': time.time()
        }
        db.collection('groups').insert_one(group)

    record = {
        'group': group_name,
        'ip': ip,
        'hostname': hostname,
        'username': user['username'],
        'created_at': time.time()
    }

    db.collection('hosts').insert_one(record)

    return jsonify({
        'message': 'ok',
        'code': 0,
    })


@jwt_required
def add_deviece():
    admin = login_user
    params = request.get_json()
    if not params or not params.get('remote_user'):
        return jsonify({
            'message': 'illegal param',
            'code': 104000
        }), 400
    if not params.get('ip') or not params.get('group') or not params.get('use_as'):
        return jsonify({
            'message': 'miss required param',
            'code': 104001
        }), 400

    private_key = db.collection('private_keys').find_one({'username': admin['username']})
    pprint.pprint(private_key)
    if not private_key:
        return jsonify({
            'message': 'miss private_key',
            'code': 104002
        }), 400

    work_dir = current_app.config.workspace['playbook']
    flag = hashlib.md5(admin['username'].encode('utf-8')).hexdigest()
    print('~!@#####', flag,  work_dir)
    user_dir = work_dir + '/' + flag
    private_key_file = user_dir + '/private_key'
    if not os.path.exists(user_dir):
        if not os.path.exists(work_dir):
            os.mkdir(work_dir)
        os.mkdir(user_dir)
    if not os.path.exists(private_key_file):
        with open(private_key_file, 'wb+') as fp:
            print(private_key['file_id'])
            db.fs_bucket().download_to_stream(private_key['file_id'], fp)
            os.chmod(private_key_file, 0o600)
    remote_user = params.get('remote_user', 'root')
    hosts = params.get('remote_user') + '@' + params.get('ip')
    # player = Player(hosts + ',',  dict(connection='ssh', remote_user=remote_user, private_key_file=private_key_file))
    # tasks = [{
    #     'action': {
    #         'module': 'setup',
    #     },
    # }]
    # player.run(host_list=hosts, tasks=tasks)
    # result = player.get_result()
    data = {
        'ip': params['ip'],
        'use_as': params['use_as'],
        'group': params['group'],
        'hostname': params.get('hostname', '')
    }
    # pprint.pprint(result)
    # if result['success'].get(hosts):
    #     machine = result['success'][hosts]
    #     facts = machine['ansible_facts']
    #     record = {
    #         'memory': facts['ansible_memtotal_mb'],
    #         'processor': facts.get('ansible_processor'),
    #         'ipv6': facts.get('ansible_default_ipv6'),
    #         'ipv4': facts.get('ansible_default_ipv4'),
    #         'kernel': facts.get('ansible_kernel'),
    #         'node_name': facts.get('ansible_nodename'),
    #         'swap': facts.get('ansible_swaptotal_mb'),
    #         'bios_version': facts.get('ansible_bios_version'),
    #         'all_ipv4_addresses': facts.get('ansible_all_ipv4_addresses'),
    #         'architecture': facts.get('ansible_architecture'),
    #         'disk': facts.get('ansible_mounts'),
    #         'system': facts.get('ansible_system'),
    #         'dns': facts.get('ansible_dns'),
    #         'product_name': facts.get('ansible_product_name'),
    #         'hostname': facts.get('ansible_hostname'),
    #         'lsb': facts.get('ansible_lsb'),
    #         'interfaces': facts.get('ansible_interfaces'),
    #         'add_by': admin['username'],
    #         'created_at': int(time.time()),
    #         'group': params['group'],
    #         'remote_ip': params['ip'],
    #         'use_as': params['use_as'],
    #     }

    #     db.collection('machines').insert_one(record)
    #     pprint.pprint(record)
    #     # for key, value in facts.items():
    #     #     print('>>>>', key)
    #     #     pprint.pprint(value)
    #
    # return jsonify(data)


@jwt_required
def get_devices():
    query = request.query_string
    skip = 0
    limit = 20
    result = db.collection('machines').find().skip(skip=skip).limit(limit)
    result = list(result)
    collection = db.collection('groups')
    for device in result:
        where = {
            '_id': {
                '$in': device.get('group') or []
            }
        }

        groups = collection.find(where)
        groups = list(groups)
        if groups:
            groups = map(lambda i: i['name'], groups)
            device['group_names'] = list(groups)
        else:
            device['group_name'] = ['ungrouped']

    return jsonify({
        'message': 'ok',
        'code': 0,
        'data': result,
    })


def get_device_info(_id):
    record = db.collection('machines').find_one({'_id': ObjectId(_id)})
    if not record:
        return jsonify({
            'message': 'record not found',
            'code': 104040,
        }), 404

    where = {
        'id': {
            '$in': record.get('group')
        }
    }
    groups = db.collection('groups').find(where)
    group_names = map(lambda i: i['name'], groups)
    group_names = list(group_names)
    record['group_names'] = group_names

    return jsonify({
        'message': 'ok',
        'code': 0,
        'data': record,
    })

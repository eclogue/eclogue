import time
import pymongo
from bson import ObjectId
from flask import request, jsonify
from eclogue.model import db
from eclogue.utils import md5
from eclogue.middleware import jwt_required, login_user
from eclogue.ansible.runer import PlayBookRunner
from eclogue.lib.workspace import Workspace
from eclogue.lib.helper import load_ansible_playbook
from eclogue.lib.inventory import get_inventory_from_cmdb, get_inventory_by_book
from eclogue.ansible.remote import AnsibleGalaxy
from eclogue.lib.logger import logger


@jwt_required
def get_playbook(_id):
    if not _id:
        return jsonify({
            'message': 'invalid id',
            'code': 154000
        }), 400

    book = db.collection('books').find_one({'_id': ObjectId(_id)})
    if not book or not int(book.get('status')):
        return jsonify({
            'message': 'invalid id',
            'code': 154001,
        }), 400

    cursor = db.collection('playbook').find({'book_id': str(book.get('_id'))})
    cursor = cursor.sort([('is_edit', pymongo.ASCENDING), ('path', pymongo.ASCENDING)])
    # for item in cursor:
    #     db.collection('playbook').update_one({'_id': item['_id']}, {'$set': {'book_id': str(item.get('book_id'))}})
    return jsonify({
        'message': 'ok',
        'code': 0,
        'data': list(cursor),
    })


@jwt_required
def get_tags():
    body = request.get_json()
    if not body:
        return jsonify({
            'message': 'miss required params',
            'code': 104000,
        }), 400
    template = body.get('template')
    listtags = template.get('listtags')
    listtasks = template.get('listtasks')
    if not listtags or not listtasks:
        return jsonify({
            'message': 'invalid params',
            'code': 104001,
        }), 400
    payload = load_ansible_playbook(body)
    if payload.get('message') is not 'ok':
        return jsonify(payload), 400

    data = payload.get('data')
    options = data.get('options')
    wk = Workspace()
    res = wk.load_book_from_db(name=data.get('book_name'), roles=data.get('roles'))
    if not res:
        return jsonify({
            'message': 'book not found',
            'code': 104000,
        }), 400
    entry = wk.get_book_entry(data.get('book_name'), data.get('entry'))
    play = PlayBookRunner([data['inventory']], options)
    play.run(entry)

    return jsonify({
        'message': 'ok',
        'code': 0,
        'data': {
            'tags': list(play.tags),
            'tasks': list(play.tasks),
        }
    })


@jwt_required
def get_inventory():
    query = request.args
    type = query.get('type', 'cmdb')
    if type == 'file':
        bookname = query.get('book')
        hosts = get_inventory_by_book(bookname)
    else:
        keyword = query.get('keyword')
        hosts = get_inventory_from_cmdb(keyword=keyword)
    return jsonify({
        'message': 'ok',
        'code': 0,
        'data': hosts,
    })


@jwt_required
def edit_file(_id):
    params = request.get_json() or request.form
    if not params:
        return jsonify({
            'message': 'invalid params',
            'code': 154000,
        }), 400
    edit_type = params.get('type')
    if edit_type == 'upload':
        return upload_file(_id)

    name = params.get('name')
    role = params.get('role')
    description = params.get('description')
    status = params.get('status', 1)
    maintainer = params.get('maintainer', [])
    is_edit = params.get('is_edit')
    is_dir = params.get('is_dir')
    is_encrypt = params.get('is_encrypt')
    project = params.get('project')
    register = params.get('register')
    content = params.get('content')
    record = db.collection('playbook').find_one({'_id': ObjectId(_id)})
    if not record:
        return jsonify({
            'message': 'record not found',
            'code': 154041,
        }), 404

    data = {
        'status': status,
    }

    if name:
        data['name'] = name
    if role:
        data['role'] = role
    if project:
        data['project'] = project
    if content:
        data['content'] = content
        data['md5'] = md5(content)
    if description:
        data['description'] = description
    if maintainer:
        data['maintainer'] = maintainer
    if is_edit is not None:
        data['is_edit'] = bool(is_edit)
    if is_edit is not None:
        data['is_dir'] = bool(is_dir)
    if is_edit is not None:
        data['is_encrypt'] = bool(is_encrypt)
    if register:
        c_ids = map(lambda i: ObjectId(i), register)
        where = {'_id': {'$in': c_ids}}
        register_config = db.collection('configurations').find(where)
        if not register_config:
            return jsonify({
                'message': 'invalid register config',
                'code': 154042,
            }), 404

        data['register'] = register

    result = db.collection('playbook').update_one({
        '_id': ObjectId(_id)
    }, {
        '$set': data,
    }, upsert=True)
    data['_id'] = result.upserted_id
    logger.info('update playbook file', extra={'record': record, 'changed': data})
    book = db.collection('books').find_one({'_id': ObjectId(record['book_id'])})
    wk = Workspace()
    wk.write_book_file(book.get('name'), record)

    return jsonify({
        'message': 'ok',
        'code': 0,
        'data': data,
    })


def upload_file(_id):
    pass


@jwt_required
def remove_file(_id):
    collection = db.collection('playbook')
    record = collection.find_one({'_id': ObjectId(_id)})
    if not record:
        return jsonify({
            'message': 'record not found',
            'code': 104040
        }), 404

    remove_dir(_id)

    return jsonify({
        'message': 'ok',
        'code': 0,
    })


def remove_dir(_id):
    collection = db.collection('playbook')
    record = collection.find_one({'_id': ObjectId(_id)})
    if not record:
        return False

    children = collection.find({'parent': record['_id']})
    for item in children:
        if item.get('is_dir'):
            remove_dir(item['_id'])
            continue

        collection.delete_one({'_id': item['_id']})
        logger.info('delete playbook file', extra={'record': item})

    collection.delete_one({'_id': record['_id']})
    logger.info('delete playbook file', extra={'record': record})

    return True


def import_galaxy():
    name = 'geerlingguy.composer'
    galaxy = AnsibleGalaxy(['geerlingguy.composer'], {})
    # galaxy.install()
    # result = galaxy.info()
    # result = result[0]
    # galaxy_info = result.get('galaxy_info')
    # record = {
    #     'name': name,
    #     'description': result.get('description'),
    #     'galaxy_info': {
    #         'author': galaxy_info.get('author'),
    #         'company': galaxy_info.get('company'),
    #         'license': galaxy_info.get('license')
    #     },
    #     'type': 'galaxy',
    #     'version': result.get('intalled_version'),
    #     'repo': {
    #         'github_repo': result.get('github_repo'),
    #         'github_branch': result.get('github_branch'),
    #         'github_user': result.get('github_user'),
    #         'commit': result.get('commit'),
    #         'commit_message': result.get('commit_message'),
    #     }
    # }

    logger.warning({'name': '111111\'\'fuck'})

    return jsonify({
        'message': 'ok',
        'code': 0,
        # 'data': record
    })


@jwt_required
def rename(_id):
    oid = ObjectId(_id)
    body = request.get_json()
    file_path = body.get('path')
    if not file_path:
        return jsonify({
            'message': 'invalid param path',
            'code': 104001,
        }), 400

    upset = {
        '$set': {
            'path': file_path
        }
    }
    record = db.collection('playbook').find_one({'_id': oid})
    if not record:
        return jsonify({
            'message': 'record not found',
            'code': 104040,
        }), 400

    if record.get('is_dir') is True:
        records = db.collection('playbook').find({'parent': record.get('path')})
        for doc in records:
            new_path = doc['path'].replace(record['path'], file_path)
            db.collection('playbook').update_one({'_id': doc['_id']}, {
                '$set': {
                    'path': new_path
                }
            })

    db.collection('playbook').update_one({'_id': oid}, upset)

    return jsonify({
        'message': 'ok',
        'code': 0,
        'data': record
})

import time
import pymongo
import datetime
import os

from bson import ObjectId
from flask import request, jsonify
from eclogue.model import db
from eclogue.utils import md5, is_edit
from eclogue.middleware import jwt_required, login_user
from eclogue.ansible.runer import PlayBookRunner
from eclogue.lib.workspace import Workspace
from eclogue.lib.helper import load_ansible_playbook, get_meta
from eclogue.lib.inventory import get_inventory_from_cmdb, get_inventory_by_book
from eclogue.ansible.remote import AnsibleGalaxy
from eclogue.lib.logger import logger
from eclogue.models.configuration import configuration
from eclogue.models.playbook import Playbook
from eclogue.models.book import Book
from eclogue.models.configuration import Configuration
from eclogue.lib.builder import build_book_from_db


@jwt_required
def get_playbook(_id):
    book = Book.find_by_id(_id)
    if not book or int(book.get('status') == -1):
        return jsonify({
            'message': 'invalid id',
            'code': 154001,
        }), 400

    cursor = Playbook.find({'book_id': str(book.get('_id'))})
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
    with build_book_from_db(name=data.get('book_name'), roles=data.get('roles')) as bookspace:
        if not bookspace:
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
    """
    edit playbook file
    @todo add lock
    :param _id: ObjectId string
    :return: json
    """
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
    can_edit = params.get('is_edit')
    is_dir = params.get('is_dir')
    is_encrypt = params.get('is_encrypt')
    project = params.get('project')
    register = params.get('register')
    content = params.get('content')
    record = Playbook.find_by_id(_id)
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
    if can_edit is not None:
        data['is_edit'] = bool(is_edit)
        data['is_encrypt'] = bool(is_encrypt)
    if is_dir is not None:
        data['is_dir'] = bool(is_dir)
    if register:
        c_ids = map(lambda i: ObjectId(i), register)
        where = {'_id': {'$in': c_ids}}
        register_config = Configuration.find(where)
        if not register_config:
            return jsonify({
                'message': 'invalid register config',
                'code': 154042,
            }), 404

        data['register'] = register

    result = Playbook.update_one({'_id': ObjectId(_id)}, {'$set': data}, upsert=True)
    data['_id'] = result.upserted_id
    book = Book.find_one({'_id': ObjectId(record['book_id'])})
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

    _remove_dir(_id)

    return jsonify({
        'message': 'ok',
        'code': 0,
    })


def _remove_dir(_id):
    collection = db.collection('playbook')
    record = collection.find_one({'_id': ObjectId(_id)})
    if not record:
        return False

    children = collection.find({'parent': record['_id']})
    for item in children:
        if item.get('is_dir'):
            _remove_dir(item['_id'])
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

    record = Playbook.find_by_id(oid)
    if not record:
        return jsonify({
            'message': 'record not found',
            'code': 104040,
        }), 404

    if record.get('path') == file_path:
        return jsonify({
            'message': 'ok',
            'code': 0,
            'data': record
        })

    Playbook().rename(_id, file_path)

    return jsonify({
        'message': 'ok',
        'code': 0,
        'data': record
    })


@jwt_required
def upload():
    files = request.files
    form = request.form
    if not form or not form.get('parent'):
        return jsonify({
            'message': 'illegal param',
            'code': 104000,
        }), 400

    if not files.get('files'):
        return jsonify({
            'message': 'illegal param',
            'code': 104001,
        }), 400

    parent_id = form.get('parent')
    book_id = form.get('bookId')
    if parent_id == '/' and book_id:
        book = Book.find_one({'_id': ObjectId(book_id)})
        if not book:
            return jsonify({
                "message": "record not found",
                "code": 104040,
            }), 404

        parent = {
            'path': '/',
            'book_id': book_id
        }
    else:
        parent = Playbook.find_one({'_id': ObjectId(parent_id)})

    if not parent:
        return jsonify({
            "message": "parent path not found",
            "code": 104004,
        }), 400

    file = files['files']
    filename = file.filename
    path = os.path.join(parent['path'], filename)
    record = {
        'book_id': parent.get('book_id'),
        'path': path,
        'is_dir': False,
    }

    meta = get_meta(path)
    record.update(meta)

    can_edit = is_edit(file)
    if not can_edit:
        file_id = db.save_file(filename=filename, fileobj=file)
        record['file_id'] = file_id
    else:
        content = file.read()
        content = content.decode('utf-8')
        record['content'] = content

    record['is_edit'] = can_edit
    record['created_at'] = int(time.time())
    record['updated_at'] = datetime.datetime.now().isoformat()
    where = {
        'path': path,
        'book_id': ObjectId(parent['book_id'])
    }
    update = {
        '$set': record,
    }
    Playbook.update_one(where, update=update, upsert=True)

    return jsonify({
        'message': 'ok',
        'code': 0,
    })


@jwt_required
def add_folder():
    params = request.get_json()
    if not params or not params.get('id') or not params.get('folder'):
        return jsonify({
            'message': 'illegal param',
            'code': 104000,
        }), 400

    record_id = params.get('id')
    folder = params.get('folder')
    parent = params.get('parent')
    book_id = params.get('book_id')
    parent = parent if parent != '.' else '/'
    parent_path = None
    if parent != '/':
        parent_record = Playbook.find_one({'_id': ObjectId(record_id), 'is_dir': True})
        if not parent_record:
            return jsonify({
                'message': 'invalid params',
                'code': 104001,
            }), 400

        parent_path = parent_record.get('path')

    file_path = os.path.join(parent, folder)
    record = {
        'path': file_path,
        'book_id': book_id,
        'parent': parent_path,
        'is_dir': True,
        'content': '',
        'is_edit': False,
        'add_by': login_user.get('username'),
        'created_at': int(time.time()),
        'updated_at': datetime.datetime.now().isoformat(),
    }
    meta = get_meta(file_path)
    record.update(meta)
    record['additions'] = meta
    check = Playbook.find_one({'book_id': book_id, 'path': record['path']})
    if check:
        additions = check.get('additions') or {}
        additions.update(meta)
        record['additions'] = additions
        Playbook.update_one({'_id': check['_id']}, {'$set': record})
    else:
        Playbook.insert_one(record)

    return jsonify({
        'message': 'ok',
        'code': 0,
    })


@jwt_required
def get_file(_id):
    if not _id:
        return jsonify({
            'message': 'illegal param',
            'code': 104000,
        }), 400

    record = db.collection('playbook').find_one({'_id': ObjectId(_id)})
    if not record:
        return jsonify({
            'message': 'record not found',
            'code': 104040
        }), 404

    if record.get('register'):
        record['configVariables'] = configuration.get_variables(record.get('register'))

    return jsonify({
        'message': 'ok',
        'code': 0,
        'data': record,
    })

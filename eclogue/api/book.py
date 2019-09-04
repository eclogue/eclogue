import time
import datetime
import os
import pymongo

from bson import ObjectId
from tempfile import NamedTemporaryFile
from flask import request, jsonify, send_file
from eclogue.model import db
from eclogue.middleware import jwt_required, login_user
from eclogue.utils import is_edit, md5, make_zip
from eclogue.ansible.vault import Vault
from eclogue.lib.helper import get_meta
from eclogue.lib.workspace import Workspace
from eclogue.models.book import book
from eclogue.models.playbook import playbook
from eclogue.ansible.remote import AnsibleGalaxy
from eclogue.lib.logger import logger
from eclogue.ansible.playbook import check_playbook


@jwt_required
def books():
    query = request.args
    page = int(query.get('page', 1))
    size = int(query.get('pageSize', 50))
    offset = (page - 1) * size
    keyword = query.get('keyword')
    is_admin = login_user.get('is_admin')
    start = query.get('start')
    end = query.get('end')
    maintainer = query.get('maintainer')
    where = {}
    if keyword:
        where['name'] = {
            '$regex': keyword
        }

    if not is_admin:
        where['maintainer'] = {
            '$in': [login_user.get('username')]
        }
    elif maintainer:
        where['maintainer'] = {
            '$in': [maintainer]
        }

    date = []
    if start:
        date.append({
            'created_at': {
                '$gte': int(time.mktime(time.strptime(start, '%Y-%m-%d')))
            }
        })

    if end:
        date.append({
            'created_at': {
                '$lte': int(time.mktime(time.strptime(end, '%Y-%m-%d')))
            }
        })

    if date:
        where['$and'] = date

    cursor = db.collection('books').find(where, skip=offset, limit=size)
    total = cursor.count()
    records = list(cursor)
    data = []
    for item in records:
        where = {
            'role': 'entry',
            'book_id': item['_id'],
        }
        if item.get('status'):
            data.append(item)
            continue

        entry = playbook.collection.find_one(where)
        if not entry:
            book.collection.update_one({'_id': item['_id']}, {'$set': {'status': 0}})
            item['status'] = 0

        data.append(item)

    return jsonify({
        'message': 'ok',
        'code': 0,
        'data': {
            'list': records,
            'page': page,
            'pagesize': size,
            'total': total,
        }
    })


@jwt_required
def add_book():
    params = request.get_json() or request.form
    if not params:
        return jsonify({
            'message': 'invalid params',
            'code': 154000,
        }), 400
    name = params.get('name')
    if not name:
        return jsonify({
            'message': 'name param required',
            'code': 154001,
        }), 400

    existed = db.collection('books').find_one({'name': name})
    if existed:
        return jsonify({
            'message': 'book exist',
            'code': 154003,
        }), 400

    description = params.get('description')
    status = params.get('status', 1)
    pbid = params.get('_id')
    import_type = params.get('importType')
    galaxy_repo = params.get('galaxyRepo')
    maintainer = params.get('maintainer', [])
    if pbid:
        record = db.collection('playbook').find_one({'_id': ObjectId(pbid)})
        if not record:
            return jsonify({
                'message': 'record not found',
                'code': 154041,
            }), 404

    else:
        if import_type == 'galaxy' and galaxy_repo:
            galaxy = AnsibleGalaxy([galaxy_repo])
            galaxy.install()
            logger.info('import galaxy', extra={'repo': galaxy_repo})

    data = {
        'name': name,
        'description': description,
        'maintainer': maintainer,
        'import_type': import_type,
        'galaxy_repo': galaxy_repo,
        'status': int(status),
        'created_at': int(time.time())
    }

    result = db.collection('books').update_one({
        '_id': ObjectId(pbid)
    }, {
        '$set': data,
    }, upsert=True)
    data['_id'] = result.upserted_id

    return jsonify({
        'message': 'ok',
        'code': 0,
        'data': data,
    })


@jwt_required
def edit_book(_id):
    params = request.get_json() or request.form
    if not params:
        return jsonify({
            'message': 'invalid params',
            'code': 154000,
        }), 400
    name = params.get('name')
    description = params.get('description')
    status = params.get('status', 1)
    maintainer = params.get('maintainer', [])
    import_type = params.get('importType')
    galaxy_repo = params.get('galaxyRepo')
    record = db.collection('books').find_one({'_id': ObjectId(_id)})
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

    if description:
        data['description'] = description

    if maintainer:
        data['maintainer'] = maintainer

    if import_type == 'galaxy':
        galaxy = AnsibleGalaxy([galaxy_repo], {'force': True})
        galaxy.install(record.get('_id'))

    db.collection('books').update_one({
        '_id': ObjectId(_id)
    }, {
        '$set': data,
    }, upsert=True)
    logger.info('book update', extra={'record': record, 'changed': data})

    return jsonify({
        'message': 'ok',
        'code': 0,
        'data': data,
    })


@jwt_required
def book_detail(_id):
    record = book.find_by_id(_id)
    if not record:
        return jsonify({
            'message': 'record not found',
            'code': 154041
        }), 400

    return jsonify({
        'message': 'ok',
        'code': 0,
        'data': record,
    })


@jwt_required
def all_books():
    cursor = book.collection.find({})

    return jsonify({
        'message': 'ok',
        'code': 0,
        'data': list(cursor),
    })


@jwt_required
def upload_playbook(_id):
    files = request.files
    record = book.find_by_id(_id)
    if not record:
        return jsonify({
            "message": "parent path not found",
            "code": 104004,
        }), 400

    file = files['file']
    filename = file.filename.lstrip('/')
    path_list = filename.split('/')
    filename = '/'.join(path_list[1:])
    filename = '/' + filename
    home_path, basename = os.path.split(filename)
    file_list = set(_make_path(filename))
    for dirname in file_list:
        check = playbook.collection.find_one({
            'book_id': _id,
            'path': dirname,
        })
        if not check:
            parent_path, name = os.path.split(dirname)
            parent_path = parent_path if parent_path != '/' else None
            parent = {
                'path': dirname,
                'is_dir': True,
                'is_edit': False,
                'book_id': record.get('_id'),
                'parent': parent_path,
                'name': name,
                'created_at': int(time.time()),
            }
            meta = get_meta(dirname)
            parent.update(meta)
            parent['additions'] = meta
            playbook.insert_one(parent)

    data = {
        "path": filename,
        'is_dir': False,
        'parent': home_path or None,
        'book_id': record.get('_id')
    }

    can_edit = is_edit(file)
    if not can_edit:
        file_id = db.save_file(filename=filename, fileobj=file)
        data['file_id'] = file_id
    else:
        content = file.stream.read()
        content = content.decode('utf-8')
        data['is_encrypt'] = Vault.is_encrypted(content)
        if data['is_encrypt']:
            # @todo
            vault = Vault({'vault_pass': ''})
            data['content'] = vault.encrypt_string(content)
            data['md5'] = md5(content)
        else:
            data['content'] = content
            data['md5'] = md5(content)

    meta = get_meta(data['path'])
    data.update(meta)
    data['additions'] = meta
    data['is_edit'] = can_edit
    data['created_at'] = int(time.time())
    data['updated_at'] = datetime.datetime.now().isoformat()
    playbook.collection.update_one({
        'path': filename,
        'book_id': str(record['_id']),
    }, {
        '$set': data,
    }, upsert=True)
    data['book_id'] = str(record['_id'])
    logger.info('upload playbook', extra={'record': record, 'changed': data})

    return jsonify({
        "message": "ok",
        "code": 0,
    })


def _make_path(path):
    if not path:
        return False

    file_list = []
    path = path.lstrip('/')
    dirname, filename = os.path.split(path)
    if filename and dirname:
        file_list.append('/' + dirname)
        file_list.extend(_make_path(dirname))

    return file_list


def download_book(_id):
    record = book.find_by_id(_id)
    if not record:
        return jsonify({
            'message': 'record not found',
            'code': 104040
        }), 404

    name = record.get('name')
    wk = Workspace()
    wk.load_book_from_db(name)
    dirname = wk.get_book_space(name)
    filename = name + '.zip'
    with NamedTemporaryFile('w+t', delete=True) as fd:
        make_zip(dirname, fd.name)

        return send_file(fd.name, attachment_filename=filename)


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
def get_roles_by_book(_id):
    record = db.collection('books').find_one(({
        '_id': ObjectId(_id)
    }))
    if not record:
        return jsonify({
            'message': 'book not found',
            'code': '104001',
        }), 400

    book_id = str(record['_id'])
    check_playbook(book_id)
    condition = {
        'book_id': book_id,
        'role': 'roles',
        'is_dir': True
    }

    print(condition)
    parent = db.collection('playbook').find_one(condition)
    if not parent:
        return jsonify({
            'message': 'ok',
            'code': 0,
            'data': [],
        })

    where = {
        'book_id': book_id,
        'is_dir': True,
        'parent': parent.get('path')
    }
    cursor = db.collection('playbook').find(where)
    records = list(cursor)

    return jsonify({
        'message': 'ok',
        'code': 0,
        'data': records,
    })


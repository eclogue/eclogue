import time
import os
import pymongo
import uuid

from bson import ObjectId
from tempfile import NamedTemporaryFile
from flask import request, jsonify, send_file
from eclogue.model import db
from eclogue.middleware import jwt_required, login_user
from eclogue.utils import is_edit, md5, make_zip
from eclogue.ansible.vault import Vault
from eclogue.lib.helper import get_meta
from eclogue.lib.workspace import Workspace
from eclogue.models.book import Book
from eclogue.models.playbook import Playbook
from eclogue.ansible.remote import AnsibleGalaxy
from eclogue.lib.logger import logger
from eclogue.ansible.playbook import check_playbook
from eclogue.vcs.versioncontrol import GitDownload
from flask_log_request_id import request_id


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
    where = {
        'status': {
            '$ne': -1
        }
    }
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

    cursor = Book.find(where, skip=offset, limit=size)
    total = cursor.count()
    records = list(cursor)
    data = []
    for item in records:

        item['job'] = None
        where = {
            'type': 'playbook',
            'template.entry': {
                '$in': [str(item['_id'])]
            }
        }
        job = db.collection('jobs').find_one(where)
        if job:
            item['job'] = {
                '_id': job.get('_id'),
                'name': job.get('name'),
                'type': job.get('type'),
            }

        if item.get('status'):
            data.append(item)
            continue

        where = {
            'role': 'entry',
            'book_id': item['_id'],
        }
        entry = Playbook.find_one(where)
        if not entry:
            Book.update_one({'_id': item['_id']}, {'$set': {'status': 0}})
            item['status'] = 0

        data.append(item)

    return jsonify({
        'message': 'ok',
        'code': 0,
        'data': {
            'list': records,
            'page': page,
            'pageSize': size,
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

    existed = Book.find_one({'name': name})
    if existed:
        return jsonify({
            'message': 'book exist',
            'code': 154003,
        }), 400

    description = params.get('description')
    status = params.get('status', 1)
    bid = params.get('_id')
    import_type = params.get('importType')
    galaxy_repo = params.get('galaxyRepo')
    maintainer = params.get('maintainer', [])
    if bid:
        record = Book.find_one({'_id': ObjectId(bid)})
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

    result = Book.update_one({'_id': ObjectId(bid)}, {'$set': data}, upsert=True)
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
    record = Book.find_one({'_id': ObjectId(_id)})
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

    Book.update_one({'_id': ObjectId(_id)}, {'$set': data}, upsert=True)
    logger.info('book update', extra={'record': record, 'changed': data})

    return jsonify({
        'message': 'ok',
        'code': 0,
        'data': data,
    })


@jwt_required
def book_detail(_id):
    record = Book.find_by_id(_id)
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
def delete_book(_id):
    record = Book.find_by_id(_id)
    if not record:
        return jsonify({
            'message': 'record not found',
            'code': 154041
        }), 404

    update = {
        '$set': {
            'status': -1,
            'delete_at': time.time(),
            'delete_by': login_user.get('username'),
            'version': str(ObjectId()),
        }
    }
    Book.update_one({'_id': record['_id']}, update=update)
    db.collection('playbook').update_many({'book_id': str(record['_id'])}, update=update)

    return jsonify({
        'message': 'ok',
        'code': 0,
    })


@jwt_required
def all_books():
    query = request.args
    job_id = query.get('id')
    where = {}
    cursor = Book.find({})
    records = list(cursor)
    for book in records:
        def get_children(item):
            return {
                'value': item['_id'],
                'label': item.get('name'),
                'isLeaf': True,
            }

        entries = Playbook.find({'book_id': str(book['_id']), 'role': 'entry'})
        children = map(get_children, entries)
        book['children'] = list(children)

    return jsonify({
        'message': 'ok',
        'code': 0,
        'data': list(records),
    })


@jwt_required
def upload_playbook(_id):
    files = request.files
    record = Book.find_by_id(_id)
    if not record:
        return jsonify({
            "message": "book not found",
            "code": 104004,
        }), 400

    if not files:
        return jsonify({
            'message': 'invalid files params',
            'code': 104001
        }), 400

    file = files['file']
    filename = file.filename.lstrip('/')
    path_list = filename.split('/')
    filename = '/'.join(path_list[1:])
    filename = '/' + filename
    home_path, basename = os.path.split(filename)
    file_list = set(_make_path(filename))
    for dirname in file_list:
        check = Playbook.find_one({
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
                'book_id': _id,
                'parent': parent_path,
                'name': name,
                'created_at': time.time(),
            }
            meta = get_meta(dirname)
            parent.update(meta)
            parent['additions'] = meta
            Playbook.insert_one(parent)

    data = {
        'path': filename,
        'is_dir': False,
        'parent': home_path or None,
        'book_id': _id
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
            # @todo vault password
            vault = Vault()
            data['content'] = vault.encrypt_string(content)
            data['md5'] = md5(content)
        else:
            data['content'] = content
            data['md5'] = md5(content)

    meta = get_meta(data['path'])
    data.update(meta)
    data['additions'] = meta
    data['is_edit'] = can_edit
    data['created_at'] = time.time()
    data['updated_at'] = time.time()
    Playbook.update_one({'path': filename, 'book_id': _id}, {'$set': data}, upsert=True)

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
    record = Book.find_by_id(_id)
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
    with NamedTemporaryFile('w+t', delete=False) as fd:
        make_zip(dirname, fd.name)

        return send_file(fd.name, attachment_filename=filename, as_attachment=True)


@jwt_required
def get_playbook(_id):
    book = Book.find_one({'_id': ObjectId(_id)})
    if not book or not int(book.get('status')):
        return jsonify({
            'message': 'invalid id',
            'code': 154001,
        }), 400

    cursor = Playbook.find({'book_id': str(book.get('_id'))})
    cursor = cursor.sort([('is_edit', pymongo.ASCENDING), ('path', pymongo.ASCENDING)])

    return jsonify({
        'message': 'ok',
        'code': 0,
        'data': list(cursor),
    })


@jwt_required
def get_roles_by_book(_id):
    record = Book.find_one(({
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


@jwt_required
def get_entry(_id):
    book = Book.find_one(({'_id': ObjectId(_id)}))

    if not book:
        return jsonify({
            'message': 'book not found',
            'code': 164000
        }), 400

    where = {
        'book_id': str(book.get('_id')),
        'is_dir': False,
        'role': 'entry',
    }
    cursor = Playbook.find(where)

    return jsonify({
        'message': 'ok',
        'code': 0,
        'data': list(cursor),
    })


@jwt_required
def run(_id):
    is_admin = login_user.get('is_admin')
    book = Book.find_by_id(_id)
    if not book:
        return jsonify({
            'message': 'record not found',
            'code': 10404
        }), 404

    wk = Workspace()
    payload = request.get_json()
    roles = payload.get('options')
    if book.repo == 'git':
        vcs = GitDownload(book.get('repo_options'))
        dest = vcs.install()

    wk = Workspace()
    bookspace = wk.load_book_from_db(name=book.get('name'), roles=roles, build_id=task_id)
    pass




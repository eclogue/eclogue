import time
import datetime
import pprint
import os
import pymongo

from bson.objectid import ObjectId
from flask import current_app, request, jsonify
from eclogue.model import db
from eclogue.middleware import jwt_required, login_user
from eclogue.dumper import Dumper
from eclogue.utils import md5, file_md5, check_workspace, is_edit
from eclogue.config import config
from eclogue.lib.workspace import Workspace
from eclogue.ansible.runer import PlayBookRunner
from eclogue.lib.helper import load_ansible_playbook, get_meta
from eclogue.models.configuration import configuration


class Catheter(object):

    @staticmethod
    @jwt_required
    def get():
        cursor = db.collection('playbook').find()

        return jsonify({
            'message': 'ok',
            'code': 0,
            'data': list(cursor),
        })

    @staticmethod
    @jwt_required
    def drop():
        collection = db.collection('playbook')
        play = collection.find()
        for item in play:
            # print(item['_id'])
            # res = db.fs().delete({'_id': item['_id']})
            # print(res)
            collection.delete_one({'_id': item['_id']})

        fs = db.fs()
        files = fs.find()
        for file in files:
            # print(item['_id'])
            # res = db.fs().delete({'_id': item['_id']})
            # print(res)
            fs.delete(file._id)
        return jsonify({
            'message': 'ok',
            'code': 0,
        })

    @staticmethod
    @jwt_required
    def edit_file(_id):
        if not id:
            return jsonify({
                'message': 'illegal param',
                'code': 104000,
            }), 400

        body = request.get_json()
        content = body.get('content', '')
        vault = body.get('vault', False)
        if vault:
            # @todo encrypt by vauld
            content = content
        update = {
            '$set': {
                'content': content,
                'md5': md5(content.encode('utf8'))
            }
        }
        collection = db.collection('playbook')
        record = collection.find_one({'_id': ObjectId(_id)})
        print(record)
        if not record:
            return jsonify({
                'message': 'record not found',
                'code': 104040
            }), 404
        record['uid'] = record['_id']
        record.pop('_id', None)
        db.collection('file_history').insert_one(record)
        collection.update_one({'_id': ObjectId(_id)}, update)

        return jsonify({
            'message': 'ok',
            'code': 0,
            'data': record,
        })

    @staticmethod
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

    @staticmethod
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
            parent_record = db.collection('playbook').find_one({'_id': ObjectId(record_id), 'is_dir': True})
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
        check = db.collection('playbook').find_one({'book_id': book_id, 'path': record['path']})
        if check:
            additions = check.get('additions')
            additions.update(meta)
            parent['additions'] = additions
            db.collection('playbook').update_one({'_id': check['_id']}, {'$set': record})
        else:
            db.collection('playbook').insert_one(record)

        return jsonify({
            'message': 'ok',
            'code': 0,
        })

    @staticmethod
    @jwt_required
    def upload():
        files = request.files
        form = request.form
        if not form or not form.get('parent'):
            return jsonify({
                'message': 'illegal param',
                'code': 104000,
            }), 400

        parent_id = form.get('parent')
        book_id = form.get('bookId')
        if parent_id == '/' and book_id:
            book = db.collection('books').find_one({'_id': ObjectId(book_id)})
            if not book:
                return jsonify({
                    "message": "record not found",
                    "code": 104040,
                }), 404

            parent = {
                'path': '',
                'book_id': book_id
            }
        else:
            parent = db.collection('playbook').find_one({'_id': ObjectId(parent_id)})

        if not parent:
            return jsonify({
                "message": "parent path not found",
                "code": 104004,
            }), 400

        file = files['files']
        filename = file.filename
        path = parent['path'] + '/' + filename
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
        # exist = db.collection('playbook').find_one({'path': path})
        # if exist:
        #     db.collection('playbook').update_one({})
        #     return jsonify({
        #         "message": "ok",
        #         "code": 104005,
        #     }), 400
        db.collection('playbook').update_one({
                'path': path,
                'book_id': ObjectId(parent['book_id']),
            }, {
                '$set': record,
            }, upsert=True)

        return jsonify({
            "message": "ok",
            "code": 0,
        })

    @staticmethod
    @jwt_required
    def setup():
        wk = Workspace()
        workspace = wk.workspace
        check_workspace()
        if not os.path.exists(workspace):
            os.makedirs(workspace, 0o755)
        books = db.collection('playbook').find().sort('path', pymongo.ASCENDING)
        # books = collection_array(books)
        start = time.time()
        for item in books:
            filename = workspace + item['path']
            if item['is_dir']:
                if os.path.isdir(filename):
                    continue
                else:
                    os.makedirs(filename, 0o755)
            else:
                if os.path.isfile(filename):
                    file_hash = file_md5(filename)
                    if item.get('md5') and item['md5'] == file_hash:
                        continue
                dirname = os.path.dirname(filename)
                if not os.path.exists(dirname):
                    os.makedirs(dirname)
                if item['is_edit']:
                    db.collection('playbook').update_one({'_id': item['_id']}, {'$set': {'md5': md5(item['content'])}})
                    with open(filename, 'w+') as stream:
                        stream.write(item['content'])
                else:
                    with open(filename, 'wb') as stream:
                        db.fs_bucket().download_to_stream(item['file_id'], stream)
        end = time.time()

        return jsonify({
            "message": "ok",
            "code": 0,
            'runtime': end - start
        })

    @staticmethod
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
            records = db.collection('playbook').find({
                'path': {
                    '$regex': record['path']
                }
            })
            for doc in records:
                if doc['path'] == file_path:
                    continue
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

    @staticmethod
    @jwt_required
    def tags():
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

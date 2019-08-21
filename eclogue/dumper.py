import hashlib
import pymongo
import yaml
import os
import time
import datetime
import re

from eclogue.model import db
from eclogue.config import config
from eclogue.utils import md5
from eclogue.ansible.vault import Vault
from eclogue.lib.workspace import Workspace
from eclogue.lib.helper import get_meta


class Dumper(object):

    def __init__(self, basedir):
        self._basedir = basedir

    @staticmethod
    def load_from_dir(home_path, exclude=['*.retry'], links=False, book_name=None):
        bucket = []
        cursor = 0
        parent = home_path
        book_name = book_name or os.path.basename(home_path)
        pattern = '|'.join(exclude).replace('*', '.*?')
        for current, dirs, files in os.walk(home_path, topdown=True, followlinks=links):
            pathname = current.replace(home_path, '') or '/'
            if exclude:
                match = re.search(pattern, pathname)
                if match:
                    continue
            dir_record = {
                'book_name': book_name,
                'path': pathname,
                'is_dir': True,
                'is_edit': False,
                'seq_no': cursor,
                'parent': None,
                'created_at': int(time.time()),
            }
            if not current == home_path:
                dir_record['parent'] = parent
                meta = get_meta(pathname=pathname)
                dir_record.update(meta)
            parent = pathname
            bucket.append(dir_record)
            for file in files:
                pathname = parent.rstrip('/') + '/' + file
                if exclude:
                    match = re.match(pattern, pathname)
                    if match:
                        continue
                cursor += 1
                filename = current + '/' + file
                is_edit = Dumper.is_read(filename)
                file_record = dir_record.copy()
                file_record['is_edit'] = is_edit
                file_record['path'] = pathname
                file_record['parent'] = parent
                file_record['is_dir'] = False
                file_record['seq_no'] = cursor
                if is_edit:
                    with open(filename, 'r', encoding='utf-8') as fd:
                        file_record['content'] = fd.read()
                        file_record['md5'] = md5(file_record['content'])
                        file_record['is_encrypt'] = Vault.is_encrypted(file_record['content'])
                meta = get_meta(file_record['path'])
                file_record.update(meta)
                file_record['meta'] = meta
                bucket.append(file_record)
            cursor += 1
        return bucket

    @staticmethod
    def is_read(file):
        if not file:
            return False
        if hasattr(file, 'read'):
            demo = file.read(1024)
        else:
            demo = open(file, 'rb').read(1024)
        textchars = bytearray({7, 8, 9, 10, 12, 13, 27} | set(range(0x20, 0x100)) - {0x7f})
        is_binary = lambda bytes: bool(bytes.translate(None, textchars))
        return not is_binary(demo)

    @staticmethod
    def get_role(pathname):
        pathname = pathname.rstrip('/')
        home_path, filename = os.path.split(pathname)
        meta = {
            'name': filename
        }
        path_split = pathname.lstrip('/').split('/')
        path_len = len(path_split)
        if path_len is 1:
            filename = path_split[0] or 'root'
            if filename.find('hosts') >= 0:
                meta['role'] = 'hosts'
            elif filename.find('entry') >= 0:
                meta['role'] = 'entry'
            else:
                meta['role'] = path_split[0] or 'unknown'
        elif path_len is 2:
            meta['role'] = filename
        elif path_len >= 3:
            meta['role'] = path_split[2]
            meta['project'] = path_split[1]
        return meta

    def file_md5(self, fine_name, block_size=64 * 1024):
        with open(fine_name, 'rb') as f:
            md5hash = hashlib.md5()
            while True:
                data = f.read(block_size)
                if not data:
                    break
                md5hash.update(data)
            return md5hash.hexdigest()

    def load_book_from_db(self, name, roles=None):
        wk = Workspace()
        workspace = wk.workspace
        wk.check_workspace()
        books = db.collection('playbook').find({
            'book_name': name
        }).sort('seq_no', pymongo.ASCENDING)
        for item in books:
            if roles:
                project = item.get('name')
                if project and project not in roles:
                    continue
            filename = workspace + item['path']
            if item['is_dir']:
                if os.path.isdir(filename):
                    continue
                else:
                    os.mkdir(filename, 0o600)
            else:
                if os.path.isfile(filename):
                    file_hash = self.file_md5(filename)
                    if item.get('md5') and item['md5'] == file_hash:
                        continue
                dirname = os.path.dirname(filename)
                if not os.path.exists(dirname):
                    os.makedirs(dirname)
                if item['is_edit']:
                    db.collection('playbook').update_one({'_id': item['_id']}, {
                        '$set': {
                            'md5': md5(item['content'].encode('utf8'))
                        }
                    })
                    with open(filename, 'w') as stream:
                        stream.write(item['content'])
                else:
                    with open(filename, 'wb') as stream:
                        db.fs_bucket().download_to_stream(item['file_id'], stream)
        return books

    def check_workspace(self, path=None, child=None):
        workspace = config.workspace['playbook']
        if not os.path.exists(workspace):
            return True

        if not path:
            path = workspace
        #     filename = workspace
        # else:
        filename = path
        if child:
            filename += '/' + child
        index = filename.replace(workspace, '')
        if not index:
            index = '/'
        if os.path.isfile(filename):
            record = db.collection('playbook').find_one({'path': index})
            if not record:
                os.remove(filename)
            return True
        files = os.listdir(filename)
        for file in files:  # 遍历文件夹
            self.check_workspace(filename, file)
        return True

    def check_task(self, book_name, options):
        book = db.collection('books').find_one({'name': book_name})
        if not book:
            return False
        inventory = db.collection('playbook').find_one({
            'book_name': book_name,
            'name': options.inventory
        })
        if not inventory:
            return False
        role = db.collection('playbook').find_one({
            'book_name': book_name,
            'name': options.role,
            'role': 'roles'
        })
        if not role:
            return False
        book = self.load_book_from_db(book_name)
        bucket = []
        for key, item in book.items():
            if item['role'] is 'entry' and not item['name'] is options.entry:
                continue
            if item['role'] is 'inventory' and not item['name'] is options.inventory:
                continue
            if item['role'] is 'tasks' and item['is_edit']:
                content = []
                if options.tags or options.skip_tags:
                    tasks = yaml.load_safe(item['content'])
                    for key, task in tasks.items():
                        task_tags = task.get('tags')
                        if not task:
                            continue
                        intersection = list(set(options.tags).intersection(set(task_tags)))
                        if not intersection:
                            continue
                        intersection = list(set(options.skip_tags).intersection(set(task_tags)))
                        if intersection:
                            continue
                        content.append(task)
                    item.content = yaml.safe_dump(content)
            item.pop('_id')
            bucket.append(item)
            if item['role'] is 'vars' and options.extra_vars:
                variables = yaml.safe_load(item.content)
                variables = variables.update(options.extra_vars)
                item.content = yaml.safe_dump(variables)
        return bucket

    def get_book(self, home_path):
        book = Dumper.load_from_dir(home_path)
        collection = []
        for item in book:
            item['book_name'] = 'default'
            if item.get('path') in collection:
                db.collection('playbook').delete_one({'_id': item['_id']})
            collection.append(item.get('path'))
            if not item.get('is_edit') and not item.get('file_id') and not item.get('is_dir'):
                path_name = home_path + item['path']
                with open(path_name, mode='rb') as fd:
                    file_id = db.save_file(item['path'], fd)
                    item['file_id'] = file_id
            item['created_at'] = int(time.time())
            item['updated_at'] = datetime.datetime.now().isoformat()

import os
import yaml
import time

from uuid import uuid4
from pymongo import IndexModel, DESCENDING, ASCENDING
from jinja2 import Template
from eclogue.model import db
from eclogue.config import config
from eclogue.utils import file_md5


class Migration(object):

    def __init__(self):
        self.db = db
        self.base_dir = os.path.join(config.home_path, 'migrate')

    @property
    def template(self):
        file = os.path.join(self.base_dir, 'template.yml')
        with open(file, 'r') as f:
            return f.read()

    @property
    def data_path(self):
        return os.path.join(self.base_dir, 'data')

    def up(self):
        pass

    def down(self):
        pass

    def put(self, uuid, content):
        filename = uuid + '.yml'
        file = os.path.join(self.base_dir, 'data', filename)
        with open(file, 'w') as fd:
            fd.write(content)

    def generate(self):
        uid = str(uuid4())
        version = int(time.time())
        template = self.template
        tpl = Template(template)
        content = tpl.render(uuid=uid, version=version)
        self.put(uid, content)

    def compare(self, uuid):
        pass

    def setup(self):
        # menus = db.collection('menus').find()
        # cc = []
        # for menu in menus:
        #     menu.pop('_id')
        #     if menu.get('updated_at'):
        #         menu.pop('updated_at')
        #
        #     cc.append(menu)
        # with open(self.base_dir + '/cc.yml', 'w') as t:
        #     yaml.dump(cc, stream=t)
        #
        #
        # return False
        files = os.listdir(self.data_path)
        for file in files:
            filename = os.path.join(self.data_path, file)
            with open(filename, 'r') as fd:
                data = yaml.load(fd)
                uuid = data.get('uuid')
                if not uuid:
                    continue

                where = {'uuid': uuid}
                record = self.db.collection('migration').find_one(where)
                if record:
                    continue

                tasks = data.get('setup')
                self.handler(tasks)
                report = {
                    'uuid': uuid,
                    'template': data,
                    'md5': file_md5(filename),
                    'state': 'setup',
                    'created_at': time.time()
                }
                db.collection('migration').insert_one(report)

    def rollback(self, uuid=None, version=None):
        if not uuid and not version:
            return None

        if uuid:
            return self.rollback_one(uuid)

        if version:
            records = db.collection('migration').find({'version': version})
            for record in records:
                uuid = record.get('uuid')
                self.rollback_one(uuid)

    def rollback_one(self, uuid):
        record = db.collection('migration').find_one({'uuid': uuid})
        if not record or record.get('state') != 'setup':
            return False

        template = record.get('template')
        tasks = template.get('rollback')
        self.handler(tasks)
        update = {
            '$set': {
                'state': 'rollback',
                'update_at': time.time(),
            }
        }
        db.collection('migration').update_one({'uuid': uuid}, update=update)

    @staticmethod
    def handler(tasks):
        for task in tasks:
            if not task or task.get('collection'):
                collection = db.collection(task.get('collection'))
                insert = task.get('insert')
                update = task.get('update')
                delete = task.get('delete')
                indexes = task.get('indexes')
                if insert:
                    collection.insert_many(insert)

                if update:
                    where = update.get('filter')
                    change = update.get('change')
                    many = update.get('many')
                    kwargs = update.get('kwargs') or {}
                    if many:
                        collection.update_many(where, update=change, **kwargs)
                    else:
                        collection.update_one(where, update=change, **kwargs)

                if delete:
                    where = delete.get('filter')
                    many = delete.get('many')
                    kwargs = delete.get('kwargs') or {}
                    if many:
                        collection.delete_many(where, **kwargs)
                    else:
                        collection.delete_one(where, **kwargs)

                if indexes:
                    for item in indexes:
                        name = item.get('name')
                        keys = item.get('keys')
                        if not keys:
                            continue

                        keys = list(keys.items())
                        kwargs = item.get('kwargs') or {}
                        collection.create_index(keys, name=name, **kwargs)

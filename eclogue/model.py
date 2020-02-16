import json
import time
from pymongo import MongoClient
from bson import ObjectId
from eclogue.config import config
from gridfs import GridFS, GridFSBucket
from mimetypes import guess_type
from pymongo.cursor import Cursor
# from eclogue.middleware import login_user
from munch import Munch


class Mongo(object):

    def __init__(self, conf=None):
        self.config = conf or config.mongodb
        self.client = MongoClient(self.config.get('uri'), connect=False)
        self.db = self.client[self.config['db']]

    def get_db(self, dbname):
        return self.client[dbname]

    def collection(self, collection):
        return self.db[collection]

    def fs(self):
        return GridFS(self.db, collection='fs')

    def save_file(self, filename, fileobj, collection="fs", content_type=None, **kwargs):
        if not isinstance(collection, str):
            raise TypeError("'base' must be string or unicode")
        if not (hasattr(fileobj, "read") and callable(fileobj.read)):
            raise TypeError("'fileobj' must have read() method")

        if content_type is None:
            content_type, _ = guess_type(filename)

        storage = GridFS(self.db, collection=collection)

        return storage.put(fileobj, filename=filename, content_type=content_type, **kwargs)

    def get_file(self, _id):
        if not ObjectId.is_valid(_id):
            _id = ObjectId(_id)

        fs = self.fs()
        return fs.get(_id)

    def fs_bucket(self):
        return GridFSBucket(self.db)


class Model(object):
    name = ''
    indices = []
    definitions = {}

    def __init__(self, *args, **kwargs):
        self._attr = Munch(*args, **kwargs)
        self._change = Munch()
        self.db = db
        self._collection = self.get_collection()
        self.cursor = None

    def set_db(self, database):
        self.db = database

    @property
    def collection(self):
        return self._collection

    def get_collection(self):
        return db.collection(self.name)

    @classmethod
    def find_by_id(cls, _id):
        if not ObjectId.is_valid(_id):
            return None

        _id = ObjectId(_id)
        model = cls()

        return model.find_one({'_id': _id})

    @classmethod
    def find_by_ids(cls, ids):
        model = cls()
        ids = cls.check_ids(ids)
        where = {
            '_id': {
                '$in': ids
            }

        }
        return model.find(where)
        return model.load_result(result)

    @classmethod
    def count_documents(cls, where):
        model = cls()
        return model.collection.count(where)

    def count(self):
        return self.cursor.count()

    @classmethod
    def load_result(cls, cursor):
        if isinstance(cursor, dict):
            return cls(cursor)
        bucket = []
        items = cursor
        if isinstance(cursor, Cursor):
            items = cursor.clone()
        for item in items:
            bucket.append(cls(item))
        return bucket

    @classmethod
    def find(cls, where, *args, **kwargs):
        model = cls()
        where['status'] = {
            '$ne': -1
        }

        cursor = model.collection.find(where, *args, **kwargs)
        return cursor

    @classmethod
    def find_one(cls, where, *args, **kwargs):
        model = cls()
        where['status'] = {
            '$ne': -1
        }

        result = model.collection.find_one(where, *args, **kwargs)
        if not result:
            return None
        return model.load_result(result)

    @classmethod
    def insert_one(cls, data, *args, **kwargs):
        model = cls()
        if data.get('status') is None:
            data['status'] = 1

        result = model.collection.insert_one(data, *args, **kwargs)
        record = data.copy()
        record['_id'] = result.inserted_id
        msg = 'insert new record to {}, _id: {}'.format(model.name, record['_id'])
        extra = {
            'record': record,
        }
        model.report(msg, key=record['_id'], data=extra)

        return result

    @classmethod
    def update_one(cls, where, update, **kwargs):
        model = cls()
        _id = None
        record = model.collection.find_one(where)
        if not record and not kwargs.get('upsert'):
            return False

        msg = 'update record from {}'.format(model.name)
        if record:
            _id = record['_id']
            msg = msg + ', _id: %s' % record.get('_id')

        extra = {
            'record': record,
            'change': update,
            'filter': where,
        }

        result = model.collection.update_one(where, update, **kwargs)
        if kwargs.get('upsert'):
            _id = result.upserted_id
        model.report(msg, key=_id, data=extra)
        return result

    @classmethod
    def delete_one(cls, where, force=True, **kwargs):
        model = cls()
        record = model.collection.find_one(where)
        if not record:
            return None

        msg = 'delete record from {}, _id: {}'.format(model.name, record['_id'])
        extra = {
            'record': record,
            'filter': where,
        }
        update = {
            '$set': {
                'delete_at': time.time(),
                'status': -1,
            }
        }

        model.report(msg, key=record['_id'], data=extra)
        if not force:
            return model.collection.update_one(where, update=update, **kwargs)

        return model.collection.delete_one(where)

    @staticmethod
    def check_ids(ids):
        result = []
        for i in ids:
            if ObjectId.is_valid(i):
                result.append(ObjectId(i))

        return result

    def save(self):
        update = self._attr.copy()
        update.update(self._change.copy())
        if not update:
            return False

        if update['_id']:
            _id = update.pop('_id')
            model = self.find_by_id(_id)
            for k, v in update:
                if v == model.v:
                    update.pop(k)
            result = self.update_one({'_id': _id}, update)
            self._attr.update(dict(model))

            return result
        self.insert_one(update)

    @classmethod
    def build_model(cls, name):
        cls.name = name
        model = cls()

        return model

    def report(self, msg, key, data):
        record = {
            'msg': msg,
            'key': key,
            'data': data,
            'created_at': time.time(),

        }
        # print(record)
        # self.db.collection('action_logs').insert_one(record)

    def get(self, key, default=None):
        return self.mixins.get(key) or default

    @property
    def mixins(self):
        data = self._attr.copy()
        data.update(self._change.copy())

        return data

    def __setitem__(self, key, value):
        self._change[key] = value

    def __getitem__(self, item):
        return self.mixins.get(item)

    def __delitem__(self, key):
        if key in self._attr:
            self._attr.pop(key)
        if key in self._change:
            self._change.pop(key)

    def __iter__(self):
        return iter(self.mixins)

    def __dict__(self):
        data = self.mixins
        return data

    def __str__(self):
        data = self.mixins
        if data.get('_id'):
            data['_id'] = str(data['_id'])
        return str(data)

    def to_dict(self):
        return self.__dict__()


db = Mongo()

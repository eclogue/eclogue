import json
import time
from pymongo import MongoClient
from bson import ObjectId
from eclogue.config import config
from gridfs import GridFS, GridFSBucket
from mimetypes import guess_type
from eclogue.lib.logger import logger


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

    def __init__(self, data=None, database=None):
        self._attr = data or {}
        self.db = database or db
        self._collection = self.get_collection()

    @property
    def collection(self):
        return self._collection

    @classmethod
    def get_collection(cls):
        return db.collection(cls.name)

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

        return list(model.find(where))

    @classmethod
    def find(cls, where, *args, **kwargs):
        model = cls()
        where['status'] = {
            '$ne': -1
        }

        return model.collection.find(where, *args, **kwargs)

    @classmethod
    def find_one(cls, where, *args, **kwargs):
        model = cls()
        where['status'] = {
            '$ne': -1
        }

        return model.collection.find_one(where, *args, **kwargs)

    @classmethod
    def insert_one(cls, data, *args, **kwargs):
        model = cls()

        result = model.collection.insert_one(data, *args, **kwargs)
        record = data.copy()
        record['_id'] = result.inserted_id
        msg = 'insert new record to {}, _id: {}'.format(model.name, record['_id'])
        logger.info(msg, extra={'record': record})

        return result

    @classmethod
    def update_one(cls, where, update, **kwargs):
        model = cls()
        record = model.collection.find_one(where)
        if not record and not kwargs.get('upsert'):
            return False

        msg = 'update record from {}'.format(model.name)
        if record:
            msg = msg + ', _id: %s' % record.get('_id')

        extra = {
            'record': record,
            'change': update,
            'filter': where,
        }
        logger.info(msg, extra)

        return model.collection.update_one(where, update, **kwargs)

    @classmethod
    def delete_one(cls, where, **kwargs):
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

        logger.info(msg, extra)

        return model.collection.update_one(where, update=update, **kwargs)

    @staticmethod
    def check_ids(ids):
        result = []
        for i in ids:
            if ObjectId.is_valid(i):
                result.append(ObjectId(i))

        return result

    def save(self):
        if self._attr:
            result = self.collection.insert_one(self._attr)
            self._attr = {}

            return result

        return None

    @classmethod
    def build_model(cls, name):
        model = cls()
        model.name = name

        return model

    def __setitem__(self, key, value):
        self._attr[key] = value

    def __getitem__(self, item):
        return self._attr.get(item)

    def __delitem__(self, key):
        if key in self._attr:
            return self._attr.pop(key)

    def __iter__(self):
        return iter(self._attr)

    def __dict__(self):
        return self._attr

    def __str__(self):
        return json.dumps(self._attr)


db = Mongo()

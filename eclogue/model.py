from pymongo import MongoClient
from bson import ObjectId
from eclogue.config import config
from gridfs import GridFS, GridFSBucket
from mimetypes import guess_type


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
        fs = self.fs()
        return fs.get(_id)

    def fs_bucket(self):
        return GridFSBucket(self.db)


class Model(object):
    name = ''

    def __init__(self, data=None):
        self._attr = data
        self._collection = self.get_collection()

    @property
    def collection(self):
        return self._collection

    @classmethod
    def get_collection(cls):
        return db.collection(cls.name)

    def find_by_id(self, _id):
        if not ObjectId.is_valid(_id):
            return None
        _id = ObjectId(_id)

        return self.collection.find_one({'_id': _id})

    def find_by_ids(self, ids):
        ids = self.check_ids(ids)
        where = {
            '_id': {
                '$in': ids
            }
        }

        return list(self.collection.find(where))

    @staticmethod
    def check_ids(ids):
        result = []
        for i in ids:
            if ObjectId.is_valid(i):
                result.append(ObjectId(i))

        return result

    def save(self):
        return self.collection.insert_one(self._attr)


db = Mongo()

import uuid
import unittest
from bson import ObjectId
from pymongo.collection import Collection, Cursor
from gridfs import GridFS, GridFSBucket, GridOut
from pymongo.results import UpdateResult, InsertOneResult, DeleteResult


from eclogue.model import Model, Mongo
from eclogue.config import config
from tests.utils import get_data_set_file


class TestMongo(unittest.TestCase):

    def setUp(self):
        self.file = ''

    def test_mongo(self):
        mongo = Mongo()
        dbname = config.mongodb.get('db')
        db = mongo.get_db(dbname)
        assert db.name == dbname
        assert isinstance(mongo.collection('test'), Collection)
        assert isinstance(mongo.fs(), GridFS)
        assert isinstance(mongo.fs_bucket(), GridFSBucket)

    def test_fs(self):
        mongo = Mongo()
        file = get_data_set_file()
        with open(file, mode='rb') as fd:
            file_id = mongo.save_file('/tmp', fd)
            assert ObjectId.is_valid(file_id)
            out = mongo.get_file(file_id)
            assert isinstance(out, GridOut)
            mongo.fs().delete(file_id=file_id)


class TestModel(unittest.TestCase):

    def setUp(self):
        data = {
            'uuid': str(uuid.uuid4())
        }
        self.data = data
        self.model = Model.build_model('tests')

    def tearDown(self):
        self.model.collection.delete_many(self.data)

    def test_property(self):
        collection_name = 'tests'
        model = Model.build_model(collection_name)
        assert model.name == collection_name
        assert isinstance(model.collection, Collection)
        assert model.collection.name == collection_name
        assert isinstance(model.db, Mongo)

    def test_insert_one(self):
        result = self.model.insert_one(self.data)
        assert isinstance(result, InsertOneResult)
        assert hasattr(result, 'inserted_id')

    def test_update_one(self):
        self.test_insert_one()
        update = {
            '$set': {
                'update': 1
            }
        }
        result = self.model.update_one(self.data, update=update)
        assert isinstance(result, UpdateResult)
        result = self.model.update_one(self.data, update=update, upsert=True)
        assert hasattr(result, 'upserted_id')

    def test_find(self):
        self.test_insert_one()
        result = self.model.find(self.data)
        assert isinstance(result, Cursor)
        assert result.count() > 0

    def test_find_one(self):
        self.test_insert_one()
        result = self.model.find_one(self.data)
        assert 'uuid' in result
        assert result['uuid'] == self.data['uuid']

        return result

    def test_find_by_id(self):
        record = self.test_find_one()
        result = self.model.find_by_id(record['_id'])
        assert result['_id'] == record['_id']
        result = self.model.find_by_id(str(record['_id']))
        assert result['_id'] == record['_id']

    def test_find_by_ids(self):
        record = self.test_find_one()
        ids = [record['_id']]
        result = self.model.find_by_ids(ids)
        assert len(result) > 0
        for item in result:
            assert item['_id'] == record['_id']

    def test_delete_one(self):
        self.test_insert_one()
        result = self.model.delete_one(self.data)
        assert isinstance(result, UpdateResult)
        result = self.model.delete_one(self.data, force=True)
        assert isinstance(result, DeleteResult)



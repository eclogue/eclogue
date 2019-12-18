import os
import yaml
import json
from flask_testing import TestCase
from eclogue import create_app
from eclogue.models.user import User
from eclogue.jwt import jws


class BaseTestCase(TestCase):
    user = {}
    dataSet = {}
    token = ''
    trash = []

    def create_app(self):
        app = create_app(schedule=False)
        return app

    @staticmethod
    def read_file(filename):
        """Read file and return its contents."""
        with open(filename, 'r') as f:
            return f.read()

    def add_test_data(self, model, data):
        result = model.insert_one(data)
        self.trash += [
            (model, result.inserted_id)
        ]

    def setUp(self):
        super().setUp()
        base_dir = os.path.dirname(__file__)
        filename = os.path.join(base_dir, 'data/dataset.yaml')
        data = yaml.load(self.read_file(filename))
        self.dataSet = data
        admin = data['admin']
        User().collection.delete_one({'username': admin['username']})
        is_inserted, user_id = User().add_user(admin.copy())
        admin['_id'] = user_id
        self.user = admin
        user_info = {
            'user_id': str(admin['_id']),
            'username': admin['username'],
            'status': 1,
            'is_admin': admin.get('is_admin', True),
        }
        token = jws.encode(user_info)
        self.token = token.decode('utf-8')
        self.jwt_headers = {
            'Content-Type': 'application/json',
            'Authorization': ' '.join(['Bearer', self.token])
        }

    def authorization_header(self):
        return {
            'Authorization': 'Bearer %s' % self.token,
            'Content-Type': 'application/json',
        }

    @staticmethod
    def get_api_path(path, version='/api/v1'):
        return version + path

    @staticmethod
    def body(data):
        return json.dumps(data)

    def get_data(self, key):
        return self.dataSet.get(key)

    def get_user_token(self):
        user = self.get_data('user')
        User().collection.delete_one({'username': user['username']})
        User().add_user(user)
        user_info = {
            'user_id': str(user['_id']),
            'username': user['username'],
            'status': 1,
            'is_admin': False,
        }
        token = jws.encode(user_info)

        return token.decode('utf-8')

    def assertResponseDataHasKey(self, response, key):
        assert response.json is not None
        result = response.json
        assert 'data' in result
        data = result['data']
        self.assertEqual(key in data, True)

    def assertResponseCode(self, response, code):
        assert response.json is not None
        result = response.json
        assert 'code' in result
        self.assertEqual(result['code'], code)

    def tearDown(self):
        super().tearDown()
        while len(self.trash):
            item = self.trash.pop()
            model, pk = item
            model().collection.delete_one({'_id': pk})

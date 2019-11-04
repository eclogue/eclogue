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

    def create_app(self):
        app = create_app(schedule=False)
        return app

    @staticmethod
    def read_file(filename):
        """Read file and return its contents."""
        with open(filename, 'r') as f:
            return f.read()

    def setUp(self):
        super().setUp()
        base_dir = os.path.dirname(__file__)
        filename = os.path.join(base_dir, 'data/dataset.yaml')
        data = yaml.load(self.read_file(filename))
        self.dataSet = data
        admin = data['admin']
        User.delete_one({'username': admin['username']})
        is_inserted, user_id = User().add_user(admin)
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

import uuid
from bson import ObjectId
from tests.basecase import BaseTestCase
from unittest.mock import patch
from eclogue.models.configuration import Configuration
from eclogue.models.playbook import Playbook


class ConfigurationTest(BaseTestCase):

    def test_get_configs(self):
        admin = self.user
        record = self.get_data('configuration')
        Configuration.insert_one(record)
        self.trash += [
            [Configuration, record['_id']]
        ]
        url = self.get_api_path('/configurations')
        response = self.client.get(url, headers=self.jwt_headers)
        self.assert200(response)
        self.assertResponseCode(response, 0)
        self.assertResponseDataHasKey(response, 'list')
        self.assertResponseDataHasKey(response, 'total')
        self.assertResponseDataHasKey(response, 'page')
        self.assertResponseDataHasKey(response, 'pageSize')
        assert len(response.json['data']['list']) > 0
        query = {
            'page': 2,
            'pageSize': 1,
            'name': 'test',
            'start': '2018-11-03',
            'end': '2019-11-04',
            'status': 1
        }

        response = self.client.get(url, query_string=query, headers=self.jwt_headers)
        self.assert200(response)
        self.assertResponseCode(response, 0)
        self.assertResponseDataHasKey(response, 'list')
        self.assertResponseDataHasKey(response, 'total')
        self.assertResponseDataHasKey(response, 'page')
        self.assertResponseDataHasKey(response, 'pageSize')
        result = response.json
        data = result.get('data')
        assert data['page'] == 2
        assert data['pageSize'] == 1
        user = admin.copy()
        user['is_admin'] = False
        user['username'] = str(uuid.uuid4())

        with patch('eclogue.api.configuration.login_user', user) as mock_build:
            response = self.client.get(url, headers=self.jwt_headers)
            self.assert200(response)
            self.assertResponseCode(response, 0)
            self.assertResponseDataHasKey(response, 'list')
            self.assertResponseDataHasKey(response, 'total')
            self.assertResponseDataHasKey(response, 'page')
            self.assertResponseDataHasKey(response, 'pageSize')
            result = response.json
            data = result.get('data')
            self.assertEqual(data['list'], [])

    def test_add_configuration(self):
        data = self.get_data('configuration')
        data['name'] = str(uuid.uuid4())
        url = self.get_api_path('/configurations')
        body = self.body(data)
        response = self.client.post(url, data=self.body({}), headers=self.jwt_headers)
        self.assert400(response)
        self.assertResponseCode(response, 184000)
        clone = data.copy()
        clone.pop('name')
        response = self.client.post(url, data=self.body(clone), headers=self.jwt_headers)
        self.assert400(response)
        self.assertResponseCode(response, 184001)
        response = self.client.post(url, data=body, headers=self.jwt_headers)
        self.assert200(response)
        response = self.client.post(url, data=body, headers=self.jwt_headers)
        self.assert400(response)
        self.assertResponseCode(response, 184002)

        Configuration().collection.delete_many({'name': data['name']})

    def test_get_configs_by_ids(self):
        url = self.get_api_path('/configurations/list/ids')
        record = self.get_data('configuration')
        record['name'] = str(uuid.uuid4())
        Configuration.insert_one(record)
        self.trash += [
            [Configuration, record['_id']]
        ]
        response = self.client.get(url, headers=self.jwt_headers)
        self.assert400(response)
        self.assertResponseCode(response, 184000)
        query = {
            'ids': ','.join([str(record['_id']), str(record['_id'])])
        }
        response = self.client.get(url, query_string=query, headers=self.jwt_headers)
        self.assert200(response)
        result = response.json
        records = result.get('data')
        self.assertEqual(len(records), 1)
        Configuration().collection.delete_one({'_id': record['_id']})

    def test_get_register_config(self):
        playbook = self.get_data('playbook')
        configuration = self.get_data('configuration')
        configuration['name'] = str(uuid.uuid4())
        Configuration.insert_one(configuration)

        playbook['register'] = [str(configuration['_id'])]
        Playbook.insert_one(playbook)
        self.trash += [
            [Configuration, configuration['_id']],
            [Playbook, playbook['_id']],
        ]
        path = '/configurations/%s/register' % str(ObjectId())
        url = self.get_api_path(path)
        response = self.client.get(url, headers=self.jwt_headers)
        self.assert404(response)
        self.assertResponseCode(response, 104040)
        path = '/configurations/%s/register' % str(playbook['_id'])
        url = self.get_api_path(path)
        response = self.client.get(url, headers=self.jwt_headers)
        self.assert200(response)

    def test_delete_configuration(self):
        configuration = self.get_data('configuration')
        playbook = self.get_data('playbook')
        configuration['name'] = str(uuid.uuid4())
        Configuration.insert_one(configuration)
        playbook['register'] = [str(configuration['_id'])]
        Playbook.insert_one(playbook)
        self.trash += [
            [Configuration, configuration['_id']],
            [Playbook, playbook['_id']],
        ]
        path = '/configurations/%s' % str(ObjectId())
        url = self.get_api_path(path)
        response = self.client.delete(url, headers=self.jwt_headers)
        self.assert404(response)
        self.assertResponseCode(response, 104040)
        path = '/configurations/%s' % str(configuration['_id'])
        url = self.get_api_path(path)
        response = self.client.delete(url, headers=self.jwt_headers)
        self.assert403(response)
        self.assertResponseCode(response, 104038)
        Playbook().collection.delete_one({'_id': playbook['_id']})
        path = '/configurations/%s' % str(configuration['_id'])
        url = self.get_api_path(path)
        response = self.client.delete(url, headers=self.jwt_headers)
        self.assert200(response)
        Configuration().collection.delete_one({'_id': configuration['_id']})

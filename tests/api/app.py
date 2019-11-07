import uuid
from bson import ObjectId
from tests.basecase import BaseTestCase
from unittest.mock import patch
from eclogue.models.application import Application


class AppTest(BaseTestCase):

    def test_get_apps(self):
        url = self.get_api_path('/apps')
        response = self.client.get(url, headers=self.jwt_headers)
        self.assert200(response)
        self.assertResponseCode(response, 0)
        self.assertResponseDataHasKey(response, 'list')
        self.assertResponseDataHasKey(response, 'total')
        self.assertResponseDataHasKey(response, 'page')
        self.assertResponseDataHasKey(response, 'pageSize')
        query = {
            'page': 2,
            'pageSize': 1,
            'keyword': 'test',
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

    def test_add_app(self):
        data = self.get_data('application')
        data['name'] = str(uuid.uuid4())
        url = self.get_api_path('/apps')
        body = self.body(data)
        response = self.client.post(url, data=self.body({}), headers=self.jwt_headers)
        self.assert400(response)
        self.assertResponseCode(response, 174000)
        with patch('eclogue.api.app.Integration') as mockClass:
            instance = mockClass.return_value
            instance.check_app_params.return_value = False
            response = self.client.post(url, data=body, headers=self.jwt_headers)
            self.assert400(response)
            self.assertResponseCode(response, 174003)
            instance.check_app_params.return_value = True
            clone = data.copy()
            clone.pop('name')
            response = self.client.post(url, data=self.body(clone), headers=self.jwt_headers)
            self.assert400(response)
            self.assertResponseCode(response, 174001)
            response = self.client.post(url, data=body, headers=self.jwt_headers)
            self.assert200(response)
            response = self.client.post(url, data=body, headers=self.jwt_headers)
            self.assert400(response)
            self.assertResponseCode(response, 174002)

        Application().collection.delete_many({'name': data['name']})

    def test_update_app(self):
        data = self.get_data('application')
        data['name'] = str(uuid.uuid4())
        result = Application.insert_one(data.copy())
        app_id = result.inserted_id
        with patch('eclogue.api.app.Integration') as mockClass:
            instance = mockClass.return_value
            instance.check_app_params.return_value = False
            url = self.get_api_path('/apps/' + str(app_id))
            response = self.client.put(url, data=self.body(data), headers=self.jwt_headers)
            self.assert400(response)
            self.assertResponseCode(response, 174003)
            instance.check_app_params.return_value = True
            response = self.client.put(url, data=self.body({}), headers=self.jwt_headers)
            self.assert400(response)
            self.assertResponseCode(response, 174000)
            invalid_url = self.get_api_path('/apps/' + str(ObjectId()))
            response = self.client.put(invalid_url, data=self.body(data), headers=self.jwt_headers)
            self.assert404(response)
            self.assertResponseCode(response, 104040)
            response = self.client.put(url, data=self.body(data), headers=self.jwt_headers)
            self.assert200(response)

        Application().collection.delete_one({'_id': app_id})


from bson import ObjectId
from tests.basecase import BaseTestCase
from unittest import mock
from eclogue.models.application import Application
from eclogue.lib.integration import Integration



class AppTest(BaseTestCase):

    def test_dashboard(self):
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
        url = self.get_api_path('/apps')
        body = self.body(data)
        response = self.client.post(url, data=self.body({}), headers=self.jwt_headers)
        self.assert400(response)
        self.assertResponseCode(response, 174000)
        with mock.patch('eclogue.lib.integration.Integration', app_type='test', app_params={}) as mock_instance:
            mock_ret = mock_instance.return_value
            mock_ret.check_app_params.return_value = False
            print(Integration('test', {}) is mock_ret)

            # response = self.client.post(url, data=body, headers=self.jwt_headers)
            # print('mmmmmmmcok', response.json)
        # self.assert200(response)
        Application.delete_one({'name': data['name']})


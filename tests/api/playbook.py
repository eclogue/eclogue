import uuid
from bson import ObjectId
from tests.basecase import BaseTestCase
from unittest.mock import patch
from eclogue.models.book import Book
from eclogue.models.playbook import Playbook


class PlaybookTest(BaseTestCase):

    def test_add_file(self):
        pass
        # data = self.get_data('book')
        # data['name'] = str(uuid.uuid4())
        # url = self.get_api_path('/books')
        # response = self.client.post(url, data="{}", headers=self.jwt_headers)
        # self.assert400(response)
        # self.assertResponseCode(response, 154000)
        # clone = data.copy()
        # clone.pop('name')
        # response = self.client.post(url, data=self.body(clone), headers=self.jwt_headers)
        # self.assert400(response)
        # self.assertResponseCode(response, 154001)
        # clone = data.copy()
        # clone['_id'] = str(ObjectId())
        # response = self.client.post(url, data=self.body(clone), headers=self.jwt_headers)
        # self.assert404(response)
        # self.assertResponseCode(response, 154041)
        # with patch('eclogue.api.book.AnsibleGalaxy') as mock_build:
        #     clone = data.copy()
        #     clone['importType'] = 'galaxy'
        #     response = self.client.post(url, data=self.body(clone), headers=self.jwt_headers)
        #     params = [data.get('galaxyRepo')]
        #     mock_build.assert_called_with(params)
        #     self.assert200(response)
        #     self.assertResponseDataHasKey(response, '_id')
        #     result = response.json.get('data')
        #     self.assertEqual(result['name'], clone.get('name'))
        #     Book().collection.delete_one({'_id': ObjectId(result['_id'])})




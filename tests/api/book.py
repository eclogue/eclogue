import uuid
from bson import ObjectId
from tests.basecase import BaseTestCase
from unittest.mock import patch
from eclogue.models.book import Book
from eclogue.models.playbook import Playbook


class BookTest(BaseTestCase):

    def test_add_book(self):
        data = self.get_data('book')
        data['name'] = str(uuid.uuid4())
        url = self.get_api_path('/books')
        response = self.client.post(url, data="{}", headers=self.jwt_headers)
        self.assert400(response)
        self.assertResponseCode(response, 154000)
        clone = data.copy()
        clone.pop('name')
        response = self.client.post(url, data=self.body(clone), headers=self.jwt_headers)
        self.assert400(response)
        self.assertResponseCode(response, 154001)
        clone = data.copy()
        clone['_id'] = str(ObjectId())
        response = self.client.post(url, data=self.body(clone), headers=self.jwt_headers)
        self.assert404(response)
        self.assertResponseCode(response, 154041)
        with patch('eclogue.api.book.AnsibleGalaxy') as mock_build:
            clone = data.copy()
            clone['importType'] = 'galaxy'
            response = self.client.post(url, data=self.body(clone), headers=self.jwt_headers)
            params = [data.get('galaxyRepo')]
            mock_build.assert_called_with(params)
            self.assert200(response)
            self.assertResponseDataHasKey(response, '_id')
            result = response.json.get('data')
            self.assertEqual(result['name'], clone.get('name'))
            Book().collection.delete_one({'_id': ObjectId(result['_id'])})

    def test_get_books(self):
        url = self.get_api_path('/books')
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

    def test_update_book(self):
        data = self.get_data('book')
        data['name'] = str(uuid.uuid4())
        result = Book.insert_one(data.copy())
        book_id = result.inserted_id
        url = self.get_api_path('/books/' + str(book_id))
        response = self.client.put(url, data=self.body({}), headers=self.jwt_headers)
        self.assert400(response)
        self.assertResponseCode(response, 154000)
        not_found_url = self.get_api_path('/books/' + str(ObjectId()))
        body = self.body(data)
        response = self.client.put(not_found_url, data=body, headers=self.jwt_headers)
        self.assert404(response)
        self.assertResponseCode(response, 154041)

        with patch('eclogue.api.book.AnsibleGalaxy') as mock_build:
            clone = data.copy()
            clone['importType'] = 'galaxy'
            clone['status'] = 0
            response = self.client.put(url, data=self.body(clone), headers=self.jwt_headers)
            params = [data.get('galaxyRepo')]
            mock_build.assert_called_with(params, {'force': True})
            self.assert200(response)
        Book().collection.delete_one({'_id': book_id})

    def test_book_detail(self):
        data = self.get_data('book')
        data['name'] = str(uuid.uuid4())
        result = Book.insert_one(data)
        book_id = result.inserted_id
        url = self.get_api_path('/books/' + str(ObjectId()))
        response = self.client.get(url, headers=self.jwt_headers)
        self.assert400(response)
        self.assertResponseCode(response, 154041)
        url = self.get_api_path('/books/' + str(book_id))
        response = self.client.get(url, headers=self.jwt_headers)
        self.assert200(response)
        Book().collection.delete_one({'_id': book_id})

    def test_delete_book(self):
        data = self.get_data('book')
        playbook = self.get_data('playbook')
        data['name'] = str(uuid.uuid4())
        result = Book.insert_one(data.copy())
        book_id = result.inserted_id
        playbook['book_id'] = str(book_id)
        Playbook.insert_one(playbook)
        url = self.get_api_path('/books/' + str(book_id))
        not_found_url = self.get_api_path('/books/' + str(ObjectId()))
        response = self.client.delete(not_found_url, headers=self.jwt_headers)
        self.assert404(response)
        self.assertResponseCode(response, 154041)
        response = self.client.delete(url, headers=self.jwt_headers)
        self.assert200(response)
        record = Book.find_by_id(book_id)
        self.assertEqual(record, None)
        record = Book().collection.find_one({'_id': book_id})
        self.assertIsNotNone(record)
        self.assertEqual(record['_id'], book_id)
        self.assertEqual(record['status'], -1)
        playbook_record = Playbook().collection.find_one({'_id': playbook['_id']})
        self.assertIsNotNone(playbook_record)
        self.assertEqual(playbook_record['status'], -1)
        Playbook().collection.delete_one({'_id': playbook['_id']})
        Book().collection.delete_one({'_id': book_id})




import uuid
from io import BytesIO
from bson import ObjectId
from tests.basecase import BaseTestCase
from unittest.mock import patch
from eclogue.models.book import Book
from eclogue.models.playbook import Playbook
from eclogue.model import db


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
        self.trash += [
            [Book, book_id],
        ]
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

    def test_book_detail(self):
        data = self.get_data('book')
        data['name'] = str(uuid.uuid4())
        result = Book.insert_one(data)
        book_id = result.inserted_id
        self.trash += [
            [Book, book_id],
        ]
        url = self.get_api_path('/books/' + str(ObjectId()))
        response = self.client.get(url, headers=self.jwt_headers)
        self.assert400(response)
        self.assertResponseCode(response, 154041)
        url = self.get_api_path('/books/' + str(book_id))
        response = self.client.get(url, headers=self.jwt_headers)
        self.assert200(response)

    def test_delete_book(self):
        data = self.get_data('book')
        playbook = self.get_data('playbook')
        data['name'] = str(uuid.uuid4())
        result = Book.insert_one(data.copy())
        book_id = result.inserted_id
        playbook['book_id'] = str(book_id)
        Playbook.insert_one(playbook)
        self.trash += [
            [Book, book_id],
            [Playbook, playbook['_id']],
        ]
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

    def test_get_playbook(self):
        data = self.get_data('book')
        playbook = self.get_data('playbook')
        data['name'] = str(uuid.uuid4())
        result = Book.insert_one(data.copy())
        book_id = result.inserted_id
        playbook['book_id'] = str(book_id)
        Playbook.insert_one(playbook)
        self.trash += [
            [Book, book_id],
            [Playbook, playbook['_id']],
        ]
        url = self.get_api_path('/books/%s/playbook' % str(ObjectId()))
        query = {
            'current': str(playbook['_id'])
        }
        response = self.client.get(url, query_string=query, headers=self.jwt_headers)
        self.assert400(response)
        self.assertResponseCode(response, 154001)
        url = self.get_api_path('/books/%s/playbook' % playbook['book_id'])
        Book.update_one({'_id': book_id}, {'$set': {'status': -1}})
        response = self.client.get(url, query_string=query, headers=self.jwt_headers)
        self.assert400(response)
        self.assertResponseCode(response, 154001)
        Book.update_one({'_id': book_id}, {'$set': {'status': 1}})
        url = self.get_api_path('/books/%s/playbook' % playbook['book_id'])
        response = self.client.get(url, query_string=query, headers=self.jwt_headers)
        self.assert200(response)
        result = response.json
        data = result.get('data')
        check = map(lambda i: str(i['_id']), data)
        check = list(check)
        assert str(playbook['_id']) in check

    def test_download(self):
        url = self.get_api_path('/books/%s/download' % str(ObjectId()))
        response = self.client.get(url, headers=self.jwt_headers)
        self.assert404(response)
        self.assertResponseCode(response, 104040)
        data = self.get_data('book')
        playbook = self.get_data('playbook')
        data['name'] = str(uuid.uuid4())
        result = Book.insert_one(data.copy())
        book_id = result.inserted_id
        playbook['book_id'] = str(book_id)
        Playbook.insert_one(playbook)
        playbook_file = self.get_data('playbook_file')
        playbook_file['book_id'] = playbook['book_id']
        Playbook.insert_one(playbook_file)
        self.trash += [
            [Book, book_id],
            [Playbook, playbook['_id']],
            [Playbook, playbook_file['_id']]
        ]
        url = self.get_api_path('/books/%s/download' % str(book_id))
        response = self.client.get(url, headers=self.jwt_headers)
        # Playbook().collection.delete_one({'_id': playbook['_id']})
        # Book().collection.delete_one({'_id': book_id})
        self.assert200(response)
        headers = response.headers
        self.assertEqual(headers['Content-Type'], 'application/zip')
        assert len(response.get_data()) > 0
        response.close()

    def test_upload(self):
        url = self.get_api_path('/books/%s/playbook' % str(ObjectId()))
        response = self.client.post(url, headers=self.jwt_headers)
        self.assert400(response)
        self.assertResponseCode(response, 104004)
        data = self.get_data('book')
        data['name'] = str(uuid.uuid4())
        result = Book.insert_one(data.copy())
        book_id = result.inserted_id
        self.trash += [
            [Book, book_id],
        ]
        url = self.get_api_path('/books/%s/playbook' % str(book_id))
        response = self.client.post(url, headers=self.jwt_headers)
        self.assert400(response)
        self.assertResponseCode(response, 104001)
        headers = self.jwt_headers.copy()
        headers.update({'Content-Type': 'multipart/form-data'})
        stream = BytesIO(bytes('mock test', 'utf-8'))
        params = {'file': (stream, 'test.yaml')}
        response = self.client.post(url, data=params, headers=headers, content_type='multipart/form-data')
        self.assert200(response)
        record = Playbook.find_one({'book_id': str(book_id)})
        assert record is not None
        db.fs().delete(record.get('file_id'))
        with patch('eclogue.api.book.is_edit') as build_mock:
            build_mock.return_value = False
            stream = BytesIO(bytes('mock test', 'utf-8'))
            params = {'file': (stream, 'binary.mock')}
            response = self.client.post(url, data=params, headers=headers, content_type='multipart/form-data')
            self.assert200(response)
            record = Playbook.find_one({'book_id': str(book_id), 'file_id': {'$exists': True}})
            assert record is not None
            db.fs().delete(record.get('file_id'))

        Playbook().collection.delete_many({'book_id': str(book_id)})

    def test_get_entries(self):
        pass


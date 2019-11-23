import uuid
import json
from bson import ObjectId
from tests.basecase import BaseTestCase
from unittest.mock import patch
from eclogue.models.book import Book
from eclogue.models.playbook import Playbook


class PlaybookTest(BaseTestCase):

    def test_get_playbook(self):
        book = self.get_data('book')
        playbook = self.get_data('playbook')
        result = Book.insert_one(book.copy())
        book_id = result.inserted_id
        playbook['book_id'] = str(book_id)
        Playbook.insert_one(playbook)
        self.trash += [
            [Book, book_id],
            [Playbook, playbook['_id']]
        ]
        url = self.get_api_path('/books/%s/playbook' % str(ObjectId()))
        response = self.client.get(url, headers=self.jwt_headers)
        self.assert400(response)
        self.assertResponseCode(response, 154001)
        Book.update_one({'_id': book_id}, {'$set': {'status': -1}})
        url = self.get_api_path('/books/%s/playbook' % str(book_id))
        response = self.client.get(url, headers=self.jwt_headers)
        self.assert400(response)
        self.assertResponseCode(response, 154001)
        Book.update_one({'_id': book_id}, {'$set': {'status': 1}})
        url = self.get_api_path('/books/%s/playbook' % str(book_id))
        response = self.client.get(url, headers=self.jwt_headers)
        self.assert200(response)

    def test_get_tags(self):
        params = {
            'template': {
                'listtags': True,
                'listtasks': True,
            }
        }

        url = self.get_api_path('/playbook/tags')
        response = self.client.post(url, data=self.body({}), headers=self.jwt_headers)
        self.assert400(response)
        self.assertResponseCode(response, 104000)
        with patch('eclogue.api.playbook.load_ansible_playbook') as stub:
            stub.return_value = {
                'message': 'error',
                'code': 12345,
            }

            response = self.client.post(url, data=self.body(params), headers=self.jwt_headers)
            self.assert400(response)
            self.assertResponseCode(response, 12345)
            parsed_template = {
                    'inventory': 'local',
                    'options': {},
                    'name': 'name',
                    'entry': 'entry',
                    'book_id': '',
                    'book_name': 'book_name',
                    'roles': ['role'],
                    'inventory_type': 'file',
                    'private_key': None,
                    'template': {},
                    'extra': {},
                    'status': 1,
                }
            stub.return_value = {
                'message': 'ok',
                'data': parsed_template,
            }

            with patch('eclogue.api.playbook.Workspace') as mock_build:
                instance = mock_build.return_value
                instance.load_book_from_db.return_value = False
                response = self.client.post(url, data=self.body(params), headers=self.jwt_headers)
                self.assert400(response)
                self.assertResponseCode(response, 104000)
                instance.load_book_from_db.return_value = True
                with patch('eclogue.api.playbook.PlayBookRunner') as mock_playbook_runner:
                    data = parsed_template
                    runner = mock_playbook_runner.return_value
                    response = self.client.post(url, data=self.body(params), headers=self.jwt_headers)
                    runner.run.assert_called()
                    mock_playbook_runner.assert_called_with([data['inventory']], data['options'])
                    self.assert200(response)

    def test_edit_file(self):
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

        path = '/playbook/%s/file'
        url = self.get_api_path(path % str(ObjectId()))
        response = self.client.put(url, data=self.body({}), headers=self.jwt_headers)
        self.assert400(response)
        self.assertResponseCode(response, 154000)
        url = self.get_api_path(path % str(ObjectId()))
        params = playbook.copy()
        params.pop('_id')
        register_id = str(ObjectId())
        update = {
            'description': 'big jet plane',
            'is_edit': False,
            'register': [register_id]
        }
        params.update(update)
        response = self.client.put(url, data=self.body(params), headers=self.jwt_headers)
        self.assert404(response)
        url = self.get_api_path(path % str(playbook['_id']))
        with patch('eclogue.api.playbook.Configuration') as config_mock:
            # instance = build_mock.return_value
            config_mock.find.return_value = None
            # instance.find.return_value = {'_id': ObjectId()}
            response = self.client.put(url, data=self.body(params), headers=self.jwt_headers)
            print(response.json)
            self.assert404(response)
            self.assertResponseCode(response, 154042)
            config_mock.find.return_value = {'_id': register_id}
            with patch('eclogue.api.playbook.Workspace') as wk_mock:
                response = self.client.put(url, data=self.body(params), headers=self.jwt_headers)
                self.assert200(response)
                wk_mock.assert_called()
                wk_mock.return_value.write_book_file.assert_called()


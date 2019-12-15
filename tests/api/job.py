import uuid
import os
from bson import ObjectId
import unittest
from tests.basecase import BaseTestCase
from unittest.mock import patch
from eclogue.models.book import Book
from eclogue.models.playbook import Playbook
from eclogue.model import db


class JobTest(BaseTestCase):

    @patch('eclogue.api.job.PlayBookRunner')
    @patch('eclogue.api.job.get_credential_content_by_id')
    @patch('eclogue.api.job.Workspace')
    @patch('eclogue.api.job.load_ansible_playbook')
    def test_add_job(self, load_ansible_playbook, workspace, key_mock, runner):
        data = self.get_data('playbook_job')
        data['name'] = str(uuid.uuid4())
        url = self.get_api_path('/jobs')
        response = self.client.post(url, data='{}', headers=self.jwt_headers)
        self.assert400(response)
        self.assertResponseCode(response, 104000)
        params = data.copy()
        params['type'] = 'playbook'
        payload = self.body(params)
        load_ansible_playbook.return_value = {
            'message': 'test',
            'code': 123
        }
        response = self.client.post(url, data=payload, headers=self.jwt_headers)
        self.assert400(response)
        self.assertResponseCode(response, 123)
        options = {}
        ansible_payload = {
            'message': 'ok',
            'code': 0,
            'data': {
                'inventory': options.get('inventory'),
                'options': options,
                'name': data.get('name'),
                'entry': data['entry'],
                'book_id': data.get('book_id'),
                'book_name': 'test',
                'roles': ['test'],
                'inventory_type': 'cmdb',
                'private_key': True,
                'template': {},
                'extra': {},
                'status': 1,
            }
        }

        load_ansible_playbook.return_value = ansible_payload
        instance = workspace.return_value
        instance.load_book_from_db.return_value = False
        response = self.client.post(url, data=payload, headers=self.jwt_headers)
        self.assert400(response)
        self.assertResponseCode(response, 104000)
        instance.load_book_from_db.return_value = True
        instance.get_book_entry.return_value = '/dev/null'
        params['check'] = True
        params['private_key'] = True
        payload = self.body(params)
        key_mock.return_value = 'test_private_key'
        instance = runner.return_value
        instance.get_result.return_value = 'fuck'
        response = self.client.post(url, data=payload, headers=self.jwt_headers)
        self.assert200(response)
        params['check'] = False
        payload = self.body(params)
        instance.get_result.return_value = 'fuck'
        response = self.client.post(url, data=payload, headers=self.jwt_headers)
        self.assert200(response)
        response = self.client.post(url, data=payload, headers=self.jwt_headers)
        self.assert400(response)
        self.assertResponseCode(response, 104001)
        Playbook().collection.delete_one({'name': data['name']})





import uuid
import os
from bson import ObjectId
import unittest
from tests.basecase import BaseTestCase
from unittest.mock import patch
from eclogue.models.job import Job
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
        Job().collection.delete_one({'name': data['name']})

    @patch('eclogue.api.job.AdHocRunner')
    @patch('eclogue.api.job.get_credential_content_by_id')
    @patch('eclogue.api.job.parse_cmdb_inventory')
    def test_add_adhoc_job(self, parse_cmdb_inventory, get_credential_content_by_id,
                           adhoc_runner):
        data = self.get_data('adhoc_job')
        data['name'] = str(uuid.uuid4())
        url = self.get_api_path('/jobs')
        response = self.client.post(url, data='{}', headers=self.jwt_headers)
        self.assert400(response)
        self.assertResponseCode(response, 104000)
        params = data.copy()
        # None module params should response 400
        params['module'] = None
        params['type'] = 'adhoc'
        current_user = self.user
        params['maintainer'] = [current_user.get('username')]
        payload = self.body(params)
        response = self.client.post(url, data=payload, headers=self.jwt_headers)
        self.assert400(response)
        self.assertResponseCode(response, 104002)
        # test parse_cmdb_inventory return None
        parse_cmdb_inventory.return_value = None
        params['module'] = 'ls'
        payload = self.body(params)
        response = self.client.post(url, data=payload, headers=self.jwt_headers)
        self.assert400(response)
        self.assertResponseCode(response, 104004)

        # test with check and no private_key condition
        params['check'] = True
        params['private_key'] = None
        parse_cmdb_inventory.return_value = 'localhost'
        runner_instance = adhoc_runner.return_value
        runner_instance.get_result.return_value = data['name']
        payload = self.body(params)
        response = self.client.post(url, data=payload, headers=self.jwt_headers)
        self.assert200(response)
        runner_instance.run.assert_called()
        # test run with private_key
        params['private_key'] = True
        get_credential_content_by_id.return_value = None
        payload = self.body(params)
        response = self.client.post(url, data=payload, headers=self.jwt_headers)
        self.assert400(response)
        self.assertResponseCode(response, 104004)
        # assume get private_key return correct
        get_credential_content_by_id.return_value = 'test-private'
        response = self.client.post(url, data=payload, headers=self.jwt_headers)
        self.assert200(response)
        runner_instance.run.assert_called()
        params['check'] = False
        payload = self.body(params)
        response = self.client.post(url, data=payload, headers=self.jwt_headers)
        self.assert200(response)
        runner_instance.run.assert_called()
        response = self.client.post(url, data=payload, headers=self.jwt_headers)
        self.assert400(response)
        record = Job.find_one({'name': data['name']})
        assert record
        assert record.get('name') == data.get('name')
        params['job_id'] = str(ObjectId())
        payload = self.body(params)
        response = self.client.post(url, data=payload, headers=self.jwt_headers)
        self.assert404(response)
        self.assertResponseCode(response, 104040)
        params['job_id'] = str(record.get('_id'))
        payload = self.body(params)
        response = self.client.post(url, data=payload, headers=self.jwt_headers)
        self.assert200(response)
        Job().collection.delete_one({'name': data['name']})

    @patch('eclogue.api.job.parse_cmdb_inventory')
    @patch('eclogue.api.job.parse_file_inventory')
    @patch('eclogue.api.job.check_playbook')
    def test_get_job(self, check_book, parse_file_inventory, parse_cmdb_inventory):
        data = self.get_data('playbook_job')
        data['name'] = str(uuid.uuid4())
        data['status'] = 1
        url = self.get_api_path('/jobs/%s' % str(ObjectId()))
        response = self.client.get(url, headers=self.jwt_headers)
        self.assert400(response)
        self.assertResponseCode(response, 154001)
        result = self.add_test_data(Job, data)
        url = self.get_api_path('/jobs/%s' % str(result.inserted_id))
        response = self.client.get(url, headers=self.jwt_headers)
        self.assert400(response)
        Job.update_one({'_id': result.inserted_id}, {
            '$set': {
                'maintainer': [self.user.get('username')],
                'book_id': str(ObjectId())
            }
        })
        parse_cmdb_inventory.return_value = ''
        parse_file_inventory.return_value = ''
        response = self.client.get(url, headers=self.jwt_headers)
        parse_file_inventory.assert_called()
        self.assert200(response)
        self.assertResponseDataHasKey(response, 'logs')
        self.assertResponseDataHasKey(response, 'previewContent')
        self.assertResponseDataHasKey(response, 'record')
        self.assertResponseDataHasKey(response, 'roles')
        data = self.get_data('adhoc_job')
        data['maintainer'] = [self.user.get('username')]
        data['template'] = {
            'inventory_type': 'adhoc',
            'inventory': 'localhost'
        }
        result = self.add_test_data(Job, data)
        url = self.get_api_path('/jobs/%s' % str(result.inserted_id))
        response = self.client.get(url, headers=self.jwt_headers)
        parse_cmdb_inventory.assert_called()
        self.assertResponseDataHasKey(response, 'logs')
        self.assertResponseDataHasKey(response, 'previewContent')
        self.assertResponseDataHasKey(response, 'record')









from bson import ObjectId
from tests.basecase import BaseTestCase
from unittest.mock import patch


class ConsoleTest(BaseTestCase):

    def test_run_task(self):
        url = self.get_api_path('/execute')
        response = self.client.post(url, data='{}', headers=self.jwt_headers)
        self.assert400(response)
        self.assertResponseCode(response, 114000)
        key_content = 'tests content'
        return_result = {
            'failed': {},
            'success': {
                'local': 'mulberry10 | CHANGED | rc=0 >\ntest\n'
            },
            'unreachable': {}
        }
        with patch('eclogue.api.console.parse_cmdb_inventory') as mock_build:
            mock_build.return_value = False
            payload = self.get_data('console_adhoc')
            body = self.body(payload)
            response = self.client.post(url, data=body, headers=self.jwt_headers)
            self.assert400(response)
            self.assertResponseCode(response, 114001)
            mock_build.return_value = {
                'local': {
                    'hosts': {
                        'mulberry10': {
                            'ansible_ssh_host': 'localhost', 'ansible_ssh_user': 'bugbear',
                            'ansible_ssh_port': 22
                        }
                    }
                }
            }

            params = payload.copy()
            params.pop('module')
            body = self.body(params)
            response = self.client.post(url, data=body, headers=self.jwt_headers)
            self.assert400(response)
            self.assertResponseCode(response, 114002)
            with patch('eclogue.api.console.get_credential_content_by_id') as credential_mock:
                credential_mock.return_value = None
                params = payload.copy()
                params['private_key'] = str(ObjectId())
                response = self.client.post(url, data=self.body(params), headers=self.jwt_headers)
                self.assert401(response)
                self.assertResponseCode(response, 104033)
                credential_mock.return_value = key_content
                # test adhoc
                with patch('eclogue.api.console.AdHocRunner') as mock_adhoc:
                    instance = mock_adhoc.return_value
                    tasks = [{
                        'action': {
                            'module': payload.get('module'),
                            'args': payload.get('args'),
                        }
                    }]

                    instance.format_result.return_value = return_result

                    response = self.client.post(url, data=self.body(payload), headers=self.jwt_headers)
                    instance.run.assert_called_with('all', tasks)
                    self.assert200(response)
                    self.assertResponseDataHasKey(response, 'success')
                    self.assertResponseDataHasKey(response, 'failed')
                    self.assertResponseDataHasKey(response, 'unreachable')
                    params = payload.copy()
                    params['private_key'] = str(ObjectId())
                    response = self.client.post(url, data=self.body(params), headers=self.jwt_headers)
                    instance.run.assert_called_with('all', tasks)
                    self.assert200(response)

                # test playbook
                with patch('eclogue.api.console.PlayBookRunner') as playbook_mock:
                    payload = self.get_data('console_playbook')
                    params = payload.copy()
                    params.pop('entry')
                    response = self.client.post(url, data=self.body(params), headers=self.jwt_headers)
                    self.assert400(response)
                    self.assertResponseCode(response, 114004)
                    credential_mock.return_value = None
                    params = payload.copy()
                    params['private_key'] = str(ObjectId())
                    response = self.client.post(url, data=self.body(params), headers=self.jwt_headers)
                    self.assert401(response)
                    self.assertResponseCode(response, 104033)
                    credential_mock.return_value = key_content
                    params = payload.copy()
                    params['private_key'] = str(ObjectId())
                    instance = playbook_mock.return_value
                    instance.format_result.return_value = return_result
                    response = self.client.post(url, data=self.body(payload), headers=self.jwt_headers)
                    instance.run.assert_called_once()
                    self.assert200(response)
                    self.assertResponseDataHasKey(response, 'success')
                    self.assertResponseDataHasKey(response, 'failed')
                    self.assertResponseDataHasKey(response, 'unreachable')
                    params['private_key'] = None
                    response = self.client.post(url, data=self.body(payload), headers=self.jwt_headers)
                    self.assert200(response)

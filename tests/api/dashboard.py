from tests.basecase import BaseTestCase


class DashboardTest(BaseTestCase):

    def test_dashboard(self):
        url = self.get_api_path('/dashboard')
        response = self.client.get(url, headers=self.jwt_headers)
        self.assert200(response)
        self.assertResponseCode(response, 0)
        self.assertResponseDataHasKey(response, 'apps')
        self.assertResponseDataHasKey(response, 'hosts')
        self.assertResponseDataHasKey(response, 'jobs')
        self.assertResponseDataHasKey(response, 'taskPies')
        self.assertResponseDataHasKey(response, 'taskHistogram')
        self.assertResponseDataHasKey(response, 'playbooks')
        self.assertResponseDataHasKey(response, 'config')
        self.assertResponseDataHasKey(response, 'jobDuration')
        self.assertResponseDataHasKey(response, 'jobRunPies')



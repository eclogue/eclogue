from tests.basecase import BaseTestCase


class AuthTest(BaseTestCase):

    def test_login(self):
        user = self.user
        payload = {
            'username': user['username'],
            'password': str(user['password']),
        }
        headers = {
            'Content-Type': 'application/json',
        }
        url = self.get_api_path('/login')
        response = self.client.post(url, data='{}', headers=headers)
        self.assert400(response)
        self.assertResponseCode(response, 104000)
        # test 104001
        temp = payload.copy()
        temp['username'] = None
        response = self.client.post(url, data=self.body(temp), headers=headers)
        self.assert400(response)
        self.assertResponseCode(response, 104001)

        # test user not found
        temp = payload.copy()
        temp['username'] = 'some_user'
        response = self.client.post(url, data=self.body(temp), headers=headers)
        self.assert400(response)
        self.assertResponseCode(response, 104002)

        # test password incorrect
        temp = payload.copy()
        temp['password'] = 'some_password'
        response = self.client.post(url, data=self.body(temp), headers=headers)
        self.assert401(response)
        self.assertResponseCode(response, 104003)

        # test success
        body = self.body(payload)
        response = self.client.post(url, data=body, headers=headers)
        self.assert200(response)
        self.assertResponseCode(response, 0)
        self.assertResponseDataHasKey(response, 'token')

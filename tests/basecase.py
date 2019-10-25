from flask_testing import TestCase

from eclogue import create_app


class BaseTestCase(TestCase):

    def create_app(self):
        app = create_app(schedule=False)
        return app

    def test_some(self):
        response = self.client.get('/api/v1/test')
        self.assertEqual(response.json, dict(code=0, message='ok'))




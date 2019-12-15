import unittest

from flask import current_app
from app import create_app, db


class BasicsTestCase(unittest.TestCase):
    # run before each test (it tries to create an environment for the test)
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

    # run after each test (database and the application context are removed)
    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    # test ensures that the application instance exists
    def test_app_exists(self):
        self.assertFalse(current_app is None)

    # test ensures that the application is running under the testing configuration
    def test_app_is_testing(self):
        self.assertTrue(current_app.config['TESTING'])



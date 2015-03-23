import httplib
import unittest
from webapp2_extras import json
import webtest

import error_codes
import main
import models
import user_utils

app = webtest.TestApp(main.app)


class RegisterTest(unittest.TestCase):
    # enable the datastore stub
    nosegae_datastore_v3 = True

    def setUp(self):
        self.original_get_facebook_user_id = user_utils.get_facebook_user_id

        def mock_get_facebook_user_id(fb_access_token):
            return str(fb_access_token)
        user_utils.get_facebook_user_id = mock_get_facebook_user_id

    def tearDown(self):
        user_utils.get_facebook_user_id = self.original_get_facebook_user_id

    def test_new_user(self):
        # At first, there should be no account.
        user = models.User.query(models.User.third_party_id == '1').get()
        self.assertIsNone(user)

        # Now register.
        response = app.post('/register', params={'fb_access_token': 1})
        self.assertEqual(httplib.OK, response.status_int)

        # Now check that a User object was indeed created.
        user = models.User.query(models.User.third_party_id == '1').get()
        self.assertIsNotNone(user)

    def test_register_twice_is_error(self):
        # Registering once works.
        response = app.post('/register', params={'fb_access_token': 1})
        self.assertEqual(httplib.OK, response.status_int)

        # Registering a second time should give errors.
        response = app.post('/register', params={'fb_access_token': 1},
                           expect_errors=True)
        self.assertEqual(httplib.BAD_REQUEST, response.status_int)
        response_body = json.decode(response.body)
        self.assertEqual(error_codes.ACCOUNT_EXISTS.code,
                         response_body['error']['error_code'])
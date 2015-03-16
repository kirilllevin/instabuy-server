import httplib
import unittest
from webapp2_extras import json
import webtest

import error_codes
import main
import models
import user_utils

app = webtest.TestApp(main.app)


def mock_get_facebook_user_id(_):
    return '10'

user_utils.get_facebook_user_id = mock_get_facebook_user_id


class RegisterTest(unittest.TestCase):
    # enable the datastore stub
    nosegae_datastore_v3 = True

    def test_new_user(self):
        # First, try registering the user.
        response = app.get('/register', params={'fb_access_token': 1})
        self.assertEqual(httplib.OK, response.status_int)

        # Now check that a User object was indeed created.
        user = models.User.query(models.User.third_party_id == '10').get()
        self.assertIsNotNone(user)

    def test_register_twice_is_error(self):
        # Registering once works.
        response = app.get('/register', params={'fb_access_token': 1})
        self.assertEqual(httplib.OK, response.status_int)

        # Registering a second time should give errors.
        response = app.get('/register', params={'fb_access_token': 1},
                           expect_errors=True)
        self.assertEqual(httplib.BAD_REQUEST, response.status_int)
        response_body = json.decode(response.body)
        self.assertEqual(error_codes.ACCOUNT_EXISTS.code,
                         response_body['error']['error_code'])
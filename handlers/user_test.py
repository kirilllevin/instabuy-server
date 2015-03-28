import httplib
from webapp2_extras import json
import webtest

import error_codes
import main
import models
import test_utils

app = webtest.TestApp(main.app)


class RegisterTest(test_utils.HandlerTest):
    # enable the datastore stub
    nosegae_datastore_v3 = True

    headers = {
        'X-Auth-Token': '2',
        'Content-Type': 'application/json'
    }

    def test_new_user(self):
        # At first, there should be no account.
        user = models.User.query(models.User.third_party_id == '2').get()
        self.assertIsNone(user)

        # Now register.
        response = app.post('/register',
                            headers=self.headers,
                            content_type='application/json')
        self.assertEqual(httplib.OK, response.status_int)

        # Now check that a User object was indeed created.
        user = models.User.query(models.User.third_party_id == '2').get()
        self.assertIsNotNone(user)

    def test_register_twice_is_error(self):
        # Registering once works.
        response = app.post('/register',
                            headers=self.headers,
                            content_type='application/json')
        self.assertEqual(httplib.OK, response.status_int)

        # Registering a second time should give errors.
        response = app.post('/register',
                            headers=self.headers,
                            content_type='application/json',
                            expect_errors=True)
        self.assertEqual(httplib.BAD_REQUEST, response.status_int)
        response_body = json.decode(response.body)
        self.assertEqual(error_codes.ACCOUNT_EXISTS.code,
                         response_body['error']['error_code'])
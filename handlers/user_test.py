import httplib
from webapp2_extras import json
import webtest

import error_codes
import main
import models
import test_utils

app = webtest.TestApp(main.app)


class RegisterTest(test_utils.HandlerTest):
    headers = {
        'X-Auth-Token': '2',
        'Content-Type': 'application/json'
    }

    def test_new_user(self):
        # At first, there should be no account.
        user = models.User.query(models.User.third_party_id == '2').get()
        self.assertIsNone(user)

        # Now register.
        response = app.post('/user/register',
                            params=json.encode({'name': 'fake_name',
                                                'distance_radius_km': 20}),
                            headers=self.headers)
        self.assertEqual(httplib.OK, response.status_int)

        # Now check that a User object was indeed created.
        user = models.User.query(models.User.third_party_id == '2').get()
        self.assertIsNotNone(user)
        self.assertEqual('fake_name', user.name)
        self.assertEqual(20, user.distance_radius_km)

    def test_register_twice_is_error(self):
        # Registering once works.
        response = app.post('/user/register',
                            params=json.encode({'name': 'fake_name'}),
                            headers=self.headers)
        self.assertEqual(httplib.OK, response.status_int)

        # Registering a second time should give errors.
        response = app.post('/user/register',
                            params=json.encode({'name': 'fake_name2'}),
                            headers=self.headers,
                            expect_errors=True)
        self.assertEqual(httplib.BAD_REQUEST, response.status_int)
        response_body = json.decode(response.body)
        self.assertEqual(error_codes.ACCOUNT_EXISTS.code,
                         response_body['error']['error_code'])


class UpdateTest(test_utils.HandlerTest):
    def test_update_nonexisting_user(self):
        headers = self.headers
        headers['X-Auth-Token'] = '2'
        response = app.post('/user/update',
                            params=json.encode({'name': 'changed_name',
                                                'distance_radius_km': 100}),
                            headers=headers,
                            expect_errors=True)
        self.assertEqual(httplib.BAD_REQUEST, response.status_int)
        response_body = json.decode(response.body)
        self.assertEqual(error_codes.INVALID_USER.code,
                         response_body['error']['error_code'])

    def test_proper_update(self):
        self.assertEqual('test_name', self.user.name)
        self.assertEqual(10, self.user.distance_radius_km)
        response = app.post('/user/update',
                            params=json.encode({'name': 'changed_name',
                                                'distance_radius_km': 100}),
                            headers=self.headers,
                            expect_errors=True)
        self.assertEqual(httplib.OK, response.status_int)
        self.user = self.user_key.get()
        self.assertEqual('changed_name', self.user.name)
        self.assertEqual(100, self.user.distance_radius_km)

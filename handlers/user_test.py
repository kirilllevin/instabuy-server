import httplib
from webapp2_extras import json

import error_codes
import models
import test_utils


class AuthenticateTest(test_utils.HandlerTest):
    def test_new_user(self):
        # At first, there should be no account.
        user = models.User.query(models.User.third_party_id == '2').get()
        self.assertIsNone(user)

        # Now authenticate.
        response = self.app.post(
            '/user/auth',
            params=json.encode({'name': 'fake_name'}),
            headers=self.headers_for_user(2))
        self.assertEqual(httplib.OK, response.status_int)

        # Now check that a User object was indeed created.
        user = models.User.query(models.User.third_party_id == '2').get()
        self.assertIsNotNone(user)
        self.assertEqual('fake_name', user.name)
        self.assertIsNotNone(user.distance_radius_km)

    def test_auth_twice_is_idempotent(self):
        # At first, there is just one user, which is the one from the test
        # setup.
        self.assertEqual(1, len(models.User.query().fetch(keys_only=True)))

        # Authenticating once registers the user.
        response = self.app.post(
            '/user/auth',
            params=json.encode({'name': 'fake_name'}),
            headers=self.headers_for_user(2))
        self.assertEqual(httplib.OK, response.status_int)

        # There should be exactly two users now.
        self.assertEqual(2, len(models.User.query().fetch(keys_only=True)))

        # Authenticating a second time should do nothing.
        response = self.app.post(
            '/user/auth',
            params=json.encode({'name': 'fake_name2'}),
            headers=self.headers_for_user(2),
            expect_errors=True)
        self.assertEqual(httplib.OK, response.status_int)

        # There should still be exactly two users.
        self.assertEqual(2, len(models.User.query().fetch(keys_only=True)))


class UpdateTest(test_utils.HandlerTest):
    def test_update_nonexisting_user(self):
        response = self.app.post(
            '/user/update',
            params=json.encode({'name': 'changed_name',
                                'distance_radius_km': 100}),
            headers=self.headers_for_user(2),
            expect_errors=True)
        self.assertEqual(httplib.BAD_REQUEST, response.status_int)
        response_body = json.decode(response.body)
        self.assertEqual(error_codes.INVALID_USER.code,
                         response_body['error']['error_code'])

    def test_proper_update(self):
        self.assertEqual('test_name', self.user.name)
        self.assertEqual(10, self.user.distance_radius_km)
        response = self.app.post(
            '/user/update',
            params=json.encode({'name': 'changed_name',
                                'distance_radius_km': 100}),
            headers=self.headers_for_user(self.user.third_party_id),
            expect_errors=True)
        self.assertEqual(httplib.OK, response.status_int)
        self.user = self.user_key.get()
        self.assertEqual('changed_name', self.user.name)
        self.assertEqual(100, self.user.distance_radius_km)

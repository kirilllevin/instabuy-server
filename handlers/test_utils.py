import unittest

import models
import user_utils


class HandlerTest(unittest.TestCase):

    def setUp(self):
        self.original_get_facebook_user_id = user_utils.get_facebook_user_id

        def mock_get_facebook_user_id(fb_access_token):
            return str(fb_access_token)
        user_utils.get_facebook_user_id = mock_get_facebook_user_id

        self.user = models.User(login_type='facebook', third_party_id='1')
        self.user_key = self.user.put()

    def tearDown(self):
        user_utils.get_facebook_user_id = self.original_get_facebook_user_id

    def make_request(self, fb_access_token=1):
        pass
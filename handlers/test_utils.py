from google.appengine.ext import ndb
import unittest

import models
import user_utils


class HandlerTest(unittest.TestCase):

    headers = {
        'X-Auth-Token': '1',
        'Content-Type': 'application/json'
    }

    def setUp(self):
        self.original_get_facebook_user_id = user_utils.get_facebook_user_id

        def mock_get_facebook_user_id(fb_access_token):
            return str(fb_access_token)
        user_utils.get_facebook_user_id = mock_get_facebook_user_id

        self.user = models.User(login_type='facebook',
                                third_party_id='1',
                                name='test_name',
                                distance_radius_km=10)
        self.user_key = self.user.put()

    def tearDown(self):
        # Delete all the data.
        ndb.delete_multi(models.User.query().fetch(keys_only=True))
        ndb.delete_multi(models.LikeState.query().fetch(keys_only=True))
        ndb.delete_multi(models.Item.query().fetch(keys_only=True))
        ndb.delete_multi(models.Image().query().fetch(keys_only=True))

        user_utils.get_facebook_user_id = self.original_get_facebook_user_id

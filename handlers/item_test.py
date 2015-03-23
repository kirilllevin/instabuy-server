from google.appengine.api import files
from google.appengine.ext import blobstore
from google.appengine.ext import ndb
import httplib
import unittest
from webapp2_extras import json
import webtest

import error_codes
import main
import models
import user_utils

app = webtest.TestApp(main.app)


class DeleteItemTest(unittest.TestCase):
    # Enable the relevant stubs.
    nosegae_blobstore = True
    nosegae_datastore_v3 = True
    nosegae_file = True
    nosegae_images = True
    nosegae_search = True

    def setUp(self):
        self.original_get_facebook_user_id = user_utils.get_facebook_user_id

        def mock_get_facebook_user_id(fb_access_token):
            return str(fb_access_token)
        user_utils.get_facebook_user_id = mock_get_facebook_user_id

        self.user = models.User(login_type='facebook', third_party_id='1')
        self.user_key = self.user.put()

    def tearDown(self):
        user_utils.get_facebook_user_id = self.original_get_facebook_user_id

    def test_delete_invalid_item(self):
        # Ensure that there is no item with id=7.
        self.assertIsNone(ndb.Key(models.Item, 7).get())

        # Now try to delete it.
        response = app.post('/delete_item',
                            params={'fb_access_token': 1,
                                    'item_id': 7},
                            expect_errors=True)
        self.assertEqual(httplib.BAD_REQUEST, response.status_int)
        response_body = json.decode(response.body)
        self.assertEqual(error_codes.INVALID_ITEM.code,
                         response_body['error']['error_code'])

    def test_delete_wrong_user(self):
        # Set up an item that is owned by a different user.
        item = models.Item(user_id=ndb.Key(models.User, self.user_key.id() + 1))
        item_key = item.put()
        response = app.post('/delete_item',
                            params={'fb_access_token': 1,
                                    'item_id': item_key.id()},
                            expect_errors=True)
        self.assertEqual(httplib.BAD_REQUEST, response.status_int)
        response_body = json.decode(response.body)
        self.assertEqual(error_codes.USER_PERMISSION_ERROR.code,
                         response_body['error']['error_code'])

    def test_successful_delete(self):
        # TODO: Update test to include search document.

        # Set up the item we're going to delete.
        file_name = files.blobstore.create(mime_type='application/octet-stream')
        with files.open(file_name, 'a') as f:
            f.write('fake_image_data')
        files.finalize(file_name)
        blob_key = files.blobstore.get_blob_key(file_name)
        image = models.Image(blob_key=blob_key, url='/fake')

        item = models.Item(user_id=ndb.Key(models.User, self.user_key.id()),
                           image=[image])
        item_key = item.put()

        # Set up a second user that has seen this item.
        other_user = models.User(login_type='facebook',
                                 third_party_id='2',
                                 seen_items=[item_key.id()])
        other_user_key = other_user.put()
        like_state = models.LikeState(user_id=other_user_key,
                                      item_id=item_key,
                                      like_state=False)
        like_state_key = like_state.put()

        # Delete the item.
        response = app.post('/delete_item',
                            params={'fb_access_token': 1,
                                    'item_id': item_key.id()})
        self.assertEqual(httplib.OK, response.status_int)

        # Check that the other user's seen_items list no longer has this
        # item's id.
        # We need to refetch other_user because the version we have is a
        # local copy.
        other_user = other_user_key.get()
        self.assertListEqual([], other_user.seen_items)

        # Check that the associated image was deleted from the blobstore.
        self.assertIsNone(blobstore.get(blob_key))

        # Check that the like state was deleted.
        self.assertIsNone(like_state_key.get())

        # Check that the item itself was deleted.
        self.assertIsNone(item_key.get())

from google.appengine.api import files
from google.appengine.api import search
from google.appengine.ext import blobstore
from google.appengine.ext import ndb
import httplib
import unittest
from webapp2_extras import json
import webtest

import constants
import error_codes
import main
import models
import user_utils

app = webtest.TestApp(main.app)


class PostTest(unittest.TestCase):
    nosegae_blobstore = True
    nosegae_datastore_v3 = True
    nosegae_search = True

    def setUp(self):
        self.original_get_facebook_user_id = user_utils.get_facebook_user_id

        def mock_get_facebook_user_id(fb_access_token):
            return str(fb_access_token)
        user_utils.get_facebook_user_id = mock_get_facebook_user_id

        self.user = models.User(login_type='facebook', third_party_id='1')
        self.user_key = self.user.put()
        self.item_index = search.Index(name=constants.ITEM_INDEX_NAME)
        self.params = {
            'fb_access_token': 1,
            'title': 'fake_title',
            'description': 'fake_description',
            'price': 10.00,
            'currency': 'USD',
            'category': 'other',
            'lat': 0,
            'lng': 0,
        }

    def tearDown(self):
        user_utils.get_facebook_user_id = self.original_get_facebook_user_id

    def test_post_invalid_latlng(self):
        self.params['lat'] = 900
        response = app.post('/post_item',
                            params=self.params,
                            expect_errors=True)
        self.assertEqual(httplib.BAD_REQUEST, response.status_int)
        response_body = json.decode(response.body)
        self.assertEqual(error_codes.MALFORMED_REQUEST.code,
                         response_body['error']['error_code'])

    def test_post_simple(self):
        response = app.post('/post_item', params=self.params)
        self.assertEqual(httplib.OK, response.status_int)
        response_body = json.decode(response.body)
        item_id = long(response_body['item_id'])

        # Check that the item object was created.
        item = models.Item.get_by_id(item_id)
        self.assertIsNotNone(item)
        self.assertEqual(self.user_key, item.user_id)

        # Check that the search document was created.
        doc = self.item_index.get(str(item_id))
        self.assertIsNotNone(doc)
        self.assertEqual('fake_title', doc.field('title').value)
        self.assertEqual('fake_description', doc.field('description').value)
        self.assertEqual(10, doc.field('price').value)
        self.assertEqual('USD', doc.field('currency').value)
        self.assertEqual('other', doc.field('category').value)
        self.assertEqual(search.GeoPoint(0, 0), doc.field('location').value)


class DeleteTest(unittest.TestCase):
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
        self.item_index = search.Index(name=constants.ITEM_INDEX_NAME)

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
        # Set up the item we're going to delete.
        file_name = files.blobstore.create(mime_type='application/octet-stream')
        with files.open(file_name, 'a') as f:
            f.write('fake_image_data')
        files.finalize(file_name)
        blob_key = files.blobstore.get_blob_key(file_name)
        self.assertIsNotNone(blobstore.get(blob_key))

        image = models.Image(blob_key=blob_key, url='/fake')

        item = models.Item(user_id=ndb.Key(models.User, self.user_key.id()),
                           image=[image])
        item_key = item.put()
        self.assertIsNotNone(item_key.get())

        # Set up the search documented associated to this item.
        fields = [
            search.AtomField(name='user_id', value=str(self.user_key.id())),
            search.TextField(name='title', value='fake_title'),
            search.TextField(name='description', value='fake_description')]
        item_doc = search.Document(
            doc_id=str(item_key.id()),
            fields=fields)
        self.item_index.put(item_doc)
        self.assertIsNotNone(self.item_index.get(str(item_key.id())))

        # Set up a second user that has seen this item.
        other_user = models.User(login_type='facebook',
                                 third_party_id='2',
                                 seen_items=[item_key.id()])
        other_user_key = other_user.put()
        like_state = models.LikeState(user_id=other_user_key,
                                      item_id=item_key,
                                      like_state=False)
        like_state_key = like_state.put()
        self.assertIsNotNone(like_state_key.get())

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

        # Check that the associated search document was deleted.
        self.assertIsNone(self.item_index.get(str(item_key.id())))

        # Check that the associated image was deleted from the blobstore.
        self.assertIsNone(blobstore.get(blob_key))

        # Check that the like state was deleted.
        self.assertIsNone(like_state_key.get())

        # Check that the item itself was deleted.
        self.assertIsNone(item_key.get())

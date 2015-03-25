from google.appengine.api import search
from google.appengine.ext import blobstore
from google.appengine.ext import ndb
import httplib
from webapp2_extras import json
import webtest

import constants
import error_codes
import main
import models
import test_utils

app = webtest.TestApp(main.app)


class PostTest(test_utils.HandlerTest):
    nosegae_datastore_v3 = True
    nosegae_search = True

    params = {
        'title': 'fake_title',
        'description': 'fake_description',
        'price': 10.00,
        'currency': 'USD',
        'category': 'other',
        'lat': 0,
        'lng': 0,
    }

    def test_post_invalid_latlng(self):
        params = self.params.copy()
        params['lat'] = 900
        response = app.post('/post_item',
                            params=json.encode(params),
                            headers=self.headers,
                            content_type='application/json',
                            expect_errors=True)
        self.assertEqual(httplib.BAD_REQUEST, response.status_int)
        response_body = json.decode(response.body)
        self.assertEqual(error_codes.MALFORMED_REQUEST.code,
                         response_body['error']['error_code'])

    def test_post_simple(self):
        response = app.post('/post_item',
                            params=json.encode(self.params),
                            headers=self.headers,
                            content_type='application/json')
        self.assertEqual(httplib.OK, response.status_int)
        response_body = json.decode(response.body)
        item_id = long(response_body['item_id'])

        # Check that the item object was created.
        item = models.Item.get_by_id(item_id)
        self.assertIsNotNone(item)
        self.assertEqual(self.user_key, item.user_id)

        # Check that the search document was created.
        item_index = search.Index(name=constants.ITEM_INDEX_NAME)
        doc = item_index.get(str(item_id))
        self.assertIsNotNone(doc)
        self.assertEqual('fake_title', doc.field('title').value)
        self.assertEqual('fake_description', doc.field('description').value)
        self.assertEqual(10, doc.field('price').value)
        self.assertEqual('USD', doc.field('currency').value)
        self.assertEqual('other', doc.field('category').value)
        self.assertEqual(search.GeoPoint(0, 0), doc.field('location').value)


class GetTest(test_utils.HandlerTest):
    # Enable the relevant stubs.
    nosegae_blobstore = True
    nosegae_datastore_v3 = True
    nosegae_images = True
    nosegae_search = True

    def setUp(self):
        super(GetTest, self).setUp()
        self.maxDiff = None

        item_index = search.Index(name=constants.ITEM_INDEX_NAME)

        # An item that belongs to the current user.
        user_item = models.Item(
            user_id=ndb.Key(models.User, self.user_key.id()))
        user_item_key = user_item.put()
        fields = [
            search.AtomField(name='user_id', value=str(self.user_key.id())),
            search.TextField(name='title', value='user_item_title'),
            search.TextField(name='category', value=''),
            search.TextField(name='description',
                             value='user_item_description'),
            search.NumberField(name='price', value=10),
            search.TextField(name='currency', value='currency'),
            search.GeoField(name='location',
                            value=search.GeoPoint(0, 0))]
        item_index.put(
            search.Document(doc_id=str(user_item_key.id()), fields=fields))

        # Another user's item that this user already liked.
        liked_item = models.Item(
            user_id=ndb.Key(models.User, self.user_key.id() + 1))
        liked_item_key = liked_item.put()
        fields = [
            search.AtomField(name='user_id', value=str(self.user_key.id() + 1)),
            search.TextField(name='title', value='liked_item_title'),
            search.TextField(name='category', value=''),
            search.TextField(name='description',
                             value='liked_item_description'),
            search.NumberField(name='price', value=10),
            search.TextField(name='currency', value='currency'),
            search.GeoField(name='location',
                            value=search.GeoPoint(0, 0))]
        item_index.put(
            search.Document(doc_id=str(liked_item_key.id()), fields=fields))
        like_state = models.LikeState(user_id=self.user_key,
                                      item_id=liked_item_key,
                                      like_state=True)
        like_state.put()
        self.user.seen_items = [liked_item_key.id()]
        self.user.put()

        # Another user's item that this user hasn't seen. This one also has an
        # image attached to it.
        self.testbed.get_stub('blobstore').CreateBlob(
            'blob_key', 'fake_image_data')
        blob_key = blobstore.BlobKey('blob_key')
        image = models.Image(blob_key=blob_key, url='/fake')
        new_item_a = models.Item(
            user_id=ndb.Key(models.User, self.user_key.id() + 1),
            image=[image])
        new_item_a_key = new_item_a.put()
        fields = [
            search.AtomField(name='user_id', value=str(self.user_key.id() + 1)),
            search.TextField(name='title', value='new_item_a_title'),
            search.TextField(name='category', value='category_a'),
            search.TextField(name='description',
                             value='new_item_a_description'),
            search.NumberField(name='price', value=10),
            search.TextField(name='currency', value='currency_a'),
            search.GeoField(name='location',
                            value=search.GeoPoint(0, 0))]
        item_index.put(
            search.Document(doc_id=str(new_item_a_key.id()),
                            fields=fields))
        self.result_item_a = {
            u'item_id': unicode(new_item_a_key.id()),
            u'date_time_added': u'',
            u'date_time_modified': u'',
            u'title': u'new_item_a_title',
            u'category': u'category_a',
            u'description': u'new_item_a_description',
            u'price': 10,
            u'currency': u'currency_a',
            u'image': [unicode(image.url)],
            u'lat': 0,
            u'lng': 0}

        # Another user's item that this user hasn't seen, but with a
        # different category.
        new_item_b = models.Item(
            user_id=ndb.Key(models.User, self.user_key.id() + 1))
        new_item_b_key = new_item_b.put()
        fields = [
            search.AtomField(name='user_id', value=str(self.user_key.id() + 1)),
            search.TextField(name='title', value='new_item_b_title'),
            search.TextField(name='category', value='category_b'),
            search.TextField(name='description',
                             value='new_item_b_description'),
            search.NumberField(name='price', value=10),
            search.TextField(name='currency', value='currency_b'),
            search.GeoField(name='location',
                            value=search.GeoPoint(0, 0))]
        item_index.put(
            search.Document(doc_id=str(new_item_b_key.id()),
                            fields=fields))
        self.result_item_b = {
            u'item_id': unicode(new_item_b_key.id()),
            u'date_time_added': u'',
            u'date_time_modified': u'',
            u'title': u'new_item_b_title',
            u'category': u'category_b',
            u'description': u'new_item_b_description',
            u'price': 10,
            u'currency': u'currency_b',
            u'image': [],
            u'lat': 0,
            u'lng': 0}

    def compare_lists_of_dicts_ignore_order(self, expected, actual):
        self.assertEqual(len(expected), len(actual))
        sorted_expected = sorted(expected)
        sorted_actual = sorted(actual)
        for i in range(0, len(expected)):
            self.assertDictEqual(sorted_expected[i], sorted_actual[i])

    def test_get_by_distance(self):
        response = app.get('/get_items',
                           params={'lat': 0, 'lng': 0},
                           headers=self.headers)
        self.assertEqual(httplib.OK, response.status_int)
        results = json.decode(response.body)['results']

        # Only new_item_a and new_item_b should be returned, doesn't matter
        # in which order.
        self.compare_lists_of_dicts_ignore_order(
            [self.result_item_a, self.result_item_b], results)

    def test_distance_too_far(self):
        response = app.get('/get_items',
                           params={'lat': 0, 'lng': 180},
                           headers=self.headers)
        self.assertEqual(httplib.OK, response.status_int)
        results = json.decode(response.body)['results']

        # There should be no results if we search from the opposite side of
        # the earth.
        self.assertEqual(0, len(results))

    def test_get_by_category(self):
        response = app.get('/get_items',
                           params={'lat': 0, 'lng': 0,
                                   'category': 'category_a'},
                           headers=self.headers)
        self.assertEqual(httplib.OK, response.status_int)
        results = json.decode(response.body)['results']

        # Only new_item_a has category set to category_a.
        self.compare_lists_of_dicts_ignore_order([self.result_item_a], results)

    def test_get_by_search(self):
        response = app.get('/get_items',
                           params={'lat': 0, 'lng': 0,
                                   'search_query': 'new_item_b_description'},
                           headers=self.headers)
        self.assertEqual(httplib.OK, response.status_int)
        results = json.decode(response.body)['results']

        # Only new_item_b has the token being searched for.
        self.compare_lists_of_dicts_ignore_order([self.result_item_b], results)

    def test_cursor(self):
        orig_num_items_per_request = constants.NUM_ITEMS_PER_REQUEST
        orig_num_items_per_page = constants.NUM_ITEMS_PER_PAGE
        constants.NUM_ITEMS_PER_REQUEST = 1
        constants.NUM_ITEMS_PER_PAGE = 1

        try:
            response = app.get('/get_items',
                               params={'lat': 0, 'lng': 0},
                               headers=self.headers)
            self.assertEqual(httplib.OK, response.status_int)
            json_body = json.decode(response.body)

            # Check that we were given a cursor.
            self.assertTrue('cursor' in json_body)

            # Check that we got one response, which is either new_item_a or
            # new_item_b.
            self.assertEqual(1, len(json_body['results']))
            first_result = json_body['results'][0]
            self.assertTrue(first_result in [self.result_item_a,
                                             self.result_item_b])

            # Now ask for more items, passing in the cursor.
            response = app.get('/get_items',
                               params={'lat': 0, 'lng': 0,
                                       'cursor': json_body['cursor']},
                               headers=self.headers)
            self.assertEqual(httplib.OK, response.status_int)
            json_body = json.decode(response.body)

            # There should not be a cursor now that we've exhausted the results.
            self.assertFalse('cursor' in json_body)

            # Again, we should have gotten one response, which is either
            # new_item_a or new_item_b.
            self.assertEqual(1, len(json_body['results']))
            second_result = json_body['results'][0]
            self.assertTrue(second_result in [self.result_item_a,
                                              self.result_item_b])

            # The two results we got from the two invocations should be
            # different.
            self.assertNotEqual(first_result, second_result)
        finally:
            constants.NUM_ITEMS_PER_REQUEST = orig_num_items_per_request
            constants.NUM_ITEMS_PER_PAGE = orig_num_items_per_page


class DeleteTest(test_utils.HandlerTest):
    # Enable the relevant stubs.
    nosegae_blobstore = True
    nosegae_datastore_v3 = True
    nosegae_images = True
    nosegae_search = True

    def test_delete_invalid_item(self):
        # Ensure that there is no item with id=7.
        self.assertIsNone(ndb.Key(models.Item, 7).get())

        # Now try to delete it.
        response = app.post('/delete_item',
                            params=json.encode({'item_id': 7}),
                            headers=self.headers,
                            content_type='application/json',
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
                            params=json.encode({'item_id': item_key.id()}),
                            headers=self.headers,
                            content_type='application/json',
                            expect_errors=True)
        self.assertEqual(httplib.BAD_REQUEST, response.status_int)
        response_body = json.decode(response.body)
        self.assertEqual(error_codes.USER_PERMISSION_ERROR.code,
                         response_body['error']['error_code'])

    def test_successful_delete(self):
        item_index = search.Index(name=constants.ITEM_INDEX_NAME)
        # Set up the item we're going to delete.
        self.testbed.get_stub('blobstore').CreateBlob(
            'blob_key', 'fake_image_data')
        blob_key = blobstore.BlobKey('blob_key')
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
        item_index.put(item_doc)
        self.assertIsNotNone(item_index.get(str(item_key.id())))

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
                            params=json.encode({'item_id': item_key.id()}),
                            headers=self.headers,
                            content_type='application/json')
        self.assertEqual(httplib.OK, response.status_int)

        # Check that the other user's seen_items list no longer has this
        # item's id.
        # We need to refetch other_user because the version we have is a
        # local copy.
        other_user = other_user_key.get()
        self.assertListEqual([], other_user.seen_items)

        # Check that the associated search document was deleted.
        self.assertIsNone(item_index.get(str(item_key.id())))

        # Check that the associated image was deleted from the blobstore.
        self.assertIsNone(blobstore.get(blob_key))

        # Check that the like state was deleted.
        self.assertIsNone(like_state_key.get())

        # Check that the item itself was deleted.
        self.assertIsNone(item_key.get())


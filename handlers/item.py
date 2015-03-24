import logging

from google.appengine.api import images
from google.appengine.api import search
from google.appengine.ext import blobstore
from google.appengine.ext import ndb
from webapp2_extras import json

import constants
import error_codes
import base
import models


class Post(base.BaseHandler):
    @ndb.toplevel
    def post(self):
        success = self.parse_request(
            {'fb_access_token': (str, True, None),
             'title':       (str, True, None),
             'description': (str, True, None),
             'price':       (float, True, None),
             'currency':    (str, True, None),
             'category':    (str, True, None),
             'lat':         (float, True, lambda x: -90 <= x <= 90),
             'lng':         (float, True, lambda x: -180 <= x <= 180)})
        if not success:
            self.populate_error_response(error_codes.MALFORMED_REQUEST)
            return

        # Retrieve the user associated with the Facebook token.
        if not self.populate_user(self.args['fb_access_token']):
            return

        item = models.Item(user_id=self.user.key)
        item_key = item.put()

        try:
            fields = [
                # Include the user ID so we can skip items owned by a user in
                # queries.
                search.AtomField(name='user_id', value=str(self.user.key.id())),
                search.AtomField(name='category', value=self.args['category']),
                search.TextField(name='title', value=self.args['title']),
                search.TextField(name='description',
                                 value=self.args['description']),
                search.NumberField(name='price', value=self.args['price']),
                search.TextField(name='currency', value=self.args['currency']),
                search.GeoField(name='location',
                                value=search.GeoPoint(
                                    self.args['lat'], self.args['lng']))]
            # The Item object's id is shared with the document.
            item_doc = search.Document(
                doc_id=str(item_key.id()),
                fields=fields)

            index = search.Index(name=constants.ITEM_INDEX_NAME)
            index.put(item_doc)
        except search.Error:
            # Delete the stored item.
            item_key.delete()
            self.populate_error_response(error_codes.INDEXING_ERROR)
            return

        self.populate_success_response({'item_id': item_key.id()})


class Delete(base.BaseHandler):
    @ndb.toplevel
    def post(self):
        success = self.parse_request(
            {'fb_access_token': (str, True, None),
             'item_id': (long, True, None)})
        if not success:
            self.populate_error_response(error_codes.MALFORMED_REQUEST)
            return

        if not self.populate_user(self.args['fb_access_token']):
            return
        if not self.populate_item_for_mutation(self.args['item_id']):
            return

        # Delete all the likes/dislikes of this item by removing all the
        # LikedItemState objects that are mentioning this item.
        dislikes_query = models.LikeState.query(
            models.LikeState.item_id == self.item.key)
        ndb.delete_multi_async(dislikes_query.fetch(keys_only=True))

        # Delete this item's id from all the seen_items lists of all users.
        users_query = models.User.query(
            models.User.seen_items == self.item.key.id())
        cursor = None
        more = True
        while more:
            users, cursor, more = users_query.fetch_page(
                constants.NUM_USERS_PER_PAGE, start_cusor=cursor)
            for user in users:
                # Delete the unique occurrence of the item's id in the
                # seen_items list.
                del user.seen_items[user.seen_items.index(self.item.key.id())]
            ndb.put_multi_async(users)

        # TODO: When chat is implemented, delete all the chat conversations
        # associated to this item as well.

        # Delete all the image data associated to this item.
        blobstore_future = blobstore.delete_async(
            [image.blob_key for image in self.item.image])
        for image in self.item.image:
            images.delete_serving_url(image.blob_key)

        # Delete the search document associated with this item.
        try:
            index = search.Index(name=constants.ITEM_INDEX_NAME)
            index_future = index.delete_async(str(self.item.key.id()))
        except search.Error as e:
            logging.error(
                'Index delete failed for item_id={}. Message: {}'.format(
                    self.item.key.id(), e.message))

        # Delete the item itself.
        self.item.key.delete_async()

        # We actually have to wait on the Blobstore and Index futures, unlike
        # the others.
        index_future.get_result()
        blobstore_future.wait()
        self.populate_success_response()


class Get(base.BaseHandler):
    @ndb.toplevel
    def get(self):
        success = self.parse_request(
            {'fb_access_token': (str, True, None),
             'lat':          (float, True, lambda x: -90 <= x <= 90),
             'lng':          (float, True, lambda x: -180 <= x <= 180),
             'category':     (str, False, None),
             'search_query': (str, False, None),
             'cursor':       (str, False, None)})
        if not success:
            self.populate_error_response(error_codes.MALFORMED_REQUEST)
            return

        cursor = search.Cursor(web_safe_string=self.args['cursor'])

        # Populate a set containing the ids of all the items that the user has
        # already seen. These will need to be skipped.
        seen_items = set(self.user.seen_items)

        # This will store dict representations
        returned_results = []

        query = [
            'distance(location, geopoint({}, {})) < {}'.format(
                self.args['lat'], self.args['lng'],
                self.user.distance_radius_km),
            'NOT user_id={}'.format(self.user.key.id())]
        if self.args['category']:
            query.append('category={}'.format(self.args['category']))
        if self.args['search_query']:
            # Split the search query on whitespace, convert to lowercase and
            # stem each word. then join on space and add to the query.
            t = ['~' + t for t in self.args['search_query'].lower().split()]
            query.append(' '.join(t))

        begin_search = True
        item_index = search.Index(constants.ITEM_INDEX_NAME)
        try:
            while (len(returned_results) < constants.NUM_ITEMS_PER_REQUEST and
                   (begin_search or cursor is not None)):
                begin_search = False
                search_response = item_index.search(
                    search.Query(' AND '.join(query),
                                 options=search.QueryOptions(
                                     limit=constants.NUM_ITEMS_PER_PAGE,
                                     cursor=cursor)))
                cursor = search_response.cursor
                for document in search_response.results:
                    # Skip items that the user has seen already.
                    if int(document.doc_id) in seen_items:
                        continue
                    # Skip items owned by the user.
                    if document.field('user_id') == str(self.user.key.id()):
                        continue
                    # Create a JSON representation of the item to be returned.
                    item = models.Item.get_by_id(document.doc_id)

                    # TODO: Figure out how to convert DateTimeProperty.
                    item_dict = {
                        'item_id': document.doc_id,
                        'date_time_added': '',
                        'date_time_modified': '',
                        'title': document.field('title').value,
                        'category': document.field('category').value,
                        'description': document.field('description').value,
                        'price': document.field('price').value,
                        'currency': document.field('currency').value,
                        'image': [i.url for i in item.image],
                    }
                    returned_results.append(item_dict)
                    if len(returned_results) == constants.NUM_ITEMS_PER_REQUEST:
                        break

        except search.Error as e:
            logging.error(
                'Item search failed for query="{}". Message: {}'.format(
                    query, e.message))
            self.populate_error_response(error_codes.SEARCH_ERROR)
            return

        self.populate_success_response(
            {'results': json.encode(returned_results),
             'cursor': cursor.web_safe_string()})

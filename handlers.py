import logging

from google.appengine.api import images
from google.appengine.api import search
from google.appengine.ext import blobstore
from google.appengine.ext import ndb
from google.appengine.ext.webapp import blobstore_handlers
from webapp2_extras import json

import constants
import error_codes
import instabuy_handler
import user_utils
import models


class DefaultHandler(instabuy_handler.InstabuyHandler):
    def get(self):
        self.response.write('This is the default handler!')


class Register(instabuy_handler.InstabuyHandler):
    @ndb.toplevel
    def get(self):
        # Verify that the required parameters were supplied.
        fb_access_token = self.request.get('fb_access_token')
        if not fb_access_token:
            self.populate_error_response(error_codes.MALFORMED_REQUEST)
            return

        # Use the token to get the Facebook user id.
        try:
            fb_user_id = user_utils.get_facebook_user_id(fb_access_token)
        except user_utils.FacebookTokenExpiredException:
            self.populate_error_response(error_codes.FACEBOOK_TOKEN_ERROR)
            return
        except user_utils.FacebookException as e:
            self.populate_error_response(error_codes.FACEBOOK_ERROR, e)
            return

        # Check if the user is already registered.
        user = models.User.query(models.User.third_party_id == fb_user_id).get()
        if user:
            self.populate_error_response(error_codes.ACCOUNT_EXISTS)
            return

        # Store a new user entry.
        user = models.User(login_type='facebook',
                           third_party_id=fb_user_id)
        user.put()
        self.populate_success_response()


class ClearAllEntry(instabuy_handler.InstabuyHandler):
    @ndb.toplevel
    def get(self):
        ndb.delete_multi(models.User.query().fetch(keys_only=True))
        ndb.delete_multi(models.LikeState.query().fetch(keys_only=True))
        ndb.delete_multi(models.Item.query().fetch(keys_only=True))
        ndb.delete_multi(models.Image().query().fetch(keys_only=True))
        self.populate_success_response()


class GetImageUploadUrl(instabuy_handler.InstabuyHandler):
    @ndb.toplevel
    def get(self):
        self.populate_success_response(
            {'upload_url': blobstore.create_upload_url('/upload_image')})


class UploadImage(blobstore_handlers.BlobstoreUploadHandler,
                  instabuy_handler.InstabuyHandler):
    @ndb.toplevel
    def post(self):
        # Verify that the required parameters were supplied.
        fb_access_token = self.request.POST['fb_access_token']
        item_id = self.request.POST['item_id']

        # Verify that the request is formed correctly.
        malformed_request = False
        try:
            if not (fb_access_token and item_id):
                malformed_request = True
            else:
                item_id = long(item_id)
        except ValueError:
            malformed_request = False

        if malformed_request:
            self.populate_error_response(error_codes.MALFORMED_REQUEST)
            return

        # Check that something was uploaded.
        uploads = self.get_uploads()
        if not uploads:
            self.populate_error_response(error_codes.UPLOAD_FAILED)
            return
        image_key = uploads[0].key()

        if not (self.populate_user(fb_access_token) and
                self.populate_item_for_mutation(item_id)):
            # Delete the blob.
            blobstore.delete(image_key)
            return

        # Append the image key to the item's list of images.
        image = models.Image(blob_key=image_key,
                             url=images.get_serving_url(image_key))

        self.item.image.append(image)
        self.item.put()

        self.populate_success_response()


class PostItem(instabuy_handler.InstabuyHandler):
    @ndb.toplevel
    def post(self):
        # Verify that the required parameters were supplied.
        fb_access_token = self.request.POST['fb_access_token']
        title = self.request.POST['title']
        description = self.request.POST['description']
        price = self.request.POST['price']
        currency = self.request.POST['currency']
        category = self.request.POST.getall('category')
        lat = self.request.POST['lat']
        lng = self.request.POST['lng']

        malformed_request = False
        try:
            if not (fb_access_token and title and description and price and
                    currency and category and lat and lng):
                malformed_request = True
            else:
                lat = float(lat)
                lng = float(lng)
        except ValueError:
            malformed_request = True

        if malformed_request:
            self.populate_error_response(error_codes.MALFORMED_REQUEST)
            return

        # Retrieve the user associated with the Facebook token.
        if not self.populate_user(fb_access_token):
            return

        item = models.Item(user_id=self.user.key())
        item_key = item.put()

        fields = [
            # Include the user ID so we can skip items owned by a user in
            # queries.
            search.AtomField(name='user_id', value=self.user.key()),
            search.AtomField(name='category', value=category),
            search.TextField(name='title', value=title),
            search.TextField(name='description', value=description),
            search.TextField(name='price', value=price),
            search.TextField(name='currency', value=currency),
            search.GeoField(name='location', value=search.GeoPoint(lat, lng))]

        # The Item object's id is shared with the document.
        item_doc = search.Document(
            doc_id=str(item_key.id()),
            fields=fields)
        try:
            index = search.Index(name=constants.ITEM_INDEX_NAME)
            index.put(item_doc)
        except search.Error:
            # Delete the stored item.
            item_key.delete()
            self.populate_error_response(error_codes.INDEXING_ERROR)
            return

        self.populate_success_response({'item_id': item_key.id()})


class DeleteItem(instabuy_handler.InstabuyHandler):
    @ndb.toplevel
    def get(self):
        # Verify that the required parameters were supplied.
        fb_access_token = self.request.get('fb_access_token')
        item_id = self.request.get('item_id')
        malformed_request = False
        try:
            if not (fb_access_token and item_id):
                malformed_request = True
            else:
                item_id = long(item_id)
        except ValueError:
            malformed_request = True

        if malformed_request:
            self.populate_error_response(error_codes.MALFORMED_REQUEST)
            return

        if not self.populate_user(fb_access_token):
            return
        if not self.populate_item_for_mutation(item_id):
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


class UpdateItemLikeState(instabuy_handler.InstabuyHandler):
    @ndb.toplevel
    def get(self):
        # Verify that the required parameters were supplied.
        fb_access_token = self.request.get('fb_access_token')
        item_id = self.request.get('item_id')
        like_state = self.request.get('like_state')

        malformed_request = False
        try:
            if not (fb_access_token and item_id and like_state):
                malformed_request = True
            else:
                like_state = int(like_state)
                item_id = long(item_id)
                # Ensure that like_state is either 1 (like) or 0 (dislike).
                if like_state != 0 and like_state != 1:
                    malformed_request = True
        except ValueError:
            malformed_request = True
        if malformed_request:
            self.populate_error_response(error_codes.MALFORMED_REQUEST)
            return

        # Retrieve the relevant user and item objects.
        if not self.populate_user(fb_access_token):
            return
        if not self.populate_item(item_id):
            return

        # Check if we already recorded a like state for this user, item pair.
        # If it exists, simply update it, otherwise store a new one.
        query = models.LikeState.query(
            models.LikeState.item_id == self.item.key)
        item_like_state = query.filter(
            models.LikeState.user_id == self.user.key).get()
        if item_like_state:
            item_like_state.like_state = bool(like_state)
        else:
            item_like_state = models.LikeState(
                parent=self.item.key,
                user_id=self.user.key,
                like_state=bool(like_state))
            # Mark that the user has now seen this item.
            self.user.seen_items.append(self.item.key.id())
            self.user.put_async()
        item_like_state.put_async()
        self.populate_success_response()


class GetItems(instabuy_handler.InstabuyHandler):
    @ndb.toplevel
    def get(self):
        # Verify that the required parameters were supplied.
        fb_access_token = self.request.get('fb_access_token')
        request_type = self.request.get('request_type')
        cursor = search.Cursor(web_safe_string=self.request.get('cursor'))
        category = self.request.get('category')
        user_query = self.request.get('query')
        lat = self.request.get('lat')
        lng = self.request.get('lng')

        malformed_request = False
        try:
            if not (fb_access_token and request_type):
                malformed_request = True
            else:
                # Validate that the request contained all the necessary data for
                # the given request type.
                if request_type == constants.RETRIEVAL_CATEGORY:
                    # Category must be provided.
                    malformed_request = not category
                elif request_type == constants.RETRIEVAL_NEARBY:
                    # Lat/lng must be provided.
                    malformed_request = not (lat and lng)
                    lat = float(lat)
                    lng = float(lng)
                elif request_type == constants.RETRIEVAL_SEARCH:
                    # Search query must be provided.
                    malformed_request = not user_query
        except ValueError:
            malformed_request = True

        if malformed_request:
            self.populate_error_response(error_codes.MALFORMED_REQUEST)
            return

        # Populate a set containing the ids of all the items that the user has
        # already seen. These will need to be skipped.
        seen_items = set(self.user.seen_items)

        # This will store dict representations
        returned_results = []

        # Figure out which query to use based on the request type.
        if request_type == constants.RETRIEVAL_CATEGORY:
            query = 'category={}'.format(category)
        elif request_type == constants.RETRIEVAL_NEARBY:
            # This query is already complex because of the distance search,
            # so may as well filter out the user here.
            query = ('distance(location, geopoint({}, {})) < {} AND '
                     'NOT user_id={}').format(
                lat, lng, self.user.distance_radius_km, self.user.key.id())
        elif request_type == constants.RETRIEVAL_SEARCH:
            # TODO: Revisit this, it looks totally insecure.
            # TODO: Add stemming.
            query = user_query
        else:
            self.populate_error_response(error_codes.GENERIC_ERROR,
                                         'Unimplemented')

        begin_search = True
        item_index = search.Index(constants.ITEM_INDEX_NAME)
        try:
            while (len(returned_results) < constants.NUM_ITEMS_PER_REQUEST and
                   (begin_search or cursor is not None)):
                begin_search = False
                search_response = item_index.search(
                    search.Query(query,
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
                        'title': document.field('title'),
                        'category': document.field('category'),
                        'description': document.field('description'),
                        'price': document.field('price'),
                        'currency': document.field('currency'),
                        'image': [i.url for i in item.image],
                    }
                    returned_results.append(item_dict)
                    if len(returned_results) == constants.NUM_ITEMS_PER_REQUEST:
                        break

        except search.Error as e:
            logging.error(
                'Item search failed for query="{}". Message: {}'.format(
                    query, e.message))
            self.populate_error_response(error_codes.SEARCH_ERROR, request_type)
            return

        self.populate_success_response(
            {'results': json.encode(returned_results),
             'cursor': cursor.web_safe_string()})

import json

from google.appengine.api import images
from google.appengine.ext import blobstore
from google.appengine.ext import ndb
from google.appengine.ext.webapp import blobstore_handlers

import error_codes
import instabuy_handler
import user_utils
import models


_NUM_ITEMS_PER_REQUEST = 5
_NUM_ITEMS_PER_PAGE = 50
_NUM_USERS_PER_PAGE = 300


class DefaultHandler(instabuy_handler.InstabuyHandler):
    def get(self):
        self.response.write('This is the default handler!')


class Register(instabuy_handler.InstabuyHandler):
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
    def get(self):
        ndb.delete_multi(models.User.query().fetch(keys_only=True))
        ndb.delete_multi(models.LikeState.query().fetch(keys_only=True))
        ndb.delete_multi(models.Item.query().fetch(keys_only=True))
        ndb.delete_multi(models.Image().query().fetch(keys_only=True))
        self.populate_success_response()


class GetImageUploadUrl(instabuy_handler.InstabuyHandler):
    def get(self):
        self.populate_success_response(
            {'upload_url': blobstore.create_upload_url('/upload_image')})


class UploadImage(blobstore_handlers.BlobstoreUploadHandler,
                  instabuy_handler.InstabuyHandler):
    def post(self):
        # Verify that the required parameters were supplied.
        fb_access_token = self.request.POST['fb_access_token']
        item_id = self.request.POST['item_id']
        if not (fb_access_token and item_id):
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
        image = models.Image(data=image_key,
                             path=images.get_serving_url(image_key))

        self.item.image.append(image)
        self.item.put()

        self.populate_success_response()


class PostItem(instabuy_handler.InstabuyHandler):
    def post(self):
        # Verify that the required parameters were supplied.
        fb_access_token = self.request.POST['fb_access_token']
        description = self.request.POST['description']
        price = self.request.POST['price']
        category = self.request.POST.getall('category')
        lat = self.request.POST['lat']
        lng = self.request.POST['lng']

        if not (fb_access_token and description and price and category and
                lat and lng):
            self.populate_error_response(error_codes.MALFORMED_REQUEST)
            return

        # Retrieve the user associated with the Facebook token.
        if not self.populate_user(fb_access_token):
            return

        item = models.Item(user_id=self.user.key(),
                           description=description,
                           price=price,
                           category=category,
                           location=ndb.GeoPt(lat, lng))
        item_key = item.put()

        self.populate_success_response({'item_id': item_key.id()})


class DeleteItem(instabuy_handler.InstabuyHandler):
    def get(self):
        # Verify that the required parameters were supplied.
        fb_access_token = self.request.get('fb_access_token')
        item_id = self.request.get('item_id')
        if not (fb_access_token and item_id):
            self.populate_error_response(error_codes.MALFORMED_REQUEST)
            return

        if not self.populate_user(fb_access_token):
            return

        if not self.populate_item_for_mutation(item_id):
            return

        # Delete all the likes/dislikes of this item by removing all the
        # LikedItemState objects that are mentioning this item.
        dislikes_query = models.LikeState.query(item_id == self.item.key,
                                                keys_only=True)
        ndb.delete_multi_async(dislikes_query)

        # Delete this item's id from all the seen_items lists of all users.
        users_query = models.User.query(seen_items == self.item.key.id())
        cursor = None
        more = True
        while more:
            users, cursor, more = users_query.fetch_page(
                _NUM_USERS_PER_PAGE, start_cusor=cursor)
            for user in users:
                # Delete the unique occurrence of the item's id in the
                # seen_items list.
                del user.seen_items[user.seen_items.index(self.item.key.id())]
            ndb.put_multi_async(users)

        # TODO: When chat is implemented, delete all the chat conversations
        # associated to this item as well.

        # Delete all the image data associated to this item.
        for image in self.item.image:
            images.delete_serving_url_async(image.data)
        blobstore.delete_async([image.data for image in self.item.image])

        # Delete the item itself.
        self.item.key.delete_async()
        self.populate_success_response()


class UpdateItemLikeState(instabuy_handler.InstabuyHandler):
    def get(self):
        # Verify that the required parameters were supplied.
        fb_access_token = self.request.get('fb_access_token')
        item_id = self.request.get('item_id')
        like_state = self.request.get('like_state')
        if not (fb_access_token and item_id and like_state):
            self.populate_error_response(error_codes.MALFORMED_REQUEST)
            return
        # Ensure that like_state is either 1 (like) or 0 (dislike).
        try:
            like_state = int(like_state)
        except ValueError:
            self.populate_error_response(error_codes.MALFORMED_REQUEST)
            return
        if like_state != 0 and like_state != 1:
            self.populate_error_response(error_codes.MALFORMED_REQUEST)
            return

        # Retrieve the relevant user and item objects.
        if not self.populate_user(fb_access_token):
            return
        if not self.populate_item(item_id):
            return

        # Check if we already recorded a like state for this user, item pair.
        # If it exists, simply update it, otherwise store a new one.
        query = models.LikeState.query(item_id == self.item.key)
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
    def get(self):
        # Verify that the required parameters were supplied.
        fb_access_token = self.request.get('fb_access_token')
        request_type = self.request.get('request_type')
        category = self.request.get('category')

        if not (fb_access_token and request_type):
            self.populate_error_response(error_codes.MALFORMED_REQUEST)
            return

        # If the request type is 'category', category must not be empty.
        if request_type == 'category' and not category:
            self.populate_error_response(error_codes.MALFORMED_REQUEST)
            return

        # Populate a set containing the ids of all the items that the user has
        # already seen. These need to be skipped.
        seen_items = set(self.user.seen_items)

        if request_type == 'category':
            # This will store the results
            results = []

            # All items that contain the desired category.
            query = models.Item.query(models.Item.category == category)
            cursor = None
            more = True
            while len(results) < _NUM_ITEMS_PER_REQUEST and more:
                items, cursor, more = query.fetch_page(_NUM_ITEMS_PER_PAGE,
                                                       start_cusor=cursor)
                for item in items:
                    if item.key.id not in seen_items:
                        results.append(item)
                    if len(results) == _NUM_ITEMS_PER_REQUEST:
                        break

            self.populate_success_response(
                {'results': json.dumps([r.to_dict() for r in results])})

        else:
            self.populate_error_response(error_codes.GENERIC_ERROR,
                                         'Unimplemented')

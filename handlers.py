from google.appengine.ext import blobstore
from google.appengine.ext import ndb
from google.appengine.ext.webapp import blobstore_handlers

import error_codes
import instabuy_handler
import user_utils
import models


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
        query = models.User.query(models.User.third_party_id == fb_user_id)
        query_iterator = query.iter()
        if query_iterator.has_next():
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
        self.item.image.append(image_key)
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

        item = models.Item(user_id=user.key(),
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
        dislikes_query = models.LikedItemState.query(
            models.LikedItemState.item_id == self.item.key)
        ndb.delete_multi([d.key for d in dislikes_query.iter()])

        # TODO: When chat is implemented, delete all the chat convos
        # associated to this item as well.

        # Delete all the images associated to this item.
        for image_key in self.item.image:
            blobstore.delete(image_key)

        # Delete the item itself.
        self.item.key.delete()

        self.populate_success_response()


class UpdateLikedItemState(instabuy_handler.InstabuyHandler):
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
        query = models.LikedItemState.query(
            models.LikedItemState.user_id == self.user.key and
            models.LikedItemState.item_id == self.item.key)
        query_iterator = query.iter()
        if query_iterator.has_next():
            liked_item_state = query_iterator.next()
            liked_item_state.like_state = bool(like_state)
            liked_item_state.put()
        else:
            liked_item_state = models.LikedItemState(
                user_id=self.user.key, item_id=self.item.key,
                like_state=bool(like_state))
            liked_item_state.put()
        self.populate_success_response()

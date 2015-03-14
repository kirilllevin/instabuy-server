import json
import httplib
import webapp2

from google.appengine.ext import blobstore
from google.appengine.ext import ndb
from google.appengine.ext.webapp import blobstore_handlers

import error_codes
import user_utils
import models


class InstabuyHandler(webapp2.RequestHandler):

    def populate_error_response(self, error_code, message=None):
        self.response.status_int = httplib.BAD_REQUEST
        error_response = json.dumps({'error': {'status': error_code.name,
                                               'error_code': error_code.code,
                                               'message': message}})
        self.response.write(json.dumps(error_response))

    def populate_success_response(self, response_dict={'success': True}):
        self.response.status_int = httplib.OK
        self.response.write(json.dumps(response_dict))

    def get_item_for_mutation(self, fb_access_token, item_id):
        """Get a models.Item that is allowed to be mutated.

        This verifies that the item_id is valid and that the user
        corresponding to the Facebook access token is the owner of that item.

        In case of failure, this method populates an error response.

        Args:
          fb_access_token: The Facebook access token of the user that
            (allegedly) owns this item.
          item_id: The id of the item to retrieve.

        Returns:
          (True, item), where item is the models. Item corresponding to
          item_id, if there were no problems, or (False, None) otherwise.
        """
        # Retrieve the user associated with the Facebook token.
        try:
            user = user_utils.get_user_key_from_facebook_token(fb_access_token)
        except user_utils.FacebookTokenExpiredException:
            self.populate_error_response(error_codes.FACEBOOK_TOKEN_ERROR)
            return False, None
        except user_utils.FacebookException as e:
            self.populate_error_response(error_codes.FACEBOOK_ERROR, e)
            return False, None

        # Retrieve the item associated with the item id.
        item_key = ndb.Key(models.Item, item_id)
        item = item_key.get()
        if not item:
            self.populate_error_response(error_codes.INVALID_ITEM)
            return False, None

        # Check that the user owns the item.
        if item.user_id != user.key:
            self.populate_error_response(error_codes.USER_PERMISSION_ERROR)
            return False, None

        return True, item


class DefaultHandler(InstabuyHandler):
    def get(self):
        self.response.write('This is the default handler!')


class Register(InstabuyHandler):
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
        user_key = user.put()
        self.populate_success_response()


class ClearAllEntry(InstabuyHandler):
    def get(self):
        ndb.delete_multi(models.User.query().fetch(keys_only=True))
        self.populate_success_response()


class GetImageUploadUrl(InstabuyHandler):
    def get(self):
        self.populate_success_response(
            {'upload_url': blobstore.create_upload_url('/upload_image')})


class UploadImage(blobstore_handlers.BlobstoreUploadHandler, InstabuyHandler):
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

        success, item = self.get_item_for_mutation(fb_access_token, item_id)
        if not success:
            # Delete the blob.
            blobstore.delete(image_key)

        # Append the image key to the item's list of images.
        item.image.append(image_key)
        item.put()

        self.populate_success_response()


class PostItem(InstabuyHandler):
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
        try:
            user = user_utils.get_user_key_from_facebook_token(fb_access_token)
        except user_utils.FacebookTokenExpiredException:
            self.populate_error_response(error_codes.FACEBOOK_TOKEN_ERROR)
            return
        except user_utils.FacebookException as e:
            self.populate_error_response(error_codes.FACEBOOK_ERROR, e)
            return

        item = models.Item(user_id=user.key(),
                           description=description,
                           price=price,
                           category=category,
                           location=ndb.GeoPt(lat, lng))
        item_key = item.put()

        self.populate_success_response({'item_id': item_key.id()})


class DeleteItem(InstabuyHandler):
    def get(self):
        # Verify that the required parameters were supplied.
        fb_access_token = self.request.get('fb_access_token')
        item_id = self.request.get('item_id')
        if not fb_access_token or not item_id:
            self.populate_error_response(error_codes.MALFORMED_REQUEST)
            return

        success, item = self.get_item_for_mutation(fb_access_token, item_id)

        if success:
            # Delete the item.
            item.key.delete()

            self.populate_success_response()
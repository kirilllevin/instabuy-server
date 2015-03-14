import json
import httplib
import webapp2

from google.appengine.ext import ndb

import error_codes
import user_utils
import models


class InstabuyHandler(webapp2.RequestHandler):
    def __init__(self, request, response):
        super(InstabuyHandler, self).__init__(request, response)
        self.user = None
        self.item = None

    def populate_error_response(self, error_code, message=None):
        self.response.status_int = httplib.BAD_REQUEST
        error_response = json.dumps({'error': {'status': error_code.name,
                                               'error_code': error_code.code,
                                               'message': message}})
        self.response.write(json.dumps(error_response))

    def populate_success_response(self, response_dict={'success': True}):
        self.response.status_int = httplib.OK
        self.response.write(json.dumps(response_dict))

    def populate_user(self, fb_access_token):
        """Load a models.User corresponding to a Facebook access token.

        The loaded user is stored in self.user.

        This verifies that there is indeed a user that corresponds to this
        access token.

        In case of failure, this method populates an error response.

        Args:
          fb_access_token: The Facebook access token.
        Returns:
          True if the populate succeeded, False otherwise.
        """
        # Use the token to get the Facebook user id.
        try:
            fb_user_id = user_utils.get_facebook_user_id(fb_access_token)
        except user_utils.FacebookTokenExpiredException:
            self.populate_error_response(error_codes.FACEBOOK_TOKEN_ERROR)
            return False
        except user_utils.FacebookException as e:
            self.populate_error_response(error_codes.FACEBOOK_ERROR, e)
            return False

        # Retrieve the User object for the given Facebook user id, if it exists.
        query = models.User.query(models.User.third_party_id == fb_user_id)
        query_iterator = query.iter()
        if query_iterator.has_next():
            self.user = query_iterator.next()

        if not self.user:
            # At this point, looks like there is no user with that id.
            self.populate_error_response(error_codes.INVALID_USER)
            return False

        return True

    def populate_item(self, item_id):
        """Load a models.Item corresponding to a given item id.

        The loaded item is stored in self.item.

        This verifies that there is indeed an item with the corresponding
        item id.

        In case of failure, this method populates an error response.

        Args:
          item_id: The id of the item to retrieve.
        Returns:
          True if the populate succeeded, False otherwise.
        """
        item_key = ndb.Key(models.Item, item_id)
        self.item = item_key.get()
        if not self.item:
            self.populate_error_response(error_codes.INVALID_ITEM)
            return False
        return True

    def populate_item_for_mutation(self, item_id):
        """Like populate_item() but with additional user ownership checks.

        This verifies that the item_id is valid and that the user that was
        loaded is the owner of that item. Requires that self.user was already
        populated.

        In case of failure, this method populates an error response.

        Args:
          item_id: The id of the item to retrieve.

        Returns:
          True if the populate succeeded, False otherwise.
        """
        assert self.user

        if not self.populate_item(item_id):
            return False

        # Check that the user owns the item.
        if self.item.user_id != self.user.key:
            self.populate_error_response(error_codes.USER_PERMISSION_ERROR)
            return False

        return True
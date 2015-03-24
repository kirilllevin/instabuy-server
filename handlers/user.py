from google.appengine.ext import ndb

import base
import error_codes
import models
import user_utils


class Register(base.BaseHandler):
    @ndb.toplevel
    def post(self):
        success = self.parse_request(
            {'fb_access_token': (str, True, None)})
        if not success:
            self.populate_error_response(error_codes.MALFORMED_REQUEST)
            return

        # Use the token to get the Facebook user id.
        try:
            fb_user_id = user_utils.get_facebook_user_id(
                self.args['fb_access_token'])
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
from google.appengine.ext import ndb

import base
import error_codes
import models
import user_utils


class Register(base.BaseHandler):
    @ndb.toplevel
    def post(self):
        success = self.parse_request(
            {'name': (str, True, None),
             'distance_radius_km': (int, False, lambda x: x > 0)})
        if not success:
            self.populate_error_response(error_codes.MALFORMED_REQUEST)
            return

        fb_access_token = self.request.headers.get('x-auth-token')

        # Use the token to get the Facebook user id.
        try:
            fb_user_id = user_utils.get_facebook_user_id(fb_access_token)
        except user_utils.FacebookTokenExpiredException:
            self.populate_error_response(error_codes.FACEBOOK_TOKEN_ERROR)
            return
        except user_utils.FacebookException as e:
            self.populate_error_response(error_codes.FACEBOOK_ERROR, e.error)
            return

        # Check if the user is already registered.
        user = models.User.query(models.User.third_party_id == fb_user_id).get()
        if user:
            self.populate_error_response(error_codes.ACCOUNT_EXISTS)
            return

        # Store a new user entry.
        user = models.User(login_type='facebook',
                           third_party_id=fb_user_id,
                           name=self.args['name'])
        if 'distance_radius_km' in self.args:
            user.distance_radius_km = self.args['distance_radius_km']
        user.put_async()
        self.populate_success_response()


class Update(base.BaseHandler):
    @ndb.toplevel
    def post(self):
        success = self.parse_request(
            {'name': (str, True, None),
             'distance_radius_km': (int, True, lambda x: x > 0)})
        if not success:
            self.populate_error_response(error_codes.MALFORMED_REQUEST)
            return

        if not self.populate_user():
            return

        # Update the user settings.
        self.user.name = self.args['name']
        self.user.distance_radius_km = self.args['distance_radius_km']
        self.user.put_async()

        self.populate_success_response()

import httplib
import webapp2
from webapp2_extras import json

import error_codes
import user_utils
import models


class BaseHandler(webapp2.RequestHandler):
    def __init__(self, request, response):
        super(BaseHandler, self).__init__(request, response)
        # All the responses are JSON.
        self.response.content_type = 'application/json'
        self.args = {}
        self.user = None
        self.item = None

    def parse_request(self, allowed_args):
        """Parse the parameters from the request into a dictionary.

        :param allowed_args: A dictionary from names of arguments to
          (type, required, validate) triples, where type is the builtin cast
          function for the expected type of the argument, required is a
          boolean indicating whether or not this arg is required, and validate
          is a lambda that enforces additional constraints on the value.
          Only these arguments are permitted.
        :return: True if the parse was successful, False if there were any
          errors in the supplied values.
        """
        if self.request.method == 'GET':
            args_dict = self.request.GET
        elif self.request.method == 'POST':
            # We expect all POST requests to be JSON.
            if self.request.content_type != 'application/json':
                return False
            args_dict = json.decode(self.request.body)
        else:
            return False
        seen_args = set()
        try:
            for arg_name, type_tuple in allowed_args.iteritems():
                t, required, validate = type_tuple
                if arg_name not in args_dict.keys():
                    if required:
                        return False
                    else:
                        continue
                # Try casting the value to the given type.
                if self.request.method == 'GET' and t is list:
                    value = args_dict.getall(arg_name)
                else:
                    value = t(args_dict[arg_name])
                # Run the validation function if it's present.
                if validate and not validate(value):
                    return False
                self.args[arg_name] = value
                seen_args.add(arg_name)
        except ValueError:
            return False
        # Final check to ensure that no additional params were supplied.
        # args_dict might be a MultiDict, so we need to collapse its keys to a
        # set.
        return len(seen_args) == len(set(args_dict.keys()))

    def populate_error_response(self, error_code, message=None):
        self.response.status_int = httplib.BAD_REQUEST
        error_dict = {'status': error_code.name,
                      'error_code': error_code.code}
        if message:
            error_dict['message'] = message
        self.response.write(json.encode({'status': httplib.BAD_REQUEST,
                                         'error': error_dict}))

    def populate_success_response(self, response_dict={}):
        self.response.status_int = httplib.OK
        full_dict = {'status': httplib.OK}
        full_dict.update(response_dict)
        self.response.write(json.encode(full_dict))

    def populate_user(self):
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
        fb_access_token = self.request.headers.get("x-auth-token")
        try:
            fb_user_id = user_utils.get_facebook_user_id(fb_access_token)
        except user_utils.FacebookTokenExpiredException:
            self.populate_error_response(error_codes.FACEBOOK_TOKEN_ERROR)
            return False
        except user_utils.FacebookException as e:
            self.populate_error_response(error_codes.FACEBOOK_ERROR, e.error)
            return False

        # Retrieve the User object for the given Facebook user id, if it exists.
        self.user = models.User.query(
            models.User.third_party_id == fb_user_id).get()
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
        self.item = models.Item.get_by_id(item_id)
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
        if self.item.user_key != self.user.key:
            self.populate_error_response(error_codes.USER_PERMISSION_ERROR)
            return False

        return True
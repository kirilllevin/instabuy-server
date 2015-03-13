import httplib
import response_utils
import user_utils
import models
import webapp2

from google.appengine.ext import ndb


class DefaultHandler(webapp2.RequestHandler):
    def get(self):
        self.response.write('This is the default handler!')


class Register(webapp2.RequestHandler):
    def get(self):
        fb_access_token = self.request.get('fb_access_token')

        # Use the token to get the Facebook user id.
        try:
            fb_user_id = user_utils.get_facebook_user_id(fb_access_token)
        except user_utils.FacebookTokenExpiredException:
            self.response.status_int = httplib.BAD_REQUEST
            self.response.write(response_utils.make_fb_token_expired_response())
            return
        except user_utils.FacebookException as e:
            self.response.write('Couldn\'t retrieve Facebook user ID. '
                                'Error: {}'.format(e))
            return

        # Check if the user is already registered.
        query = models.User.query(models.User.third_party_id == fb_user_id)
        query_iterator = query.iter()
        if query_iterator.has_next():
            self.response.write('Account already exists: key={}'.format(
                query_iterator.next().key))
            return

        # Store a new user entry.
        user = models.User(login_type='facebook',
                           third_party_id=fb_user_id)
        user_key = user.put()
        self.response.write('Registered new user: key={}user={}'.format(
            user_key, user))


class ClearAllEntry(webapp2.RequestHandler):
    def get(self):
        ndb.delete_multi(models.User.query().fetch(keys_only=True))
        self.response.write('Deleted all User entries.')


class PostItem(webapp2.RequestHandler):
    def get(self):
        fb_access_token = self.request.get('fb_access_token')

        # Retrieve the user associated with the Facebook token.
        try:
            user = user_utils.get_user_key_from_facebook_token(fb_access_token)
        except user_utils.FacebookTokenExpiredException:
            self.response.status_int = httplib.BAD_REQUEST
            self.response.write(response_utils.make_fb_token_expired_response())
            return
        except user_utils.FacebookException as e:
            self.response.write('Couldn\'t retrieve Facebook user ID. '
                                'Error: {}'.format(e))
            return

        # TODO: Finish this.

        self.response.write(
            'New entry with fb_access_token={}'.format(fb_access_token))


class DeleteItem(webapp2.RequestHandler):
    def get(self):
        fb_access_token = self.request.get('fb_access_token')
        item_id = self.request.get('item_id')

        # Retrieve the user associated with the Facebook token.
        try:
            user = user_utils.get_user_key_from_facebook_token(fb_access_token)
        except user_utils.FacebookTokenExpiredException:
            self.response.status_int = httplib.BAD_REQUEST
            self.response.write(response_utils.make_fb_token_expired_response())
            return
        except user_utils.FacebookException as e:
            self.response.write('Couldn\'t retrieve Facebook user ID. '
                                'Error: {}'.format(e))
            return

        # Retrieve the item associated with the item id.
        item_key = ndb.Key(models.Item, item_id)
        item = item_key.get()
        if not item:
            self.response.write('Invalid item id {}.'.format(item_id))
            return

        # Check that the user owns the item.
        if item.user_id != user.key():
            self.response.write('User doesn\'t own the item! user={}, '
                                'item={}'.format(user, item))
            return

        # Delete the item.
        item_key.delete()

        self.response.write(
            'Successfully deleted item: item_id={}'.format(item_id))
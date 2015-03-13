import httplib
import json
import models
from google.appengine.api import urlfetch


class FacebookException(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return repr(self.message)


def get_facebook_user_id(fb_access_token):
    response = urlfetch.fetch(
        'https://graph.facebook.com/v2.2/me?access_token=' +
        fb_access_token,
        validate_certificate=True)
    if response.status_code == httplib.OK:
        json_content = json.loads(response.content)
        return json_content['id']
    else:
        raise FacebookException(response.content)


def get_user_key_from_facebook_token(fb_access_token):
    # Use the token to get the Facebook user id.
    fb_user_id = get_facebook_user_id(fb_access_token)

    # Retrieve the User object for the given Facebook user id, if it exists.
    query = models.User.query(models.User.third_party_id == fb_user_id)
    query_iterator = query.iter()
    if query_iterator.has_next():
        return query_iterator.next()

    # At this point, looks like there is no user with that id.
    return None
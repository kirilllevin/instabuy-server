import httplib
import json
import models
from google.appengine.api import urlfetch


class FacebookException(Exception):
    """An exception in communicating with Facebook."""
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return repr(self.message)


class FacebookTokenExpiredException(Exception):
    """An exception raised when the Facebook token expired."""
    pass


def get_facebook_user_id(fb_access_token):
    """Retrieve a Facebook user id using a Facebook access token.

    Args:
      fb_access_token: The Facebook access token.
    Raises:
      FacebookTokenExpiredException: if the given token expired.
      FacebookException: if there was any other problem getting the Facebook
        user id using this token.
    Returns:
      The (app-specific) Facebook user id for the given user.
    """
    response = urlfetch.fetch(
        'https://graph.facebook.com/v2.2/me?access_token=' +
        fb_access_token,
        validate_certificate=True)
    if response.status_code == httplib.OK:
        json_content = json.loads(response.content)
        return json_content['id']
    elif response.status_code == httplib.BAD_REQUEST:
        error_message = json.loads(response.content)['error']

        # Specially handle an expired token, since this is likely.
        if (error_message['type'] == 'OAuthException' and
                error_message['code'] == 190 and
                error_message['error_subcode'] == 463):
            raise FacebookTokenExpiredException()

    # Wrap all other errors.
    raise FacebookException(response.content)


def get_user_key_from_facebook_token(fb_access_token):
    """Use a Facebook access token to retrieve a user key.

    Args:
      fb_access_token: The Facebook access token.
    Raises:
      FacebookTokenExpiredException: if the given token expired.
      FacebookException: if there was any other problem getting the Facebook
        user id using this token.
    Returns:
      A models.User key to the desired user.
    """
    # Use the token to get the Facebook user id.
    fb_user_id = get_facebook_user_id(fb_access_token)

    # Retrieve the User object for the given Facebook user id, if it exists.
    query = models.User.query(models.User.third_party_id == fb_user_id)
    query_iterator = query.iter()
    if query_iterator.has_next():
        return query_iterator.next()

    # At this point, looks like there is no user with that id.
    return None
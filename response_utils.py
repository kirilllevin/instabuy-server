import json


def make_fb_token_expired_response():
    """Create the response for when a Facebook token expired."""
    error = {
        'error': {
            'status': 'OAuthException',
            'error_code': 463,
        }
    }
    return json.dumps(error)
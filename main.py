#!/usr/bin/env python
import os
import webapp2
from webapp2 import Route


DEBUG = os.environ.get('SERVER_SOFTWARE', '').startswith('Dev')

routes = [
    Route(r'/', handler='handlers.DefaultHandler', name='default'),
    Route(r'/register', handler='handlers.Register', name='register'),
    Route(r'/post_item', handler='handlers.PostItem', name='post_item'),
    Route(r'/delete_item',
          handler='handlers.DeleteItem', name='delete_item'),
    Route(r'/clear_all', handler='handlers.ClearAllEntry', name='clear_all')
]

app = webapp2.WSGIApplication(routes, debug=DEBUG)

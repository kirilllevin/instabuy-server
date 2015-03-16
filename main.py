#!/usr/bin/env python
import os
import webapp2
from webapp2 import Route


DEBUG = os.environ.get('SERVER_SOFTWARE', '').startswith('Dev')

routes = [
    Route(r'/', handler='handlers.DefaultHandler', name='default'),

    # User registration.
    Route(r'/register', handler='handlers.Register', name='register'),

    # Item creation.
    Route(r'/post_item', handler='handlers.PostItem', name='post_item'),
    Route(r'/get_image_upload_url', handler='handlers.GetImageUploadUrl',
          name='get_image_upload_url'),
    Route(r'/upload_image', handler='handlers.UploadImage',
          name='upload_image'),

    # Item deletion.
    Route(r'/delete_item',
          handler='handlers.DeleteItem', name='delete_item'),

    # Liking and disliking of items.
    Route(r'/update_item_like_state', handler='handlers.UpdateItemLikeState',
          name='update_item_like_state'),

    # Retrieving items for display to users.
    Route(r'/get_items', handler='handlers.GetItems', name='get_items'),

    # Administrative, for development.
    Route(r'/clear_all', handler='handlers.ClearAllEntry', name='clear_all')
]

app = webapp2.WSGIApplication(routes, debug=DEBUG)

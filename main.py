#!/usr/bin/env python
import os
import webapp2
from webapp2 import Route


DEBUG = os.environ.get('SERVER_SOFTWARE', '').startswith('Dev')

routes = [
    # User registration.
    Route(r'/user/auth', handler='handlers.user.Authenticate', name='auth'),
    Route(r'/user/update', handler='handlers.user.Update', name='update'),

    # Item creation.
    Route(r'/item/post', handler='handlers.item.Post', name='post'),
    Route(r'/item/image/upload_url', handler='handlers.image.GetUploadUrl',
          name='upload_url'),
    Route(r'/item/image/upload', handler='handlers.image.Upload',
          name='upload'),

    # Item deletion.
    Route(r'/item/delete', handler='handlers.item.Delete', name='delete'),

    # Liking and disliking of items.
    Route(r'/item/like', handler='handlers.like_state.Post', name='like'),

    # Retrieving items for display to users.
    Route(r'/item/list', handler='handlers.item.List', name='list'),

    # Chatting.
    Route(r'/chat/post', handler='handlers.conversation.Post', name='post'),

    # Polling for updates.
    Route(r'/updates', handler='handlers.updates.List', name='updates'),

    # Administrative, for development.
    Route(r'/clear_all', handler='handlers.handlers.ClearAllEntry',
          name='clear_all')
]

app = webapp2.WSGIApplication(routes, debug=DEBUG)

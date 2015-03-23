from google.appengine.ext import ndb

import base
import models

# TODO: Get rid of these once the server is considered fully functional.


class DefaultHandler(base.BaseHandler):
    def get(self):
        self.response.write('This is the default handler!')


class ClearAllEntry(base.BaseHandler):
    @ndb.toplevel
    def post(self):
        ndb.delete_multi(models.User.query().fetch(keys_only=True))
        ndb.delete_multi(models.LikeState.query().fetch(keys_only=True))
        ndb.delete_multi(models.Item.query().fetch(keys_only=True))
        ndb.delete_multi(models.Image().query().fetch(keys_only=True))
        self.populate_success_response()

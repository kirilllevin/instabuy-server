from google.appengine.ext import ndb

import error_codes
import base
import models


class Update(base.BaseHandler):
    @ndb.toplevel
    def post(self):
        success = self.parse_request(
            {'fb_access_token': (str, True, None),
             'item_id':    (long, True, None),
             'like_state': (int, True, lambda x: x == 0 or x == 1)})
        if not success:
            self.populate_error_response(error_codes.MALFORMED_REQUEST)
            return

        # Retrieve the relevant user and item objects.
        if not self.populate_user(self.args['fb_access_token']):
            return
        if not self.populate_item(self.args['item_id']):
            return

        # Check if we already recorded a like state for this user, item pair.
        # If it exists, simply update it, otherwise store a new one.
        query = models.LikeState.query(
            models.LikeState.item_id == self.item.key)
        item_like_state = query.filter(
            models.LikeState.user_id == self.user.key).get()
        if item_like_state:
            item_like_state.like_state = bool(self.args['like_state'])
        else:
            item_like_state = models.LikeState(
                parent=self.item.key,
                user_id=self.user.key,
                like_state=bool(self.args['like_state']))
            # Mark that the user has now seen this item.
            self.user.seen_items.append(self.item.key.id())
            self.user.put_async()
        item_like_state.put_async()
        self.populate_success_response()



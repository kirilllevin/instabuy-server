from google.appengine.ext import ndb

import error_codes
import base
import models


class Post(base.BaseHandler):
    @ndb.toplevel
    def post(self):
        success = self.parse_request(
            {'item_id':    (long, True, None),
             'like_state': (int, True, lambda x: x == 0 or x == 1)})
        if not success:
            self.populate_error_response(error_codes.MALFORMED_REQUEST)
            return

        # Retrieve the relevant user and item objects.
        if not self.populate_user():
            return
        if not self.populate_item(self.args['item_id']):
            return

        entities_to_update = []

        # Check if we already recorded a like state for this user, item pair.
        # If it exists, simply update it, otherwise store a new one.
        query = models.LikeState.query(
            models.LikeState.item_key == self.item.key)
        item_like_state = query.filter(
            models.LikeState.user_key == self.user.key).get()
        if item_like_state:
            item_like_state.like_state = bool(self.args['like_state'])
        else:
            item_like_state = models.LikeState(
                item_key=self.item.key,
                user_key=self.user.key,
                like_state=bool(self.args['like_state']))
            # Mark that the user has now seen this item.
            self.user.seen_item_ids.append(self.item.key.id())
            entities_to_update.append(self.user)
        entities_to_update.append(item_like_state)
        ndb.put_multi_async(entities_to_update)
        self.populate_success_response()



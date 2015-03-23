from google.appengine.ext import ndb

import error_codes
import base
import models


class Update(base.BaseHandler):
    @ndb.toplevel
    def post(self):
        # Verify that the required parameters were supplied.
        fb_access_token = self.request.POST['fb_access_token']
        item_id = self.request.POST['item_id']
        like_state = self.request.POST['like_state']

        malformed_request = False
        try:
            if not (fb_access_token and item_id and like_state):
                malformed_request = True
            else:
                like_state = int(like_state)
                item_id = long(item_id)
                # Ensure that like_state is either 1 (like) or 0 (dislike).
                if like_state != 0 and like_state != 1:
                    malformed_request = True
        except ValueError:
            malformed_request = True
        if malformed_request:
            self.populate_error_response(error_codes.MALFORMED_REQUEST)
            return

        # Retrieve the relevant user and item objects.
        if not self.populate_user(fb_access_token):
            return
        if not self.populate_item(item_id):
            return

        # Check if we already recorded a like state for this user, item pair.
        # If it exists, simply update it, otherwise store a new one.
        query = models.LikeState.query(
            models.LikeState.item_id == self.item.key)
        item_like_state = query.filter(
            models.LikeState.user_id == self.user.key).get()
        if item_like_state:
            item_like_state.like_state = bool(like_state)
        else:
            item_like_state = models.LikeState(
                parent=self.item.key,
                user_id=self.user.key,
                like_state=bool(like_state))
            # Mark that the user has now seen this item.
            self.user.seen_items.append(self.item.key.id())
            self.user.put_async()
        item_like_state.put_async()
        self.populate_success_response()



from google.appengine.ext import ndb

import error_codes
import base
import models


class Post(base.BaseHandler):
    @ndb.toplevel
    def post(self):
        success = self.parse_request(
            {'item_id': (long, True, None),
             'receiver_id': (long, True, None),
             'message': (str, True, lambda x: len(x) > 0)})
        if not success:
            self.populate_error_response(error_codes.MALFORMED_REQUEST)
            return

        # Load the current user and the item in question.
        if not (self.populate_user() and
                self.populate_item(self.args['item_id'])):
            return

        # We can skip checking that the receiver_id corresponds to a real
        # user because the checks below implicitly do that.
        # Specifically, either the receiver owns the item (and hence exists),
        # or there is a conversation that includes him as the first
        # sender, so recursively, that user must've sent a message at some
        # point (and hence exists).
        receiver_key = ndb.Key(models.User, self.args['receiver_id'])

        if self.item.user_key == self.user.key:
            buyer_key = receiver_key
        else:
            buyer_key = self.user.key
            # Ensure that the receiver is really the item owner.
            if self.item.user_key != receiver_key:
                self.populate_error_response(error_codes.INVALID_USER)
                return
        # Grab the conversation between the sender and receiver for this
        # item, if it already exists. Since the seller is determined by the
        # item, we only need to keep track of the buyer.
        conversation = models.Conversation.query(
            models.Conversation.item_key == self.item.key,
            models.Conversation.buyer_key == buyer_key).get()

        # If there is no conversation, double check that the sender is the
        # buyer, to ensure that sellers can't spam people.
        # Also check that the sender liked the item.
        added_new_conversation = False
        if not conversation:
            if buyer_key != self.user.key:
                self.populate_error_response(error_codes.MALFORMED_REQUEST)
                return
            # First, do the cheaper check to see that the user has even seen
            # this item.
            if self.item.key.id() not in self.user.seen_item_ids:
                self.populate_error_response(error_codes.INVALID_ITEM)
                return
            # Now do the more expensive check to see that the user actually
            # liked the item.
            query = models.LikeState.query(
                models.LikeState.item_key == self.item.key)
            item_like_state = query.filter(
                models.LikeState.user_key == self.user.key).get()
            if not item_like_state or not item_like_state.like_state:
                self.populate_error_response(error_codes.INVALID_ITEM)
                return
            # Finally, it's safe to create the conversation.
            conversation = models.Conversation(item_key=self.item.key,
                                               buyer_key=buyer_key)
            added_new_conversation = True

        # Create the message and append it to the end of the conversation.
        message = models.Message(user_key=self.user.key,
                                 user_name=self.user.name,
                                 message=self.args['message'])
        conversation.messages.append(message)
        conversation_key = conversation.put()

        if added_new_conversation:
            # This only happens when the current user is the buyer,
            # so we need to also refetch and update the seller.
            self.user.ongoing_conversations.append(conversation_key.id())
            other_user = receiver_key.get()
            other_user.ongoing_conversations.append(conversation_key.id())
            ndb.put_multi_async([self.user, other_user])

        # TODO: Push the message to the receiver here.

        self.populate_success_response()

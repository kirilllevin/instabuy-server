import datetime
from google.appengine.ext import ndb

import base
import constants
import error_codes
import models

_EPOCH_START = datetime.datetime(1970, 1, 1)


class List(base.BaseHandler):
    @ndb.toplevel
    def get(self):
        # Grab a timestamp first, before we do anything, to ensure that we
        # don't accidentally lose any time between retrieving data and
        # storing the next cutoff timestamp.
        now = datetime.datetime.utcnow()

        success = self.parse_request(
            {'item_ids': (list, False, lambda x: len(x) < constants.MAX_ITEMS)})
        # We need to do some more processing since we want to ensure the
        # item_ids list contains longs.
        item_ids_to_check = []
        if success and 'item_ids' in self.args:
            try:
                item_ids_to_check = [long(i) for i in self.args['item_ids']]
            except ValueError:
                success = False
        if not success:
            self.populate_error_response(error_codes.MALFORMED_REQUEST)
            return

        # Load the current user.
        if not self.populate_user():
            return

        # Don't let people query for random item ids. Ensure that only the
        # ones that the user has seen can be checked.
        if not set(item_ids_to_check).issubset(self.user.seen_item_ids):
            self.populate_error_response(error_codes.INVALID_ITEM)
            return

        # Get all the new messages since the last check-in.
        messages = []
        conversations = ndb.get_multi([ndb.Key(models.Conversation, c) for c in
                                       self.user.ongoing_conversations])
        for conversation in conversations:
            # Skip all conversations that predate the user's last activity.
            if conversation.last_activity_date <= self.user.last_active:
                continue
            for message in conversation.messages:
                # Skip all the messages that predate the user's last activity.
                if message.create_date <= self.user.last_active:
                    continue
                timestamp = (message.create_date - _EPOCH_START).total_seconds()
                messages.append(
                    {'user_name': message.user_name,
                     'message': message.message,
                     'item_id': conversation.item_key.id(),
                     'date_sent': str(message.create_date),
                     'timestamp': timestamp})

        # Check which of the provided items have been deleted by retrieving
        # them, then listing the ones that didn't get retrieved.
        deleted_item_ids = []
        items = ndb.get_multi(
            [ndb.Key(models.Item, i) for i in item_ids_to_check])
        for i in range(0, len(items)):
            if not items[i]:
                deleted_item_ids.append(item_ids_to_check[i])

        response_dict = {'messages': messages,
                         'deleted': deleted_item_ids}

        # Update the last_active timestamp.
        self.user.last_active = now
        self.user.put_async()

        self.populate_success_response(response_dict)

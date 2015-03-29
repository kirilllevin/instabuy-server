import datetime
from google.appengine.ext import ndb
import httplib
from webapp2_extras import json

import error_codes
import models
import test_utils

_EPOCH_START = datetime.datetime(1970, 1, 1)


class ListTest(test_utils.HandlerTest):
    def setUp(self):
        super(ListTest, self).setUp()

        seen_item_ids = []
        ongoing_conversations = []

        other_user = ndb.Key(models.User, self.user_key.id() + 1)

        # Another user's item that this user liked, but which has been deleted.
        deleted_item = models.Item(user_key=other_user)
        self.deleted_item_key = deleted_item.put()
        like_state = models.LikeState(user_key=self.user_key,
                                      item_key=self.deleted_item_key,
                                      like_state=True)
        like_state.put()
        seen_item_ids.append(self.deleted_item_key.id())
        self.deleted_item_key.delete()

        # Another user's item that this user is having a conversation about,
        # but nothing changed since last time..
        new_item_a = models.Item(user_key=other_user)
        self.new_item_a_key = new_item_a.put()
        like_state_a = models.LikeState(user_key=self.user_key,
                                        item_key=self.new_item_a_key,
                                        like_state=True)
        like_state_a.put()
        seen_item_ids.append(self.new_item_a_key.id())
        conversation_a = models.Conversation(
            item_key=self.new_item_a_key,
            buyer_key=self.user_key,
            messages=[
                models.Message(user_key=self.user_key,
                               user_name='test_user',
                               message='first_a',
                               create_date=_EPOCH_START)],
        )
        conversation_a_key = conversation_a.put()
        ongoing_conversations.append(conversation_a_key.id())

        # Another user's item that this user is having a conversation about,
        # and which has two new messages.
        new_item_b = models.Item(user_key=other_user)
        self.new_item_b_key = new_item_b.put()
        like_state_b = models.LikeState(user_key=self.user_key,
                                        item_key=self.new_item_b_key,
                                        like_state=True)
        like_state_b.put()
        seen_item_ids.append(self.new_item_b_key.id())
        b_datetime = datetime.datetime.utcnow()
        b_timestamp = (b_datetime - _EPOCH_START).total_seconds()
        conversation_b = models.Conversation(
            item_key=self.new_item_b_key,
            buyer_key=self.user_key,
            messages=[
                models.Message(user_key=self.user_key,
                               user_name='test_user',
                               message='first_b',
                               create_date=_EPOCH_START),
                models.Message(user_key=other_user,
                               user_name='other_user',
                               message='response_b_1',
                               create_date=b_datetime),
                models.Message(user_key=other_user,
                               user_name='other_user',
                               message='response_b_2',
                               create_date=b_datetime)],
        )
        conversation_b_key = conversation_b.put()
        ongoing_conversations.append(conversation_b_key.id())

        self.expected_messages = [
            {u'user_name': u'other_user',
             u'message': u'response_b_1',
             u'item_id': long(self.new_item_b_key.id()),
             u'date_sent': unicode(b_datetime),
             u'timestamp': b_timestamp},
            {u'user_name': u'other_user',
             u'message': u'response_b_2',
             u'item_id': long(self.new_item_b_key.id()),
             u'date_sent': unicode(b_datetime),
             u'timestamp': b_timestamp}
        ]

        self.user.seen_item_ids = seen_item_ids
        self.user.ongoing_conversations = ongoing_conversations
        self.user.last_active = datetime.datetime(2000, 1, 1)
        self.user.put()

    def test_deleted_items(self):
        response = self.app.get(
            '/updates',
            params={'item_ids': [self.deleted_item_key.id(),
                                 self.new_item_a_key.id(),
                                 self.new_item_b_key.id()]},
            headers=self.headers_for_user(self.user.third_party_id))
        self.assertEqual(httplib.OK, response.status_int)
        deleted = json.decode(response.body)['deleted']
        self.assertEqual([self.deleted_item_key.id()], deleted)

    def test_deleted_must_be_seen(self):
        # Remove the deleted_item_key from the list of items this user has seen.
        deleted_item_index = self.user.seen_item_ids.index(
            self.deleted_item_key.id())
        del self.user.seen_item_ids[deleted_item_index]
        self.user.put()
        response = self.app.get(
            '/updates',
            params={'item_ids': [self.deleted_item_key.id(),
                                 self.new_item_a_key.id(),
                                 self.new_item_b_key.id()]},
            headers=self.headers_for_user(self.user.third_party_id),
            expect_errors=True)
        self.assertEqual(httplib.BAD_REQUEST, response.status_int)
        response_body = json.decode(response.body)
        self.assertEqual(error_codes.INVALID_ITEM.code,
                         response_body['error']['error_code'])

    def test_new_messages(self):
        response = self.app.get(
            '/updates',
            headers=self.headers_for_user(self.user.third_party_id))
        self.assertEqual(httplib.OK, response.status_int)
        messages = json.decode(response.body)['messages']
        self.assertListEqual(self.expected_messages, messages)


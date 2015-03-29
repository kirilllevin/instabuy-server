from google.appengine.ext import ndb
import httplib
from webapp2_extras import json

import error_codes
import models
import test_utils


class PostTest(test_utils.HandlerTest):
    def setUp(self):
        super(PostTest, self).setUp()

        # Another user, who is selling an item.
        self.second_user = models.User(login_type='facebook',
                                       third_party_id='2',
                                       name='second_name',
                                       distance_radius_km=10)
        self.second_user.put()

        # An item owned by second_user.
        self.item = models.Item(user_key=self.second_user.key)
        self.item.put()

        # One more user that likes the above item.
        self.third_user = models.User(login_type='facebook',
                                      third_party_id='3',
                                      name='third_name',
                                      distance_radius_km=10,
                                      seen_item_ids=[self.item.key.id()])
        self.third_user.put()
        third_user_like_state = models.LikeState(item_key=self.item.key,
                                                 user_key=self.third_user.key,
                                                 like_state=True)
        third_user_like_state.put()

        # The test user also likes this item.
        self.user.seen_item_ids.append(self.item.key.id())
        self.user.put()
        self.user_like_state = models.LikeState(item_key=self.item.key,
                                                user_key=self.user.key,
                                                like_state=True)
        self.user_like_state.put()

    def test_buyer_must_be_first_message(self):
        # second_user owns the item and there is no convo between him and the
        # test user about this item, so second_user can't chat to the test
        # user.
        self.assertEqual(self.second_user.key, self.item.user_key)
        response = self.app.post(
            '/chat/post',
            params=json.encode({'item_id': self.item.key.id(),
                                'receiver_id': self.user_key.id(),
                                'message': 'test_message'}),
            headers=self.headers_for_user(self.second_user.third_party_id),
            expect_errors=True)
        self.assertEqual(httplib.BAD_REQUEST, response.status_int)
        response_body = json.decode(response.body)
        self.assertEqual(error_codes.MALFORMED_REQUEST.code,
                         response_body['error']['error_code'])

    def test_seller_must_be_in_conversation(self):
        # second_user owns the item, so the test user shouldn't be able to
        # chat with third_user about it.
        self.assertEqual(self.second_user.key, self.item.user_key)

        response = self.app.post(
            '/chat/post',
            params=json.encode({'item_id': self.item.key.id(),
                                'receiver_id': self.third_user.key.id(),
                                'message': 'test_message'}),
            headers=self.headers_for_user(self.user.third_party_id),
            expect_errors=True)
        self.assertEqual(httplib.BAD_REQUEST, response.status_int)
        response_body = json.decode(response.body)
        self.assertEqual(error_codes.INVALID_USER.code,
                         response_body['error']['error_code'])

    def test_buyer_must_have_seen_item(self):
        self.user.seen_item_ids = []
        self.user.put()
        response = self.app.post(
            '/chat/post',
            params=json.encode({'item_id': self.item.key.id(),
                                'receiver_id': self.second_user.key.id(),
                                'message': 'test_message'}),
            headers=self.headers_for_user(self.user.third_party_id),
            expect_errors=True)
        self.assertEqual(httplib.BAD_REQUEST, response.status_int)
        response_body = json.decode(response.body)
        self.assertEqual(error_codes.INVALID_ITEM.code,
                         response_body['error']['error_code'])

    def test_buyer_must_like_item(self):
        self.user_like_state.like_state = False
        self.user_like_state.put()
        response = self.app.post(
            '/chat/post',
            params=json.encode({'item_id': self.item.key.id(),
                                'receiver_id': self.second_user.key.id(),
                                'message': 'test_message'}),
            headers=self.headers_for_user(self.user.third_party_id),
            expect_errors=True)
        self.assertEqual(httplib.BAD_REQUEST, response.status_int)
        response_body = json.decode(response.body)
        self.assertEqual(error_codes.INVALID_ITEM.code,
                         response_body['error']['error_code'])

        self.user_like_state.key.delete()
        self.assertIsNone(self.user_like_state.key.get())
        response = self.app.post(
            '/chat/post',
            params=json.encode({'item_id': self.item.key.id(),
                                'receiver_id': self.second_user.key.id(),
                                'message': 'test_message'}),
            headers=self.headers_for_user(self.user.third_party_id),
            expect_errors=True)
        self.assertEqual(httplib.BAD_REQUEST, response.status_int)
        response_body = json.decode(response.body)
        self.assertEqual(error_codes.INVALID_ITEM.code,
                         response_body['error']['error_code'])

    def test_new_conversation(self):
        response = self.app.post(
            '/chat/post',
            params=json.encode({'item_id': self.item.key.id(),
                                'receiver_id': self.second_user.key.id(),
                                'message': 'test_message'}),
            headers=self.headers_for_user(self.user.third_party_id))
        self.assertEqual(httplib.OK, response.status_int)

        # Check that the conversation was created and the message was recorded
        # properly.
        conversation = models.Conversation.query(
            models.Conversation.item_key == self.item.key,
            models.Conversation.buyer_key == self.user.key).get()
        self.assertIsNotNone(conversation)
        self.assertEqual(1, len(conversation.messages))
        message = conversation.messages[0]
        self.assertEqual(self.user.key, message.user_key)
        self.assertEqual('test_message', message.message)
        self.assertEqual('test_name', message.user_name)

        # Check that both the test user and second_user now have the
        # conversation in their lists of ongoing conversations.
        # We need to refetch both user objects, since they were updated.
        self.user = self.user.key.get()
        self.second_user = self.second_user.key.get()
        self.assertListEqual([conversation.key.id()],
                             self.user.ongoing_conversations)
        self.assertListEqual([conversation.key.id()],
                             self.second_user.ongoing_conversations)

    def test_seller_response(self):
        # Test user sends a message to second_user about the item.
        response = self.app.post(
            '/chat/post',
            params=json.encode({'item_id': self.item.key.id(),
                                'receiver_id': self.second_user.key.id(),
                                'message': 'test_message'}),
            headers=self.headers_for_user(self.user.third_party_id))
        self.assertEqual(httplib.OK, response.status_int)

        # Now second_user should be able to respond.
        response = self.app.post(
            '/chat/post',
            params=json.encode({'item_id': self.item.key.id(),
                                'receiver_id': self.user_key.id(),
                                'message': 'response'}),
            headers=self.headers_for_user(self.second_user.third_party_id))
        self.assertEqual(httplib.OK, response.status_int)

        # Check that the conversation was created and the messages were recorded
        # properly.
        conversation = models.Conversation.query(
            models.Conversation.item_key == self.item.key,
            models.Conversation.buyer_key == self.user.key).get()
        self.assertIsNotNone(conversation)
        self.assertEqual(2, len(conversation.messages))
        self.assertEqual('test_message', conversation.messages[0].message)
        self.assertEqual('response', conversation.messages[1].message)

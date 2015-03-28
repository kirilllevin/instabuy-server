from google.appengine.ext import ndb
import httplib
from webapp2_extras import json

import models
import test_utils


class PostTest(test_utils.HandlerTest):
    def setUp(self):
        super(PostTest, self).setUp()

        # Set up an item not owned by the user.
        item = models.Item(
            user_key=ndb.Key(models.User, self.user_key.id() + 1))
        self.item_key = item.put()

    def get_like_state(self):
        query = models.LikeState.query(
            models.LikeState.item_key == self.item_key)
        return query.filter(models.LikeState.user_key == self.user.key).get()

    def test_add_like(self):
        self.assertListEqual([], self.user.seen_item_ids)

        response = self.app.post(
            '/item/like',
            params=json.encode({'item_id': self.item_key.id(),
                                'like_state': 1}),
            headers=self.headers_for_user(self.user.third_party_id))
        self.assertEqual(httplib.OK, response.status_int)
        like_state = self.get_like_state()
        self.assertIsNotNone(like_state)
        self.assertTrue(like_state.like_state)
        # Refetch the user to make sure we have a fresh state, and ensure
        # that the item id was added to the seen items list.
        self.user = self.user_key.get()
        self.assertListEqual([self.item_key.id()], self.user.seen_item_ids)

    def test_add_dislike(self):
        self.assertListEqual([], self.user.seen_item_ids)

        response = self.app.post(
            '/item/like',
            params=json.encode({'item_id': self.item_key.id(),
                                'like_state': 0}),
            headers=self.headers_for_user(self.user.third_party_id))
        self.assertEqual(httplib.OK, response.status_int)
        like_state = self.get_like_state()
        self.assertIsNotNone(like_state)
        self.assertFalse(like_state.like_state)
        # Refetch the user to make sure we have a fresh state, and ensure
        # that the item id was added to the seen items list.
        self.user = self.user_key.get()
        self.assertListEqual([self.item_key.id()], self.user.seen_item_ids)

    def test_update(self):
        self.assertListEqual([], self.user.seen_item_ids)

        response = self.app.post(
            '/item/like',
            params=json.encode({'item_id': self.item_key.id(),
                                'like_state': 1}),
            headers=self.headers_for_user(self.user.third_party_id))
        self.assertEqual(httplib.OK, response.status_int)
        like_state = self.get_like_state()
        self.assertIsNotNone(like_state)
        self.assertTrue(like_state.like_state)

        # Refetch the user to make sure we have a fresh state, and ensure
        # that the item id was added to the seen items list.
        self.user = self.user_key.get()
        self.assertListEqual([self.item_key.id()], self.user.seen_item_ids)

        response = self.app.post(
            '/item/like',
            params=json.encode({'item_id': self.item_key.id(),
                                'like_state': 0}),
            headers=self.headers_for_user(self.user.third_party_id))
        self.assertEqual(httplib.OK, response.status_int)
        like_state = self.get_like_state()
        self.assertIsNotNone(like_state)
        self.assertFalse(like_state.like_state)
        # Refetch the user to make sure we have a fresh state, and ensure
        # that the list is still the same.
        self.user = self.user_key.get()
        self.assertListEqual([self.item_key.id()], self.user.seen_item_ids)
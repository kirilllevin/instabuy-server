from google.appengine.ext import ndb


class User(ndb.Model):
    # The type of login being used. Currently, only 'facebook' is allowed.
    login_type = ndb.StringProperty(required=True)

    # This user's ID in a third-party login system (e.g. Facebook). For a given
    # login_type value, these must be unique.
    third_party_id = ndb.StringProperty()

    # The user's name, as displayed in chat messages.
    name = ndb.StringProperty(indexed=False)

    # The user's preference for the distance radius when searching for nearby
    # items.
    distance_radius_km = ndb.IntegerProperty(default=10, indexed=False)

    # All the currently-live items that the user has seen.
    seen_item_ids = ndb.IntegerProperty(repeated=True)

    # All the ongoing conversations that this user is part of.
    ongoing_conversations = ndb.IntegerProperty(repeated=True)

    # The last time this user pinged for status.
    last_active = ndb.DateTimeProperty(auto_now_add=True, indexed=False)


class Image(ndb.Model):
    # The key for the actual image data in Blobstore.
    blob_key = ndb.BlobKeyProperty(indexed=False)

    # The path to the data, from calling get_serving_url().
    url = ndb.TextProperty()


class Item(ndb.Model):
    # The key for the user that owns this item.
    user_key = ndb.KeyProperty(User, indexed=True)

    # The time/date that this item was created.
    create_date = ndb.DateTimeProperty(auto_now_add=True, indexed=True)

    # The time/date that this item was last modified.
    modify_date = ndb.DateTimeProperty(auto_now=True, indexed=False)

    # The list of images associated to this item. Limited to 5 in the app.
    image = ndb.StructuredProperty(Image, repeated=True, indexed=False)


class LikeState(ndb.Model):
    # The user that liked/disliked the item.
    user_key = ndb.KeyProperty(User, indexed=True)

    # The item that is liked/disliked.
    item_key = ndb.KeyProperty(Item, indexed=True)

    # Whether or not this is a like or dislike.
    like_state = ndb.BooleanProperty(indexed=True)


class Message(ndb.Model):
    # The key for the user that sent this message.
    user_key = ndb.KeyProperty(User, indexed=True)

    # The name of the user, which is taken from the 'name' field in the User
    # object. This is stored here for denormalization.
    user_name = ndb.StringProperty(indexed=False)

    # The contents of the message.
    message = ndb.TextProperty()

    # The time/date that this message was created.
    create_date = ndb.DateTimeProperty(auto_now_add=True, indexed=True)


class Conversation(ndb.Model):
    # The key for the item this conversation corresponds to.
    item_key = ndb.KeyProperty(Item, indexed=True)

    # The key for the user that wants to buy the item.
    buyer_key = ndb.KeyProperty(User, indexed=True)

    # The ordered list of messages in this conversation.
    messages = ndb.StructuredProperty(Message, repeated=True, indexed=False)

    # The last time anything happened in this conversation.
    last_activity_date = ndb.DateTimeProperty(auto_now=True, indexed=False)

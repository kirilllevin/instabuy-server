from google.appengine.ext import ndb


class User(ndb.Model):
    # The type of login being used. Currently, only 'facebook' is allowed.
    login_type = ndb.StringProperty(required=True, indexed=True)

    # This user's ID in a third-party login system (e.g. Facebook). For a given
    # login_type value, these must be unique.
    third_party_id = ndb.StringProperty(indexed=True)


class Item(ndb.Model):
    # The user ID that owns this item.
    user_id = ndb.KeyProperty(User, indexed=True)

    # The time/date that this item was created.
    create_date = ndb.DateTimeProperty(auto_now_add=True)

    # The time/date that this item was last modified.
    modify_date = ndb.DateTimeProperty(auto_now=True)

    # Is this an active item?
    active = ndb.BooleanProperty(default=True)

    # The textual description supplied by the user.
    description = ndb.TextProperty()

    # The price of the item. Formatted in the app.
    price = ndb.TextProperty()

    # The categories that this item is part of.
    category = ndb.TextProperty(repeated=True)

    # The list of images associated to this item. Limited to 5 in the app.
    image = ndb.BlobKeyProperty(repeated=True)

    # The user's lat/lng when this item was created.
    location = ndb.GeoPtProperty()


class LikedItemState(ndb.Model):
    # The user that liked/disliked the item.
    user_id = ndb.KeyProperty(User, indexed=True)

    # The item that was liked/disliked by the user.
    item_id = ndb.KeyProperty(Item, indexed=True)

    # Whether or not this is a like or dislike.
    like_state = ndb.BooleanProperty()

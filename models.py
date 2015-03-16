from google.appengine.ext import ndb


class User(ndb.Model):
    # The type of login being used. Currently, only 'facebook' is allowed.
    login_type = ndb.StringProperty(required=True)

    # This user's ID in a third-party login system (e.g. Facebook). For a given
    # login_type value, these must be unique.
    third_party_id = ndb.StringProperty()

    # All the currently-live items that the user has seen.
    seen_items = ndb.IntegerProperty(repeated=True)


class Image(ndb.Model):
    # The actual image data.
    data = ndb.BlobKeyProperty(indexed=False)

    # The path to the data, from calling get_serving_url().
    path = ndb.TextProperty()


class Item(ndb.Model):
    # The user ID that owns this item.
    user_id = ndb.KeyProperty(User, indexed=True)

    # The time/date that this item was created.
    create_date = ndb.DateTimeProperty(auto_now_add=True, indexed=True)

    # The time/date that this item was last modified.
    modify_date = ndb.DateTimeProperty(auto_now=True, indexed=False)

    # The title of the item.
    title = ndb.TextProperty()

    # The textual description supplied by the user.
    description = ndb.TextProperty()

    # The price of the item. Formatted in the app.
    price = ndb.TextProperty()

    # The category that this item is part of.
    category = ndb.StringProperty()

    # The list of images associated to this item. Limited to 5 in the app.
    image = ndb.StructuredProperty(Image, repeated=True, indexed=False)

    # The user's lat/lng when this item was created.
    location = ndb.GeoPtProperty(indexed=False)


class LikeState(ndb.Model):
    # The user that liked/disliked the item.
    user_id = ndb.KeyProperty(User, indexed=True)

    # The item that is liked/disliked.
    item_id = ndb.KeyProperty(Item, indexed=True)

    # Whether or not this is a like or dislike.
    like_state = ndb.BooleanProperty(indexed=True)
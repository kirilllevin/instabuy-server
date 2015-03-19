# The number of items to return for a GetItems request.
NUM_ITEMS_PER_REQUEST = 5

# The number of items to retrieve from the datastore at a time, when iterating
# over the items.
NUM_ITEMS_PER_PAGE = 50

# The number of users to retrieve from the datastore at a time,
# when iterating over the users.
NUM_USERS_PER_PAGE = 300

# Types of retrievals for GetItems.
RETRIEVAL_SEARCH = 'search'
RETRIEVAL_CATEGORY = 'category'
RETRIEVAL_POPULAR = 'popular'
RETRIEVAL_NEARBY = 'nearby'

# Name of the Search API index that contains the items.
ITEM_INDEX_NAME = 'items'

class _ErrorCode():
    def __init__(self, name, code):
        self.name = name
        self.code = code


MALFORMED_REQUEST = _ErrorCode('MalformedRequest', 100)

FACEBOOK_ERROR = _ErrorCode('FacebookError', 200)
FACEBOOK_TOKEN_ERROR = _ErrorCode('FacebookTokenError', 201)

ACCOUNT_EXISTS = _ErrorCode('AccountExists', 300)
INVALID_ITEM = _ErrorCode('InvalidItem', 301)
INVALID_USER = _ErrorCode('InvalidUser', 302)
USER_PERMISSION_ERROR = _ErrorCode('UserPermissionError', 303)

GENERIC_ERROR = _ErrorCode('GenericError', 900)
UPLOAD_FAILED = _ErrorCode('UploadFailed', 901)
INDEXING_ERROR = _ErrorCode('IndexingError', 902)
SEARCH_ERROR = _ErrorCode('SearchError', 903)

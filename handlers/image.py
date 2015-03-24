from google.appengine.api import images
from google.appengine.ext import blobstore
from google.appengine.ext import ndb
from google.appengine.ext.webapp import blobstore_handlers

import error_codes
import base
import models


class GetUploadUrl(base.BaseHandler):
    @ndb.toplevel
    def get(self):
        self.populate_success_response(
            {'upload_url': blobstore.create_upload_url('/upload_image')})


class Upload(blobstore_handlers.BlobstoreUploadHandler, base.BaseHandler):
    @ndb.toplevel
    def post(self):
        success = self.parse_request(
            {'fb_access_token': (str, True, None),
             'item_id': (long, True, None)})
        if not success:
            self.populate_error_response(error_codes.MALFORMED_REQUEST)
            return

        # Check that something was uploaded.
        uploads = self.get_uploads()
        if not uploads:
            self.populate_error_response(error_codes.UPLOAD_FAILED)
            return
        image_key = uploads[0].key()

        if not (self.populate_user(self.args['fb_access_token']) and
                self.populate_item_for_mutation(self.args['item_id'])):
            # Delete the blob.
            blobstore.delete(image_key)
            return

        # Append the image key to the item's list of images.
        image = models.Image(blob_key=image_key,
                             url=images.get_serving_url(image_key))

        self.item.image.append(image)
        self.item.put()

        self.populate_success_response()

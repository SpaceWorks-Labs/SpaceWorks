"""Bound multipart input before Django spools a file or the serializer sees it."""

from django.core.files.uploadhandler import FileUploadHandler
from rest_framework.exceptions import ParseError

from .website_assets import MAX_BYTES


class WebsiteUploadLimit(FileUploadHandler):
    def __init__(self, request=None):
        super().__init__(request)
        self.received = 0

    def handle_raw_input(self, input_data, META, content_length, boundary, encoding=None):
        if content_length and content_length > MAX_BYTES + 65536:
            raise ParseError("Website image requests must fit the 5 MB image limit.")

    def receive_data_chunk(self, raw_data, start):
        self.received += len(raw_data)
        if self.received > MAX_BYTES:
            raise ParseError("Website images must not exceed 5 MB in total.")
        return raw_data

    def file_complete(self, file_size):
        return None

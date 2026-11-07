"""Fixed collection bounds; malformed or out-of-range page input is a field error."""

from django.utils.translation import gettext
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination


class PagePagination(PageNumberPagination):
    page_size = 24

    def get_page_number(self, request, paginator):
        value = request.query_params.get("page", "1")
        if not value.isascii() or not value.isdecimal() or not 1 <= int(value) <= paginator.num_pages:
            raise ValidationError({"page": gettext("Choose a valid collection page.")})
        return int(value)

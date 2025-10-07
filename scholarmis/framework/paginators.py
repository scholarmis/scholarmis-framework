from rest_framework.pagination import PageNumberPagination

class Pagination(PageNumberPagination):
    page_size = 20  # Items per page
    page_size_query_param = 'page_size'  # Allow clients to set page size via query
    max_page_size = 100  # Limit the maximum page size

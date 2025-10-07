from rest_framework import viewsets
from scholarmis.framework.paginators import Pagination

class OptionModelViewSet(viewsets.ModelViewSet):
    """
    Generic ViewSet for OptionModels
    """
    pagination_class = Pagination
    search_fields = ["name"]
    ordering_fields = ["name", "id"]
    ordering = ["name"]


class BaseModelViewSet(viewsets.ModelViewSet):
    pagination_class = Pagination
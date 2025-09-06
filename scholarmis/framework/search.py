from django.db.models import QuerySet # type: ignore


class SearchQuery:
    query_param = "query"  # Default query parameter name

    def get_queryset(self) -> QuerySet:
        # Fetch the original queryset
        queryset = super().get_queryset()

        # Get the value of the query parameter
        query_value = self.request.GET.get(self.query_param, "").strip()

        # If the query is empty, return an empty queryset
        if not query_value:
            return queryset.none()

        # Return the original queryset if the query is not empty
        return queryset



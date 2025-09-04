import json
import logging
from pathlib import Path
from typing import Dict, Optional
from django.db.models import Q, QuerySet, Model # type: ignore
from django.apps import apps # type: ignore
from django.core.cache import cache # type: ignore

logger = logging.getLogger(__name__)


class FilterContextLoader:
    """
    Handles loading and caching of filter context from JSON files.

    Attributes:
        app_name (str): The name of the app whose filter context is being loaded.
    """

    DEFAULT_DIR = "config"
    DEFAULT_FILE = "filters.json"
    
    def __init__(self, app_name: str, filter_dir: Optional[str] = None, filter_file: Optional[str] = None):
        self.app_name = app_name
        self.filter_dir = filter_dir or self.DEFAULT_DIR
        self.filter_file = filter_file or self.DEFAULT_FILE
        self.cache_key = f"filter_context_{self.app_name}"
        self.file_path = self._get_filter_file_path()

    def _get_cache_version_key(self) -> str:
        """
        Generates a cache version key based on the file's last modification time.
        """
        try:
            file_mod_time = self.file_path.stat().st_mtime
            return f"{self.cache_key}_version_{file_mod_time}"
        except FileNotFoundError:
            return self.cache_key
        
    def _get_app_absolute_path(self) -> Optional[Path]:
        """
        Get the absolute path of the app based on its app name.
        """
        try:
            return Path(apps.get_app_config(self.app_name).path)
        except LookupError:
            return None

    def _get_absolute_path(self, relative_path: Path) -> Path:
        """
        Resolve relative path inside app directory to an absolute path.
        """
        app_path = self._get_app_absolute_path()
        return (app_path / relative_path) if app_path else relative_path
    
    def _get_filter_file_path(self) -> Path:
        """
        Get absolute path for the filter.json file.
        """
        relative_path = self.filter_dir / self.filter_file
        return self._get_absolute_path(relative_path)

    def _load_from_file(self) -> Dict:
        """
        Load the filter context directly from the JSON file.
        If file is missing or invalid, return {} instead of raising.
        """
        if not self.file_path.exists():
            logger.warning("Filter file not found: %s", self.file_path)
            return {}
        
        try:
            with self.file_path.open("r", encoding="utf-8") as file:
                return json.load(file)
        except json.JSONDecodeError as e:
            logger.error("Error decoding JSON in %s: %s", self.file_path, e)
            return {}
        except Exception as e:
            logger.exception("Unexpected error reading %s: %s", self.file_path, e)
            return {}

    def load_filter_context(self) -> Dict:
        """
        Loads the filter context from JSON, using cached data if available.
        Falls back to {} if file is missing or invalid.
        """
        version_key = self._get_cache_version_key()
        filter_context = cache.get(version_key)

        if filter_context is None:
            filter_context = self._load_from_file()
            cache.set(version_key, filter_context, timeout=None)  # Cache indefinitely

        return filter_context



def dynamic_filter(model_class: Model, filters, **kwargs) -> QuerySet:
    """
    Dynamically filters a queryset for a given model class based on required and optional filters.
    
    - Supports Django-style field lookups (e.g., field__gte, program__division__name).
    - Skips filters where value is empty (None, "", or []).
    - Applies filters only if corresponding DB field has non-null values that can match.

    Args:
        model_class (models.Model): The model class to query.
        filters (Q | dict | QuerySet): Required conditions.
        **kwargs: Optional filters with lookup support.

    Returns:
        QuerySet: Filtered queryset.
    """
    # Step 1: Base queryset
    if isinstance(filters, Q):
        queryset = model_class.objects.filter(filters)
    elif isinstance(filters, dict):
        queryset = model_class.objects.filter(**filters)
    elif isinstance(filters, QuerySet):
        queryset = filters
    else:
        raise ValueError("Expected 'filters' to be a Q object, dict, or QuerySet.")

    # Step 2: Get nullable fields
    nullable_fields = {
        field.name for field in model_class._meta.get_fields()
        if hasattr(field, 'null') and field.null
    }

    # Step 3: Apply optional filters
    for key, value in kwargs.items():
        if value in [None, "", []]:
            continue  # skip empty values

        # Extract base field name (before any lookups)
        base_field = key.split("__")[0]

        # More precise: apply only if this value exists in non-null rows
        if base_field in nullable_fields:
            if queryset.filter(**{key: value}).exclude(**{base_field: None}).exists():
                queryset = queryset.filter(**{key: value})
        else:
            queryset = queryset.filter(**{key: value})

    return queryset


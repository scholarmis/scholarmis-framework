import json
from django.apps import AppConfig # type: ignore
from django.db.models import Model # type: ignore
from django.core.cache import cache # type: ignore


class GlobalSettingsLoader:
    """
    A class to load and manage global settings from the database with optional caching.

    Attributes:
        model (Model): a model to save and load settings from.
        use_cache (bool): Flag to determine if caching should be used.
        cache_timeout (int): Duration (in seconds) for which cached settings are valid.
    """

    def __init__(self, model: Model, use_cache: bool=True, cache_timeout:int=300):
        """
        Initializes the GlobalSettingsLoader with specified caching options.

        Args:
            model (Model): a model to save and load settings from.
            use_cache (bool): Indicates whether to use caching. Defaults to True.
            cache_timeout (int): Duration in seconds for cached settings. Defaults to 300 seconds.
        """
        self.model = model
        self.use_cache = use_cache
        self.cache_timeout = cache_timeout

    def get_setting(self, key, default=None):
        """
        Retrieves a global setting by its key.

        Args:
            key (str): The key of the setting to retrieve.
            default: The value to return if the setting is not found.

        Returns:
            The value of the setting or the default value.
        """
        return self._get_setting(key, default)

    def set_setting(self, key, value, data_type="str"):
        """
        Sets a global setting with the specified key and value.

        Args:
            key (str): The key of the setting to set.
            value: The value to set for the setting.
            data_type (str): The type of the value being set. Defaults to "str".
        """
        return self._set_setting(key, value, data_type)

    def get_int(self, key:str, default=0):
        """
        Retrieves a global setting as an integer.

        Args:
            key (str): The key of the setting to retrieve.
            default (int): The value to return if the setting is not found. Defaults to 0.

        Returns:
            int: The integer value of the setting or the default value.
        """
        return self._get_setting(key, default, data_type="int")

    def set_int(self, key:str, value:int):
        """
        Sets a global setting as an integer.

        Args:
            key (str): The key of the setting to set.
            value (int): The integer value to set for the setting.
        """
        return self._set_setting(key, value, data_type="int")

    def get_bool(self, key:str, default=False):
        """
        Retrieves a global setting as a boolean.

        Args:
            key (str): The key of the setting to retrieve.
            default (bool): The value to return if the setting is not found. Defaults to False.

        Returns:
            bool: The boolean value of the setting or the default value.
        """
        return self._get_setting(key, default, data_type="bool")

    def set_bool(self, key:int, value:bool):
        """
        Sets a global setting as a boolean.

        Args:
            key (str): The key of the setting to set.
            value (bool): The boolean value to set for the setting.
        """
        return self._set_setting(key, value, data_type="bool")

    def get_str(self, key:str, default=""):
        """
        Retrieves a global setting as a string.

        Args:
            key (str): The key of the setting to retrieve.
            default (str): The value to return if the setting is not found. Defaults to an empty string.

        Returns:
            str: The string value of the setting or the default value.
        """
        return self._get_setting(key, default, data_type="str")

    def set_str(self, key:str, value:str):
        """
        Sets a global setting as a string.

        Args:
            key (str): The key of the setting to set.
            value (str): The string value to set for the setting.
        """
        return self._set_setting(key, value, data_type="str")

    def get_list(self, key, default=None):
        """
        Retrieves a global setting as a list.

        Args:
            key (str): The key of the setting to retrieve.
            default (list): The value to return if the setting is not found. Defaults to an empty list.

        Returns:
            list: The list value of the setting or the default value.
        """
        if default is None:
            default = []
        value = self._get_setting(key, default, data_type="list")
        return json.loads(value) if isinstance(value, str) else value

    def set_list(self, key, value):
        """
        Sets a global setting as a list.

        Args:
            key (str): The key of the setting to set.
            value (list): The list value to set for the setting.
        """
        return self._set_setting(key, json.dumps(value), data_type="list")
    
    def get_setting_from_options(self, key, default=None):
        """
        Retrieves a global setting value from predefined options.

        Args:
            key (str): The key of the setting to retrieve.
            default: The value to return if the setting is not found or the value is not in options.

        Returns:
            The value of the setting if it is in options; otherwise, the default value.
        """
        setting = self._get_setting_object(key)
        options = setting.get_options() if setting else []
        if setting and setting.get_value() in options:
            return setting.get_value()
        return default

    def set_setting_from_options(self, key, selected_value):
        """
        Sets a global setting from predefined options.

        Args:
            key (str): The key of the setting to set.
            selected_value: The value to set for the setting.

        Raises:
            ValueError: If the selected_value is not in the predefined options.
        """
        setting = self._get_setting_object(key)
        options = setting.get_options() if setting else []
        if selected_value in options:
            self._set_setting(key, selected_value, data_type=setting.data_type)

    def get_model(self):
        """
        Retrieves the GlobalSetting model.

        Returns:
            The GlobalSetting model class.
        """
        return self.model

    def _get_setting_object(self, key):
        """
        Retrieves a global setting object by its key, using cache if enabled.

        Args:
            key (str): The key of the setting to retrieve.

        Returns:
            The GlobalSetting object if found; otherwise, None.
        """
        if self.use_cache:
            cache_key = f"global_{key}_object"
            cached_setting = cache.get(cache_key)
            if cached_setting is not None:
                return cached_setting
        try:
            model = self.get_model()
            setting = model.objects.get(setting_key=key)
            if self.use_cache:
                cache.set(f"global_{key}_object", setting, self.cache_timeout)
            return setting
        except model.DoesNotExist:
            return None

    def _get_setting(self, key, default=None, data_type="str"):
        """
        Retrieves the value of a global setting by its key, using cache if enabled.

        Args:
            key (str): The key of the setting to retrieve.
            default: The value to return if the setting is not found.
            data_type (str): The expected data type of the setting value.

        Returns:
            The value of the setting or the default value.
        """
        if self.use_cache:
            cache_key = f"global_{key}"
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                return cached_value
        try:
            model = self.get_model()
            setting = model.objects.get(setting_key=key)
            if setting.data_type == data_type:
                value = setting.get_value()
            else:
                value = default
        except model.DoesNotExist:
            value = default

        if self.use_cache:
            cache.set(f"global_{key}", value, self.cache_timeout)

        return value

    def _set_setting(self, key, value, data_type="str"):
        """
        Sets a global setting with the specified key and value.

        Args:
            key (str): The key of the setting to set.
            value: The value to set for the setting.
            data_type (str): The type of the value being set. Defaults to "str".
        """
        model = self.get_model()
        setting, created = model.objects.get_or_create(setting_key=key)
        setting.setting_value = str(value)
        setting.data_type = data_type
        setting.save()

        if self.use_cache:
            cache.set(f"global_{key}", setting.get_value(), self.cache_timeout)

    def get_all_settings(self):
        """
        Retrieves all global settings.

        Returns:
            dict: A dictionary of all setting keys and their values.
        """
        model = self.get_model()
        settings = model.objects.all()
        return {setting.setting_key: setting.get_value() for setting in settings}


class AppSettingsLoader(GlobalSettingsLoader):
    """
    A class to load and manage application-specific settings from the database with optional caching.

    Inherits from GlobalSettingsLoader and extends functionality to handle settings for a specific application.

    Attributes:
        app (AppConfig): The application for which settings are managed.
    """
    
    def __init__(self, app:AppConfig, model:Model, use_cache:bool=True, cache_timeout:int=300):
        """
        Initializes the AppSettingsLoader with specified application and caching options.

        Args:
            app (AppConfig): The application for which settings are managed.
            use_cache (bool): Indicates whether to use caching. Defaults to True.
            cache_timeout (int): Duration in seconds for cached settings. Defaults to 300 seconds.
        """
        super().__init__(model, use_cache, cache_timeout)
        self.app = app

    def get_setting(self, key, default=None):
        """
        Retrieves an application-specific setting by its key.

        Args:
            key (str): The key of the setting to retrieve.
            default: The value to return if the setting is not found.

        Returns:
            The value of the application-specific setting or the default value.
        """
        app_key = f"{self.app.name}.{key}"
        return super().get_setting(app_key, default)

    def set_setting(self, key, value, data_type="str"):
        """
        Sets an application-specific setting with the specified key and value.

        Args:
            key (str): The key of the setting to set.
            value: The value to set for the application-specific setting.
            data_type (str): The type of the value being set. Defaults to "str".
        """
        app_key = f"{self.app.name}.{key}"
        return super().set_setting(app_key, value, data_type)

    def get_all_settings(self):
        """
        Retrieves all application-specific settings.

        Returns:
            dict: A dictionary of all setting keys and their values for the application.
        """
        model = self.get_model()
        settings = model.objects.filter(setting_key__startswith=f"{self.app.name}.")
        return {setting.setting_key: setting.get_value() for setting in settings}

from typing import List
from django.apps import AppConfig # type: ignore


class AppRegistry:

    def __init__(self):
        self.apps: List["AppConfig"] = []  # List to store registered apps

    def register(self, app: "AppConfig"):
        """
        Register a new AppConfig instance if not already registered,
        ensuring it is registered after its dependencies.
        
        :param app: The AppConfig class to register.
        """
        # Add the app after its dependencies
        self.apps.append(app)

    def get_first(self):
        """
        Get the first app in the registry.
        
        :return: The first app or None if no apps are registered.
        """
        return self.apps[0] if self.apps else None

    def get_by_name(self, name: str):
        """
        Retrieve a app by its name.
    
        """
        for app in self.apps:
            if getattr(app, "name", None) == name:
                return app
        return None
    
    def get_by_label(self, label: str):
        """
        Retrieve a app by its label.
    
        """
        for app in self.apps:
            if getattr(app, "label", None) == label:
                return app
        return None
    
    def get_by_verbose_name(self, verbose_name: str):
        """
        Retrieve a app by its verbose name.
        """
        for app in self.apps:
            if getattr(app, "verbose_name", None) == verbose_name:
                return app
        return None
    
    def get_apps(self):
        """
        Retrieve registered apps.
        """
        return self.apps
    
    def get_labels(self):
        """
        Retrieve a list of labels for  applications.

        Returns:
            list: A list of application labels.
        """
        apps = self.get_apps()
        labels = []
        for app in apps:
            labels.append(app.label)
        return labels
    
    def has_app(self, app):
        """
        Check app exists in apps.
        """
        apps = self.get_apps()
        return app in apps

    def has_label(self, label):
        """
        Check if a specific label exists in the app labels.
        """
        labels = self.get_labels()
        return label in labels


import json
from pathlib import Path
from .utils import compare_version, match_version
from .metadata import PluginMetadata


class LockFile:
    """Manages the creation, loading, and saving of the plugins.lock file."""
   
    def __init__(self, lock_file_path: Path):
        
        self.lock_file = lock_file_path
        self.lock_dir = lock_file_path.parent
        self.ensure_lock()

    def ensure_lock(self):
        """Ensures the .scholarmis directory and plugins.lock file exist."""
        self.lock_dir.mkdir(parents=True, exist_ok=True)
        if not self.lock_file.exists():
            self.lock_file.write_text(json.dumps({"plugins": {}}, indent=2), encoding="utf-8")

    def read(self) -> dict:
        """Loads the data from the plugins.lock file."""
        try:
            return json.loads(self.lock_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError):
            self.ensure_lock()
            return {"plugins": {}}

    def write(self, data: dict):
        """Saves data to the plugins.lock file."""
        self.lock_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def add_plugin(self, name:str, version:str, source, pin:str=None, force:bool=False ):
        data = self.read()

        plugin = self.get_plugin(name)

        if plugin and not force:
            plugin_version = plugin.get("version")
            if plugin_version and compare_version(version, plugin_version) < 0:
                raise ValueError(
                    f"Downgrade detected for {name}:{version} < {plugin_version}. "
                    f"Use --force to override."

                )
            pinned = plugin.get("pin")
            if pinned and not match_version(version, pinned):
                raise ValueError(f"Version {version} of {name} does not satisfy constraint {pinned}")

        data["plugins"][name]={
            "version": version,
            "source":source,
            "pin": pin or pinned if plugin else None
        }
        self.write(data)

    def get_plugins(self) -> dict:
        data = self.read()
        return data.get("plugins")
    
    def get_plugin(self, name) -> dict:
        plugins = self.get_plugins()
        return plugins.get(name)
    
    def delete_plugin(self, name) -> bool:
        data = self.read()
        plugins = data.get("plugins", {})
        if name in plugins:
            del plugins[name]
            data["plugins"] = plugins
            self.write(data)
            return True
        return False

    def get_locked(self) -> list[PluginMetadata]:
        """Return a list of PluginMetadata objects for all locked plugins"""
        plugins = self.get_plugins()
        return [PluginMetadata.from_dict(meta) for meta in plugins.values()]
import json
import logging
import os
import shutil
import subprocess
import sys
import zipfile
import requests # type: ignore
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import urlparse
from .metadata import PluginMetadata
from .loader import PluginLoader
from .utils import compute_file_checksum, match_version
from .pip import pip_upgrade, pip_uninstall, pip_show_version, pip_list_outdated_json


logger = logging.getLogger(__name__)


class BaseInstaller(ABC):
    """Base class for all plugin installation strategies."""

    def __init__(self, loader: PluginLoader):
        self.loader = loader
        self.lock_file = loader.lock_file
        self.base_dir = loader.base_dir
        self.plugin_dir = loader.plugin_dir

    @abstractmethod
    def install(self, source: str, name: Optional[str] = None) -> Optional[PluginMetadata]:
        """Install the plugin and return the loaded PluginMetadata."""
        pass

    def load(self, plugin: PluginMetadata):
        self.loader.load_plugin(plugin)

    def lock(self, plugin: PluginMetadata):
        # Ensure checksum
        if not plugin.checksum:
            path = Path(plugin.source)
            if path.exists():
                plugin.checksum = compute_file_checksum(Path(plugin.source))

        # Ensure version pin
        if not plugin.pin and plugin.version:
            plugin.pin = f"=={plugin.version}"

        # Read existing lockfile data
        data = self.lock_file.read()
        plugins = data.setdefault("plugins", {})

        # Update the plugin entry
        plugins[plugin.name] = plugin.to_dict()

        # Persist changes
        self.lock_file.write(data)

        logger.info(f"Plugin '{plugin.name}'written to lockfile successfully .")

    def finalize(self, plugin: PluginMetadata) -> PluginMetadata:
        self.lock(plugin)
        self.load(plugin)
        return plugin


class ZipInstaller(BaseInstaller):

    """Installs a plugin from a ZIP file."""

    def install(self, zip_path: str, name: Optional[str] = None) -> Optional[PluginMetadata]:
        target_dir = self.loader.plugin_dir
        target_dir.mkdir(parents=True, exist_ok=True)

        zip_path = Path(zip_path).resolve()

        try:
            with zipfile.ZipFile(zip_path, "r") as z:
                # Determine the top-level folder in the ZIP
                top_level_dirs = {Path(f.filename).parts[0] for f in z.infolist() if f.filename.strip()}
                if len(top_level_dirs) != 1:
                    logger.error("Plugin ZIP must contain exactly one top-level folder")
                    return None
                top_folder = top_level_dirs.pop()

                # Normalize folder name (hyphens -> underscores)
                normalized_folder = top_folder.replace("-", "_")
                dest_path = target_dir / normalized_folder

                # Remove existing folder if present
                if dest_path.exists():
                    shutil.rmtree(dest_path)

                # Extract all files
                z.extractall(target_dir)

                # Rename folder if needed
                original_path = target_dir / top_folder
                if original_path != dest_path:
                    original_path.rename(dest_path)

                # Add top-level folder to sys.path for immediate import
                sys.path.insert(0, str(dest_path.resolve()))

            logger.info(f"Plugin extracted to {dest_path} and added to sys.path")

            # Discover plugin
            plugin_path = dest_path if not name else dest_path / name
            plugin = self.loader.discover_plugin(plugin_path)
            if plugin:
                return self.finalize(plugin)

            logger.error(f"Failed to discover plugin in {plugin_path}")

        except zipfile.BadZipFile as e:
            logger.error(f"Bad zip file: {zip_path} - {e}")

        return None


class GitInstaller(BaseInstaller):

    def install(self, git_url: str, name: Optional[str] = None, branch: str = "main") -> Optional[PluginMetadata]:
        repo_name = name or git_url.split("/")[-1].replace(".git", "")
        clone_path = self.loader.plugin_dir / repo_name

        if clone_path.exists():
            shutil.rmtree(clone_path)

        try:
            subprocess.run(
                ["git", "clone", "--depth", "1", "--branch", branch, git_url, str(clone_path)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            plugin = self.loader.discover_plugin(str(clone_path))
            if plugin:
                return self.finalize(plugin)
        except subprocess.CalledProcessError as e:
            logger.error(f"Git clone failed for {git_url}: {e.stderr.decode()}")
        return None


class URLInstaller(ZipInstaller):
    """Downloads a zip from a URL and delegates to ZipInstaller."""

    def install(self, url: str, name: Optional[str] = None) -> Optional[PluginMetadata]:
        filename = name or url.split("/")[-1]
        if not filename.endswith(".zip"):
            filename += ".zip"

        temp_dir = self.loader.base_dir / "temp"
        temp_zip_path = temp_dir / filename
        temp_dir.mkdir(parents=True, exist_ok=True)

        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()
            with open(temp_zip_path, "wb") as f:
                for chunk in response.iter_content(8192):
                    f.write(chunk)

            logger.info(f"Downloaded plugin to {temp_zip_path}")
            return super().install(temp_zip_path, name)
        except requests.RequestException as e:
            logger.error(f"Failed to download plugin from {url}: {e}")
            return None
        finally:
            # cleanup temp folder after installation attempt
            if temp_dir.exists():
                try:
                    shutil.rmtree(temp_dir)
                    logger.info(f"Deleted temporary folder {temp_dir}")
                except Exception as cleanup_err:
                    logger.warning(f"Failed to delete temporary folder {temp_dir}: {cleanup_err}")


class PipInstaller(BaseInstaller):

    def install(self, package_name: str, name: Optional[str] = None) -> Optional[PluginMetadata]:
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", package_name],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            plugin = self.loader.discover_plugin(package_name)
            if plugin:
                return self.finalize(plugin)

        except subprocess.CalledProcessError as e:
            logger.error(f"Pip installation failed for {package_name}: {e.stderr.decode()}")
        return None


class PluginInstaller(BaseInstaller):
    """
    Handles installation of plugins using different strategies:
    ZIP, Git, URL, or PyPI.
    """

    def __init__(self, loader: PluginLoader):
        super().__init__(loader)

        self.strategies: Dict[str, BaseInstaller] = {
            "zip": ZipInstaller(loader),
            "git": GitInstaller(loader),
            "url": URLInstaller(loader),
            "pip": PipInstaller(loader),
        }

    def install(self, source: str, name: Optional[str] = None) -> Optional[PluginMetadata]:
        """
        Determines the appropriate installation strategy and installs the plugin.

        Args:
            source: Path, URL, Git repo, or PyPI package name.
            name: Optional plugin name.

        Returns:
            PluginMetadata if installation succeeds, None otherwise.
        """
        parsed = urlparse(source)

        if parsed.scheme in ("http", "https") and source.endswith(".git"):
            return self.strategies["git"].install(source, name)
        elif parsed.scheme in ("http", "https"):
            return self.strategies["url"].install(source, name)
        elif Path(source).exists() and source.endswith(".zip"):
            return self.strategies["zip"].install(source, name)
        else:
            # Fallback to PyPI installer
            return self.strategies["pip"].install(source, name)
        
    def upgrade(self, plugin_name: str, target_version: Optional[str] = None) -> Optional[PluginMetadata]:
        """
        Upgrade a plugin via pip to the latest version or a specified version.

        Args:
            plugin_name: Name of the plugin to upgrade.
            target_version: Optional version specifier (e.g., "==1.2.3").

        Returns:
            Updated PluginMetadata if successful, None otherwise.
        """
        plugin = self.loader.discover_plugin(plugin_name)
        if not plugin:
            logger.error(f"Plugin {plugin_name} not found for upgrade.")
            return None

        target = f"{plugin_name}{target_version or ''}"
        try:
            pip_upgrade(target)
            new_version = pip_show_version(plugin_name)
            if new_version:
                plugin.version = new_version
                # Optionally update pin and checksum
                plugin.pin = f"=={new_version}"
                plugin.checksum = compute_file_checksum(Path(plugin.source))
                self.lock(plugin) 
                logger.info(f"Plugin {plugin_name} upgraded to version {new_version}.")
                return plugin
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to upgrade plugin {plugin_name}: {e}")
        return None
    
    def upgrade_all(self):
        """
        Upgrade a single plugin or all pinned plugins.

        Args:
            name: Name of the plugin to upgrade. Ignored if all_ is True.
            all_: If True, upgrade all pinned plugins.
        """
        plugins = self.lock_file.get_plugins()

        if all:
            for pname, meta in plugins.items():
                self.upgrade(pname)

    def uninstall(self, plugin_name: str) -> bool:
        """
        Uninstall the specified plugin from the environment and remove
        it from the lockfile.
        """
        try:
            # uninstall with pip
            pip_uninstall(plugin_name)

            # discover the plugin object
            plugin: Optional[PluginMetadata] = self.loader.discover_plugin(plugin_name)
            if plugin and plugin.source:
                path = Path(plugin.source)
                if path.exists():
                    try:
                        if path.is_dir():
                            shutil.rmtree(path)
                    except Exception as e:
                        pass

            # update lockfile
            if self.lock_file.delete_plugin(plugin_name):
                self.loader.unload_plugin(plugin_name)
                logger.info(f"Plugin {plugin_name} uninstalled and removed from lockfile.")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to uninstall plugin {plugin_name}: {e}")
            return False

    def check_plugins(self):
        """
        Validates that installed plugins match the lockfile.
        Returns (errors, warnings) lists.
        """
        locked_plugins = self.lock_file.get_locked()

        # Gather installed packages
        try:
            res = subprocess.run(
                [sys.executable, "-m", "pip", "list", "--format=json"],
                capture_output=True,
                text=True,
                check=True
            )
            installed = {pkg["name"].lower(): pkg["version"] for pkg in json.loads(res.stdout)}
        except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
            raise Exception(f"Failed to get installed packages: {e}")

        errors, warnings = [], []

        for plugin in locked_plugins:
            installed_version = installed.get(plugin.pip_name.lower())

            # Check if locked plugin is installed
            if not installed_version:
                errors.append(f"Plugin '{plugin.name}' locked to {plugin.version} but not installed.")
                continue

            # Check pin constraints
            if plugin.pin and not match_version(installed_version, plugin.pin):
                errors.append(f"Plugin '{plugin.name}': installed {installed_version} does not satisfy pin '{plugin.pin}'.")

            # Optional stricter check: installed version matches locked version
            if plugin.version != "unknown" and installed_version != plugin.version:
                errors.append(f"Plugin '{plugin.name}': installed {installed_version} != locked {plugin.version}.")

        # Detect installed but untracked plugins
        locked_names = {p.pip_name.lower() for p in locked_plugins}
        for pkg, ver in installed.items():
            if (pkg.startswith("scholarmis-") or pkg.startswith("scholarmis_")) and pkg not in locked_names:
                warnings.append(f"Package '{pkg}' version {ver} installed but not tracked in lockfile.")

        return errors, warnings
    
    def list_outdated(self) -> dict:
        """
        Returns a dictionary of outdated plugins and their latest available versions.
        """
        try:
            outdated_json = pip_list_outdated_json()
            return json.loads(outdated_json)
        except Exception as e:
            logger.error(f"Failed to retrieve outdated plugin list: {e}")
            return {}

"""Plugin loader for custom data adapters."""

import importlib.util
import json
import os
import sys
from pathlib import Path

from app.data.base import DataAdapter
from app.data.registry import registry
from app.logging_config import get_logger
from app.models.plugin_schemas import PluginInfo, PluginManifest

logger = get_logger(__name__)

PLUGINS_DIR = Path(__file__).parent.parent / "plugins"


def scan_plugins() -> list[PluginInfo]:
    """
    Read-only metadata scan of all plugins.

    Reads plugin.json manifests and checks env vars without
    importing any code. Returns a list of PluginInfo objects.
    """
    if not PLUGINS_DIR.exists():
        return []

    results: list[PluginInfo] = []

    # Scan flat .py files (no manifest)
    for plugin_file in sorted(PLUGINS_DIR.glob("*.py")):
        if plugin_file.name.startswith("_"):
            continue
        results.append(
            PluginInfo(
                name=plugin_file.stem,
                description="",
                author="",
                version="",
                status="no_manifest",
            )
        )

    # Scan directories with plugin.json
    for entry in sorted(PLUGINS_DIR.iterdir()):
        if not entry.is_dir() or entry.name.startswith("_"):
            continue

        manifest_path = entry / "plugin.json"
        adapter_path = entry / "adapter.py"
        readme_path = entry / "README.md"

        if not manifest_path.exists():
            results.append(
                PluginInfo(
                    name=entry.name,
                    description="",
                    author="",
                    version="",
                    status="error",
                    error_message="Missing plugin.json",
                )
            )
            continue

        # Parse manifest
        try:
            raw = json.loads(manifest_path.read_text())
            manifest = PluginManifest(**raw)
        except (json.JSONDecodeError, Exception) as e:
            results.append(
                PluginInfo(
                    name=entry.name,
                    description="",
                    author="",
                    version="",
                    status="error",
                    error_message=f"Invalid plugin.json: {e}",
                )
            )
            continue

        # Check adapter.py exists
        if not adapter_path.exists():
            results.append(
                PluginInfo(
                    name=manifest.name,
                    description=manifest.description,
                    author=manifest.author,
                    version=manifest.version,
                    status="error",
                    error_message="Missing adapter.py",
                    required_env_vars=manifest.required_env_vars,
                    has_readme=readme_path.exists(),
                )
            )
            continue

        # Check required env vars
        missing = [v for v in manifest.required_env_vars if not os.environ.get(v)]
        if missing:
            results.append(
                PluginInfo(
                    name=manifest.name,
                    description=manifest.description,
                    author=manifest.author,
                    version=manifest.version,
                    status="missing_deps",
                    error_message=(f"Missing env vars: {', '.join(missing)}"),
                    required_env_vars=manifest.required_env_vars,
                    has_readme=readme_path.exists(),
                )
            )
            continue

        results.append(
            PluginInfo(
                name=manifest.name,
                description=manifest.description,
                author=manifest.author,
                version=manifest.version,
                status="active",
                required_env_vars=manifest.required_env_vars,
                has_readme=readme_path.exists(),
            )
        )

    return results


def load_plugins() -> int:
    """
    Load all plugins from the plugins/ directory.

    Scans for .py files and plugin directories, imports them,
    and registers any DataAdapter subclasses.
    Returns the number of plugins successfully loaded.
    """
    if not PLUGINS_DIR.exists():
        logger.info("No plugins directory found, skipping plugin loading")
        return 0

    loaded = 0

    # Load flat .py files
    for plugin_file in PLUGINS_DIR.glob("*.py"):
        if plugin_file.name.startswith("_"):
            continue

        try:
            adapter = _load_plugin_file(plugin_file)
            if adapter:
                registry.register(adapter, is_plugin=True)
                logger.info(
                    "Loaded plugin: %s (%s)",
                    adapter.name,
                    plugin_file.name,
                )
                loaded += 1
        except Exception as e:
            logger.warning(
                "Failed to load plugin %s: %s",
                plugin_file.name,
                str(e),
            )

    # Load directory plugins
    for entry in sorted(PLUGINS_DIR.iterdir()):
        if not entry.is_dir() or entry.name.startswith("_"):
            continue

        adapter_path = entry / "adapter.py"
        manifest_path = entry / "plugin.json"

        if not adapter_path.exists():
            continue

        # Skip if required env vars missing
        if manifest_path.exists():
            try:
                raw = json.loads(manifest_path.read_text())
                manifest = PluginManifest(**raw)
                missing = [
                    v for v in manifest.required_env_vars if not os.environ.get(v)
                ]
                if missing:
                    logger.warning(
                        "Skipping plugin %s: missing env vars %s",
                        entry.name,
                        ", ".join(missing),
                    )
                    continue
            except Exception as e:
                logger.warning(
                    "Bad manifest for %s: %s",
                    entry.name,
                    str(e),
                )
                continue

        try:
            adapter = _load_plugin_file(adapter_path)
            if adapter:
                registry.register(adapter, is_plugin=True)
                logger.info(
                    "Loaded plugin: %s (%s/)",
                    adapter.name,
                    entry.name,
                )
                loaded += 1
        except Exception as e:
            logger.warning(
                "Failed to load plugin %s: %s",
                entry.name,
                str(e),
            )

    if loaded:
        logger.info("Loaded %d plugin(s) from %s", loaded, PLUGINS_DIR)

    return loaded


def reload_plugins() -> list[PluginInfo]:
    """
    Unregister existing plugin adapters, re-scan and re-load.

    Returns the updated scan results.
    """
    # Unregister all current plugin adapters
    for name in list(registry.plugin_adapters):
        registry.unregister(name)

    # Re-load
    load_plugins()

    # Return scan results
    return scan_plugins()


def _load_plugin_file(plugin_file: Path) -> DataAdapter | None:
    """
    Load a single plugin file and return its DataAdapter instance.

    The file must contain exactly one DataAdapter subclass.
    """
    module_name = f"plugins.{plugin_file.stem}"

    spec = importlib.util.spec_from_file_location(module_name, plugin_file)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load spec for {plugin_file}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    # Find DataAdapter subclasses in the module
    adapters = []
    for name in dir(module):
        obj = getattr(module, name)
        if (
            isinstance(obj, type)
            and issubclass(obj, DataAdapter)
            and obj is not DataAdapter
            and hasattr(obj, "name")
            and hasattr(obj, "description")
        ):
            adapters.append(obj)

    if not adapters:
        logger.debug("No DataAdapter found in %s", plugin_file.name)
        return None

    if len(adapters) > 1:
        logger.warning(
            "Multiple adapters in %s, using first: %s",
            plugin_file.name,
            adapters[0].name,
        )

    # Instantiate and return
    return adapters[0]()

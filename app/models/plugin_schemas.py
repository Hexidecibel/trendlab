"""Plugin metadata schemas."""

from pydantic import BaseModel, Field


class PluginManifest(BaseModel):
    """Schema for plugin.json manifest files."""

    name: str
    description: str
    author: str
    version: str
    required_env_vars: list[str] = Field(default_factory=list)


class PluginInfo(BaseModel):
    """Plugin metadata returned by the scan endpoint."""

    name: str
    description: str
    author: str
    version: str
    status: str  # active, missing_deps, error, no_manifest
    error_message: str | None = None
    required_env_vars: list[str] = Field(default_factory=list)
    has_readme: bool = False

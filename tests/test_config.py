import os
from unittest.mock import patch

from app.config import Settings


class TestSettings:
    def test_reads_github_token_from_env(self):
        with patch.dict(os.environ, {"GITHUB_TOKEN": "ghp_test123"}):
            settings = Settings()
            assert settings.github_token == "ghp_test123"

    def test_github_token_defaults_to_none(self):
        env = os.environ.copy()
        env.pop("GITHUB_TOKEN", None)
        with patch.dict(os.environ, env, clear=True):
            settings = Settings()
            assert settings.github_token is None

    def test_debug_reads_from_env(self):
        with patch.dict(os.environ, {"DEBUG": "false"}):
            settings = Settings()
            assert settings.debug == "false"

    def test_reads_anthropic_api_key_from_env(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test123"}):
            settings = Settings()
            assert settings.anthropic_api_key == "sk-ant-test123"

    def test_anthropic_api_key_defaults_to_none(self):
        env = os.environ.copy()
        env.pop("ANTHROPIC_API_KEY", None)
        with patch.dict(os.environ, env, clear=True):
            settings = Settings()
            assert settings.anthropic_api_key is None

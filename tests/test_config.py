"""Tests for the configuration module."""

from supabase_models import config


class TestConfigurationConstants:
    """Test application configuration constants."""

    def test_default_values_are_correct(self):
        """Test all default values are correct."""
        assert config.DEFAULT_OUTPUT_FILE == "models.py"
        assert config.DEFAULT_TEMPLATE_NAME == "default.jinja2"
        assert config.DEFAULT_TIMEOUT == 10
        assert config.DEFAULT_SCHEMA == "public"

    def test_config_values_are_reasonable(self):
        """Test config values are reasonable defaults."""
        # Output file should be a Python file
        assert config.DEFAULT_OUTPUT_FILE.endswith(".py")
        assert config.DEFAULT_TEMPLATE_NAME.endswith(".jinja2")

        # Numeric values should be positive
        assert config.DEFAULT_TIMEOUT > 0

        # String values should be non-empty and clean
        string_constants = [
            config.DEFAULT_OUTPUT_FILE,
            config.DEFAULT_TEMPLATE_NAME,
            config.DEFAULT_SCHEMA
        ]

        for constant in string_constants:
            assert constant  # Not empty
            assert constant.strip() == constant  # No whitespace padding
            assert len(constant) > 0  # Has actual content

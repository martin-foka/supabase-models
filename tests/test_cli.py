"""Tests for the CLI module."""

import pytest

from supabase_models.cli import create_parser
from supabase_models.cli import handle_error


class TestArgumentParser:
    """Test CLI argument parsing functionality."""

    def test_parser_accepts_all_expected_arguments(self):
        """Test parser accepts all expected arguments."""
        parser = create_parser()

        args = parser.parse_args(
            [
                "--database-url",
                "postgresql://user:pass@host:5432/db",
                "--output",
                "custom_models.py",
                "--schema",
                "custom_schema",
                "--template",
                "custom.jinja2",
                "--verbose",
            ]
        )

        assert args.database_url == "postgresql://user:pass@host:5432/db"
        assert args.output == "custom_models.py"
        assert args.schema == "custom_schema"
        assert args.template == "custom.jinja2"
        assert args.verbose is True

    def test_parser_applies_correct_default_values(self):
        """Test parser applies correct default values."""
        parser = create_parser()
        args = parser.parse_args([])

        assert args.database_url is None
        assert args.output == "models.py"
        assert args.schema == "public"
        assert args.template is None
        assert args.verbose is False

    def test_parser_supports_short_argument_forms(self):
        """Test parser supports short argument forms."""
        parser = create_parser()
        args = parser.parse_args(["-o", "output.py", "-s", "test_schema", "-v"])

        assert args.output == "output.py"
        assert args.schema == "test_schema"
        assert args.verbose is True

    def test_parser_program_name_and_description(self):
        """Test parser program name and description."""
        parser = create_parser()

        assert parser.prog == "supabase-models"
        assert "Generate Pydantic models" in parser.description


class TestErrorHandling:
    """Test CLI error handling functionality."""

    def test_handle_error_terminates_program_with_exit_code(self):
        """Test error handler exits with correct code."""
        error = ValueError("Configuration error")

        with pytest.raises(SystemExit) as exc_info:
            handle_error(error, "config")

        assert exc_info.value.code == 1

    def test_handle_error_processes_different_error_types(self):
        """Test error handler processes different error types."""
        test_cases = [
            (ValueError("Config issue"), "config"),
            (KeyboardInterrupt(), "keyboard"),
            (RuntimeError("Unexpected"), "unexpected"),
        ]

        for error, error_type in test_cases:
            with pytest.raises(SystemExit):
                handle_error(error, error_type)

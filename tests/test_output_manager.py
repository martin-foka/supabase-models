"""Tests for the output manager component."""

import tempfile
from pathlib import Path
from unittest.mock import Mock
from unittest.mock import patch

import pytest

from supabase_models.common.schemas import ColumnInfo
from supabase_models.common.schemas import ModelInfo
from supabase_models.components.output_manager import OutputManager


class TestOutputManager:
    """Test OutputManager class."""

    @pytest.mark.parametrize(
        "template_name,expected",
        [
            (None, "default.jinja2"),
            ("custom.jinja2", "custom.jinja2"),
        ],
    )
    @patch("supabase_models.components.output_manager.OutputManager._init_jinja_environment")
    def test_init(self, mock_init_jinja, template_name, expected):
        """Test initialization with different template names."""
        manager = OutputManager(template_name=template_name)
        assert manager.template_name == expected
        mock_init_jinja.assert_called_once()

    def test_log_generation_summary(self):
        """Test logging summary."""
        with patch("supabase_models.components.output_manager.OutputManager._init_jinja_environment"):
            manager = OutputManager()

        manager.logger = Mock()
        models = [
            ModelInfo(
                class_name="User",
                table_name="users",
                fields=[ColumnInfo(name="id", type="int", sql_type="INTEGER", nullable=False)],
                relationships=[],
            )
        ]
        enums = {"StatusEnum": ["active"]}

        manager.log_generation_summary(models, enums)

        # Should log both enums and models
        assert manager.logger.info.call_count == 2

    def test_render_models_no_template_raises_error(self):
        """Test that render_models raises error when template not initialized."""
        with patch("supabase_models.components.output_manager.OutputManager._init_jinja_environment"):
            manager = OutputManager()

        manager.template = None
        with pytest.raises(RuntimeError, match="Template not initialized"):
            manager.render_models([], {})

    @patch("supabase_models.components.output_manager.OutputManager._init_jinja_environment")
    def test_render_and_write_models(self, mock_init_jinja):
        """Test rendering and writing models to file."""
        manager = OutputManager()

        # Mock template rendering
        mock_template = Mock()
        mock_template.render.return_value = "# Generated models\nclass User:\n    pass"
        manager.template = mock_template
        manager.logger = Mock()

        models = [
            ModelInfo(
                class_name="User",
                table_name="users",
                fields=[ColumnInfo(name="id", type="int", sql_type="INTEGER", nullable=False)],
                relationships=[],
            )
        ]
        enums = {}

        with tempfile.TemporaryDirectory() as temp_dir:
            output_filename = str(Path(temp_dir) / "test_models.py")
            manager.render_and_write_models(models, enums, output_filename)

            # Verify file was created and has content
            output_path = Path(output_filename)
            assert output_path.exists()
            content = output_path.read_text(encoding="utf-8")
            assert "Generated models" in content
            assert "class User" in content

            # Verify template was called with correct data
            mock_template.render.assert_called_once_with(models=models, enums=enums)

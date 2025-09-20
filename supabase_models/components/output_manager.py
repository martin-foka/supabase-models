"""Output management component for handling template rendering and file generation."""

import logging
from pathlib import Path

from jinja2 import Environment
from jinja2 import FileSystemLoader
from jinja2 import Template
from jinja2 import select_autoescape

from supabase_models.common.schemas import ModelInfo
from supabase_models.config import DEFAULT_TEMPLATE_NAME


class OutputManager:
    """Handles template loading, rendering, and output file generation."""

    def __init__(self, template_name: str | None = None, schema: str = "public"):
        self.template_name = template_name or DEFAULT_TEMPLATE_NAME
        self.env: Environment | None = None
        self.template: Template | None = None
        self.logger = logging.getLogger(__name__)
        self._init_jinja_environment()

    def _create_jinja_environment(self, loader_path: Path) -> Environment:
        """Create Jinja2 environment with common configuration."""
        env = Environment(
            loader=FileSystemLoader(loader_path),
            autoescape=select_autoescape(disabled_extensions=(), enabled_extensions=()),
            keep_trailing_newline=True,
            trim_blocks=True,
        )
        env.globals["n"] = "\n"  # Template variable for newlines
        return env

    def _init_jinja_environment(self) -> None:
        """Initialize Jinja2 environment and load template."""
        try:
            if self.template_name != DEFAULT_TEMPLATE_NAME:
                # Custom template: use absolute path or relative to current directory
                template_path: Path = Path(self.template_name)
                if template_path.is_absolute():
                    loader_path: Path = template_path.parent
                    template_file: str = template_path.name
                else:
                    loader_path = Path.cwd()
                    template_file = self.template_name

                self.env = self._create_jinja_environment(loader_path)
                self.template = self.env.get_template(template_file)
            else:
                # Built-in template: use package directory
                package_dir = Path(__file__).parent.parent  # Go up from components/ to supabase_models/
                self.env = self._create_jinja_environment(package_dir)
                self.template = self.env.get_template(self.template_name)
        except Exception as e:
            raise ValueError(f"Failed to load template '{self.template_name}': {e}") from e

    def render_models(self, models: list[ModelInfo], enums: dict[str, list[str]]) -> str:
        """Render models and enums using the configured template."""
        if not self.template:
            raise RuntimeError("Template not initialized")

        return self.template.render(models=models, enums=enums)

    def log_generation_summary(self, models: list[ModelInfo], enums: dict[str, list[str]]) -> None:
        """Log summary of found models and enums."""
        if enums:
            enum_names = list(enums.keys())
            self.logger.info(f"Found {len(enums)} enums: {', '.join(enum_names)}")

        model_names = [model.table_name for model in models]
        self.logger.info(f"Found {len(models)} tables: {', '.join(model_names)}")

    def render_and_write_models(
        self, models: list[ModelInfo], enums: dict[str, list[str]], output_filename: str
    ) -> None:
        """Render models and write to file."""
        content = self.render_models(models, enums)
        output_path = Path(output_filename)
        with output_path.open("w", encoding="utf-8") as f:
            f.write(content)
        self.logger.info(f"Generated {len(models)} models -> {output_path.resolve()}")
        self.log_generation_summary(models, enums)

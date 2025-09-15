"""Main generator class for supabase-models."""

import logging
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

import inflect
from jinja2 import Environment
from jinja2 import FileSystemLoader
from jinja2 import select_autoescape
from sqlalchemy import MetaData
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from supabase_models.config import DEFAULT_OUTPUT_FILE
from supabase_models.config import DEFAULT_SCHEMA
from supabase_models.config import DEFAULT_TEMPLATE_NAME
from supabase_models.parser import ConstraintParser
from supabase_models.schemas import ConstraintInfo
from supabase_models.schemas import FieldInfo
from supabase_models.schemas import RelationshipInfo
from supabase_models.schemas import TableModel


class ModelGenerator:
    """Generator for Pydantic models from database schema introspection using SQLAlchemy."""

    def __init__(
        self,
        database_url: str | None = None,
        output_file: str = DEFAULT_OUTPUT_FILE,
        template_name: str | None = None,
        schema: str = DEFAULT_SCHEMA,
        parser: ConstraintParser | None = None,
    ) -> None:
        self.logger = self._setup_logger()
        self.output_file = output_file
        self.template_name = template_name or DEFAULT_TEMPLATE_NAME
        self.schema = schema
        self.database_url = database_url or os.getenv("DATABASE_URL")

        if not self.database_url:
            raise ValueError("DATABASE_URL must be provided via environment variable or constructor parameter")

        self._validate_database_url()
        self._init_jinja_environment()
        self.db_engine: Engine | None = None
        self.parser = parser or ConstraintParser()
        self.inflect_engine = inflect.engine()

    def _setup_logger(self) -> logging.Logger:
        """Get logger instance - relies on CLI for configuration"""
        return logging.getLogger(__name__)

    def _validate_database_url(self) -> None:
        """Validate the database URL format"""
        try:
            parsed = urlparse(self.database_url)
            if not parsed.scheme or parsed.scheme not in ["postgresql", "postgres"]:
                raise ValueError("DATABASE_URL must be a PostgreSQL connection string")
            if not parsed.hostname or not parsed.username:
                raise ValueError("DATABASE_URL must include hostname and username")
        except Exception as e:
            raise ValueError(f"Invalid DATABASE_URL format: {e}") from e

    def _create_jinja_environment(self, loader_path: Path) -> Environment:
        """Create Jinja2 environment with common configuration"""
        env = Environment(
            loader=FileSystemLoader(loader_path),
            autoescape=select_autoescape(disabled_extensions=(), enabled_extensions=()),
            keep_trailing_newline=True,
            trim_blocks=True,
        )
        env.globals["n"] = "\n"  # Template variable for newlines
        return env

    def _init_jinja_environment(self) -> None:
        """Initialize Jinja2 environment and load template"""
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
                self.env = self._create_jinja_environment(Path(__file__).parent)
                self.template = self.env.get_template(self.template_name)
        except Exception as e:
            raise ValueError(f"Failed to load template '{self.template_name}': {e}") from e

    def get_engine(self) -> Engine:
        """Create and return SQLAlchemy engine"""
        if self.db_engine is None:
            try:
                if self.database_url is None:
                    raise ValueError("DATABASE_URL cannot be None")
                self.db_engine = create_engine(self.database_url, echo=False)
                # Test connection
                with self.db_engine.connect() as conn:
                    from sqlalchemy import text

                    conn.execute(text("SELECT 1"))

                # Set engine on parser
                self.parser.engine = self.db_engine

            except Exception as e:
                raise RuntimeError(f"Failed to connect to database: {e}") from e
        return self.db_engine

    def get_class_name_from_table(self, table_name: str) -> str:
        """Convert table name to singular class name using inflect.

        Examples:
            - products -> Product
            - article_categories -> ArticleCategory
        """
        table_parts: list[str] = table_name.split("_")
        singular_parts: list[str] = []

        for part in table_parts:
            singular: str | bool = self.inflect_engine.singular_noun(part)  # type: ignore[arg-type]
            # singular_noun returns False if word is already singular or not recognized
            singular_parts.append(str(singular) if singular else part)

        return "".join(word.title() for word in singular_parts)

    def reflect_database_schema(self) -> MetaData:
        """Reflect database schema using SQLAlchemy"""
        try:
            engine: Engine = self.get_engine()
            metadata: MetaData = MetaData()

            self.logger.debug(f"Reflecting database schema '{self.schema}'...")
            try:
                metadata.reflect(bind=engine, schema=self.schema if self.schema != "public" else None)
            except Exception as e:
                raise RuntimeError(
                    f"Failed to reflect schema '{self.schema}': {e}. Check if schema exists and is accessible."
                ) from e

            return metadata
        except Exception as e:
            raise RuntimeError(f"Failed to reflect database schema: {e}") from e

    def generate_models(self, table_name: str, table) -> TableModel:
        """Generate model data from SQLAlchemy table"""
        class_name: str = self.get_class_name_from_table(table_name)

        fields: list[FieldInfo] = []
        relationships: list[RelationshipInfo] = []

        for column in table.columns:
            field_name: str = column.name

            # Use parser for all field analysis
            field_type: str = self.parser.get_python_type(column, table_name)
            description: str | None = self.parser.get_column_description(column)
            is_required: bool = self.parser.is_required_field(column)
            is_pk: bool = self.parser.is_primary_key_field(column)
            default_value: str | None = self.parser.get_default_value(column)
            constraints: ConstraintInfo | None = self.parser.extract_constraints(column)
            constraint_params: str = self.parser.generate_constraint_params(constraints, field_type)
            relationship: RelationshipInfo | None = self.parser.extract_relationship_info(column)

            if relationship:
                relationship.related_model_class = self.get_class_name_from_table(relationship.foreign_table)
                relationships.append(relationship)

            field_info: FieldInfo = FieldInfo(
                name=field_name,
                type=field_type,
                description=description,
                is_required=is_required,
                is_primary_key=is_pk,
                default_value=default_value,
                constraints=constraints,
                constraint_params=constraint_params,
                relationship=relationship,
            )

            fields.append(field_info)

        return TableModel(class_name=class_name, table_name=table_name, fields=fields, relationships=relationships)

    def _collect_used_types(self, models: list[TableModel]) -> set[str]:
        """Collect all unique field types from models for conditional imports."""
        used_types: set[str] = set()

        for model in models:
            for field in model.fields:
                if field.type.startswith("Literal["):
                    used_types.add("Literal")
                else:
                    used_types.add(field.type)

        return used_types

    def _collect_enum_info(self, models: list[TableModel]) -> dict[str, list[str]]:
        """Collect enum information from all models."""
        enums: dict[str, list[str]] = {}
        for model in models:
            for field in model.fields:
                if field.constraints and field.constraints.enum_values:
                    enum_name: str = field.type  # This will be like "StatusEnum"
                    if enum_name not in enums:
                        enums[enum_name] = field.constraints.enum_values
        return enums

    def write_models_file(self, models: list[TableModel]) -> None:
        """Write generated models to file"""
        used_types: set[str] = self._collect_used_types(models)
        enum_info: dict[str, list[str]] = self._collect_enum_info(models)
        content: str = self.template.render(models=models, used_types=used_types, enums=enum_info)
        output_path: Path = Path(self.output_file)
        with output_path.open("w", encoding="utf-8") as f:
            f.write(content)
        self.logger.info(f"Generated {len(models)} models -> {output_path.resolve()}")

    def run(self) -> None:
        """Main execution method"""
        try:
            # Reflect database schema
            metadata: MetaData = self.reflect_database_schema()

            # Get table names
            table_names: list[str] = list(metadata.tables.keys())
            if self.schema and self.schema != "public":
                display_names: list[str] = [name.split(".")[-1] for name in table_names]
            else:
                display_names = table_names

            if not table_names:
                raise ValueError(f"No tables found in schema '{self.schema}'.")

            self.logger.info(f"Found {len(table_names)} tables: {', '.join(display_names)}")

            models: list[TableModel] = []
            for table_key in table_names:
                table = metadata.tables[table_key]
                table_name: str = table.name

                self.logger.debug(f"Processing table: {table_name}")

                if not table.columns:
                    self.logger.warning(f"Table '{table_name}' has no columns, skipping...")
                    continue

                try:
                    model: TableModel = self.generate_models(table_name, table)
                    models.append(model)
                except Exception as e:
                    self.logger.error(f"Failed to generate model for table '{table_name}': {e}")
                    if self.logger.isEnabledFor(logging.DEBUG):
                        self.logger.debug(f"Full error details for table '{table_name}':", exc_info=True)
                    continue

            # Write models to file
            self.write_models_file(models)

        except ValueError as e:
            self.logger.error(f"Configuration error: {e}")
            sys.exit(1)
        except RuntimeError as e:
            self.logger.error(f"Database or reflection error: {e}")
            sys.exit(1)
        except FileNotFoundError as e:
            self.logger.error(f"File operation error: {e}")
            sys.exit(1)
        except PermissionError as e:
            self.logger.error(f"Permission error (check file/directory permissions): {e}")
            sys.exit(1)
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")
            self.logger.error("This may be a bug - please report with --verbose output")
            sys.exit(1)
        finally:
            # Clean up db_engine
            if hasattr(self, "db_engine") and self.db_engine:
                try:
                    self.db_engine.dispose()
                except Exception as e:
                    self.logger.warning(f"Error during engine cleanup: {e}")

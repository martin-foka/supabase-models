"""Main generator class for supabase-models."""

import logging
import sys

from supabase_models.common.schemas import ModelInfo
from supabase_models.components.database_manager import DatabaseManager
from supabase_models.components.model_extractor import ModelExtractor
from supabase_models.components.output_manager import OutputManager
from supabase_models.config import DEFAULT_OUTPUT_FILE
from supabase_models.config import DEFAULT_SCHEMA
from supabase_models.config import DEFAULT_TEMPLATE_NAME


class ModelGenerator:
    """Generator for Pydantic models from database schema introspection using SQLAlchemy."""

    def __init__(
        self,
        database_url: str | None = None,
        output_filename: str = DEFAULT_OUTPUT_FILE,
        template_name: str | None = None,
        schema: str = DEFAULT_SCHEMA,
    ) -> None:
        self.template_name = template_name or DEFAULT_TEMPLATE_NAME
        self.output_filename = output_filename
        self.schema = schema
        self.database_url = database_url

        self.logger = self._setup_logger()
        self.database_manager = DatabaseManager(database_url, schema)
        self.model_extractor = ModelExtractor()
        self.output_manager = OutputManager(template_name)

    def _setup_logger(self) -> logging.Logger:
        """Get logger instance - relies on CLI for configuration"""
        return logging.getLogger(__name__)

    def run(self) -> None:
        """Main execution method"""
        try:
            # Reflect database schema using DatabaseManager
            metadata = self.database_manager.reflect_database_schema()
            engine = self.database_manager.get_engine()

            # Extract models using ModelExtractor (includes constraint parsing)
            models: list[ModelInfo] = self.model_extractor.extract_models_info(metadata, engine)
            if not models:
                raise ValueError(f"No tables found in schema '{self.schema}'.")

            # Collect enum information and log summary
            enums = self.model_extractor.collect_enum_info(models)

            # Render and write models using OutputManager
            self.output_manager.render_and_write_models(models, enums, self.output_filename)

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
            # Clean up database manager
            if hasattr(self, "database_manager"):
                self.database_manager.dispose()

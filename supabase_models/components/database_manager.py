"""Database management component for handling SQLAlchemy operations."""

import logging
import os
from urllib.parse import urlparse

from sqlalchemy import MetaData
from sqlalchemy import create_engine
from sqlalchemy import text
from sqlalchemy.engine import Engine


class DatabaseManager:
    """Handles database connection, validation, and schema reflection operations."""

    def __init__(self, database_url: str | None = None, schema: str = "public"):
        self.database_url = database_url
        self.schema = schema
        self.logger = logging.getLogger(__name__)
        self.db_engine: Engine | None = None

        self._validate_database_url()
        self.db_engine = self._create_engine()

    def _validate_database_url(self) -> None:
        """Validate the database URL format."""
        if not self.database_url:
            self.database_url = os.getenv("DATABASE_URL")

        if not self.database_url:
            raise ValueError("DATABASE_URL must be provided via environment variable or constructor parameter")

        try:
            parsed = urlparse(self.database_url)
            if not parsed.scheme or parsed.scheme not in ["postgresql", "postgres"]:
                raise ValueError("DATABASE_URL must be a PostgreSQL connection string")
            if not parsed.hostname or not parsed.username:
                raise ValueError("DATABASE_URL must include hostname and username")
        except Exception as e:
            raise ValueError(f"Invalid DATABASE_URL format: {e}") from e

    def _create_engine(self) -> Engine:
        """Create and return SQLAlchemy engine."""
        if not self.database_url:
            raise ValueError("Database URL is not set")
        try:
            engine = create_engine(self.database_url, echo=False)
            # Test connection
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return engine
        except Exception as e:
            raise RuntimeError(f"Failed to connect to database: {e}") from e

    def reflect_database_schema(self) -> MetaData:
        """Reflect database schema using SQLAlchemy."""
        if not self.db_engine:
            raise RuntimeError("Database engine not initialized")

        try:
            metadata: MetaData = MetaData()

            self.logger.debug(f"Reflecting database schema '{self.schema}'...")
            try:
                metadata.reflect(bind=self.db_engine, schema=self.schema if self.schema != "public" else None)
            except Exception as e:
                raise RuntimeError(
                    f"Failed to reflect schema '{self.schema}': {e}. Check if schema exists and is accessible."
                ) from e

            return metadata
        except Exception as e:
            raise RuntimeError(f"Failed to reflect database schema: {e}") from e

    def get_engine(self) -> Engine:
        """Get the database engine."""
        if not self.db_engine:
            raise RuntimeError("Database engine not initialized")
        return self.db_engine

    def dispose(self) -> None:
        """Clean up database engine."""
        if self.db_engine:
            try:
                self.db_engine.dispose()
                self.db_engine = None
            except Exception as e:
                self.logger.warning(f"Error during engine cleanup: {e}")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup."""
        self.dispose()

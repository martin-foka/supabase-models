"""Tests for the database manager component."""

import os
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from supabase_models.components.database_manager import DatabaseManager


class TestDatabaseManager:
    """Test DatabaseManager class."""

    @patch("supabase_models.components.database_manager.create_engine")
    def test_init_success(self, mock_create_engine):
        """Test successful initialization."""
        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine

        manager = DatabaseManager("postgresql://user:password@localhost:5432/testdb")

        assert manager.database_url == "postgresql://user:password@localhost:5432/testdb"
        assert manager.schema == "public"
        assert manager.db_engine == mock_engine

    @patch.dict(os.environ, {}, clear=True)
    def test_init_no_database_url_raises_error(self):
        """Test that missing database URL raises error."""
        with pytest.raises(ValueError, match="DATABASE_URL must be provided"):
            DatabaseManager()

    @pytest.mark.parametrize(
        "invalid_url,expected_error",
        [
            ("mysql://user:pass@localhost:5432/db", "must be a PostgreSQL connection string"),
            ("postgresql://user:pass@/db", "must include hostname and username"),
            ("postgresql://:pass@localhost:5432/db", "must include hostname and username"),
        ],
    )
    @patch("supabase_models.components.database_manager.create_engine")
    def test_validate_database_url_errors(self, mock_create_engine, invalid_url, expected_error):
        """Test database URL validation with various invalid URLs."""
        with pytest.raises(ValueError, match=expected_error):
            DatabaseManager(database_url=invalid_url)

    @patch("supabase_models.components.database_manager.create_engine")
    def test_connection_failure(self, mock_create_engine):
        """Test engine creation and disposal."""
        # Test connection failure
        mock_create_engine.side_effect = Exception("Connection refused")
        with pytest.raises(RuntimeError, match="Failed to connect to database"):
            DatabaseManager(database_url="postgresql://user:pass@localhost:5432/db")

        # Test successful creation and disposal
        mock_create_engine.side_effect = None
        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine

        manager = DatabaseManager("postgresql://user:pass@localhost:5432/db")
        manager.dispose()

        mock_engine.dispose.assert_called_once()
        assert manager.db_engine is None

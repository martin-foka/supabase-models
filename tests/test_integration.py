"""Integration tests for supabase-models."""

import tempfile
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import Boolean
from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import MetaData
from sqlalchemy import String
from sqlalchemy import Table
from sqlalchemy.types import Enum as SQLEnum

from supabase_models.generator import ModelGenerator
from supabase_models.parser import ConstraintParser


class TestIntegration:
    """Integration tests for multiple components working together."""

    def test_full_workflow_with_mocked_database(self):
        """Full workflow with mocked database."""
        metadata = MetaData()
        Table(
            "users",
            metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("username", String(50), nullable=False),
            Column("email", String(255), nullable=False),
            Column("is_active", Boolean, default=True),
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "test_models.py"

            generator = ModelGenerator(
                database_url="postgresql://test:test@localhost:5432/test", output_file=str(output_file)
            )

            with patch.object(generator, "reflect_database_schema", return_value=metadata):
                generator.run()

            assert output_file.exists()
            content = output_file.read_text(encoding="utf-8")
            assert "class User" in content

    def test_enum_handling_integration(self):
        """Enum handling across parser and generator."""
        enum_type = SQLEnum("active", "inactive", "pending", name="user_status")
        column = Column("status", enum_type, nullable=False)

        parser = ConstraintParser()

        python_type = parser.get_python_type(column, "users")
        assert python_type == "UserStatusEnum"

        constraints = parser.extract_constraints(column)
        assert constraints is not None
        assert constraints.enum_values == ["active", "inactive", "pending"]

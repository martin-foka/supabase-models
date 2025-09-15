"""Tests for the model generator module."""

import os
import tempfile
from pathlib import Path
from unittest.mock import Mock
from unittest.mock import patch

import pytest

from supabase_models.generator import ModelGenerator
from supabase_models.schemas import FieldInfo
from supabase_models.schemas import TableModel


class TestModelGenerator:
    """Test ModelGenerator class."""

    def test_init_with_database_url(self):
        """Test generator initialization with database URL."""
        database_url = "postgresql://user:password@localhost:5432/testdb"
        generator = ModelGenerator(database_url=database_url)
        assert generator.database_url == database_url
        assert generator.output_file == "models.py"
        assert generator.schema == "public"

    def test_init_without_database_url(self):
        """Test generator initialization fails without database URL."""
        with (
            patch.dict(os.environ, {}, clear=True),
            pytest.raises(ValueError, match="DATABASE_URL must be provided"),
        ):
            ModelGenerator()

    def test_validate_database_url_invalid_scheme(self):
        """Test database URL validation with invalid scheme."""
        with pytest.raises(ValueError, match="must be a PostgreSQL connection string"):
            ModelGenerator(database_url="mysql://user:pass@localhost:5432/db")

    def test_validate_database_url_missing_hostname(self):
        """Test database URL validation with missing hostname."""
        with pytest.raises(ValueError, match="must include hostname and username"):
            ModelGenerator(database_url="postgresql://user:pass@/db")

    def test_generate_models_class_name_conversion(self):
        """Class name conversion from table name."""
        database_url = "postgresql://user:password@localhost:5432/testdb"
        generator = ModelGenerator(database_url=database_url)
        mock_table = Mock()
        mock_table.columns = []

        result = generator.generate_models("user_profiles", mock_table)
        assert result.class_name == "UserProfile"

    def test_collect_used_types_basic_types(self):
        """Collection of basic types."""
        database_url = "postgresql://user:password@localhost:5432/testdb"
        generator = ModelGenerator(database_url=database_url)

        fields = [FieldInfo(name="id", type="int", is_required=False, is_primary_key=True)]
        table_model = TableModel(class_name="Test", table_name="test", fields=fields)

        used_types = generator._collect_used_types([table_model])
        assert "int" in used_types

    def test_collect_used_types_literal_types(self):
        """Collection of Literal types."""
        database_url = "postgresql://user:password@localhost:5432/testdb"
        generator = ModelGenerator(database_url=database_url)

        fields = [
            FieldInfo(name="status", type="Literal['active', 'inactive']", is_required=True, is_primary_key=False)
        ]
        table_model = TableModel(class_name="Test", table_name="test", fields=fields)

        used_types = generator._collect_used_types([table_model])
        assert "Literal" in used_types

    def test_collect_used_types_multiple_types(self):
        """Collection of multiple different types."""
        database_url = "postgresql://user:password@localhost:5432/testdb"
        generator = ModelGenerator(database_url=database_url)

        fields = [
            FieldInfo(name="id", type="int", is_required=False, is_primary_key=True),
            FieldInfo(name="name", type="str", is_required=True, is_primary_key=False),
            FieldInfo(name="status", type="Literal['active']", is_required=True, is_primary_key=False),
        ]
        table_model = TableModel(class_name="Test", table_name="test", fields=fields)

        used_types = generator._collect_used_types([table_model])
        assert len(used_types) == 3
        assert {"int", "str", "Literal"}.issubset(used_types)

    def test_collect_enum_info(self):
        """Collection of enum information from models."""
        from supabase_models.schemas import ConstraintInfo

        database_url = "postgresql://user:password@localhost:5432/testdb"
        generator = ModelGenerator(database_url=database_url)

        status_constraints = ConstraintInfo(enum_values=["active", "inactive", "pending"])
        priority_constraints = ConstraintInfo(enum_values=["low", "high"])

        fields = [
            FieldInfo(
                name="status", type="StatusEnum", constraints=status_constraints, is_required=True, is_primary_key=False
            ),
            FieldInfo(
                name="priority",
                type="PriorityEnum",
                constraints=priority_constraints,
                is_required=True,
                is_primary_key=False,
            ),
            FieldInfo(name="name", type="str", is_required=True, is_primary_key=False),
        ]

        table_model = TableModel(class_name="Test", table_name="test", fields=fields)
        enum_info = generator._collect_enum_info([table_model])

        assert len(enum_info) == 2
        assert enum_info["StatusEnum"] == ["active", "inactive", "pending"]
        assert enum_info["PriorityEnum"] == ["low", "high"]

    def test_write_models_file(self):
        """Writing models to file."""
        database_url = "postgresql://user:password@localhost:5432/testdb"
        generator = ModelGenerator(database_url=database_url)

        fields = [
            FieldInfo(name="id", type="int", is_required=False, is_primary_key=True),
            FieldInfo(name="name", type="str", is_required=True, is_primary_key=False),
        ]
        table_model = TableModel(class_name="TestTable", table_name="test_table", fields=fields)

        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "test_models.py"
            generator.output_file = str(output_file)

            with patch.object(
                generator.template, "render", return_value="# Generated models\nclass TestTable:\n    pass"
            ):
                generator.write_models_file([table_model])

                assert output_file.exists()
                content = output_file.read_text(encoding="utf-8")
                assert "Generated models" in content
                assert "class TestTable" in content

    @patch.object(ModelGenerator, "reflect_database_schema")
    def test_run_no_tables(self, mock_reflect):
        """Run execution with no tables found."""
        database_url = "postgresql://user:password@localhost:5432/testdb"
        generator = ModelGenerator(database_url=database_url)
        mock_metadata = Mock()
        mock_metadata.tables = {}
        mock_reflect.return_value = mock_metadata

        with pytest.raises(SystemExit):
            generator.run()

    def test_init_jinja_environment_template_not_found(self):
        """Jinja environment initialization with non-existent template."""
        database_url = "postgresql://user:password@localhost:5432/testdb"
        with pytest.raises(ValueError, match="Failed to load template"):
            ModelGenerator(database_url=database_url, template_name="non_existent_template.jinja2")

    def test_get_engine_connection_failure(self):
        """Database engine creation with connection failure."""
        database_url = "postgresql://user:password@localhost:5432/testdb"
        generator = ModelGenerator(database_url=database_url)

        with (
            patch("supabase_models.generator.create_engine", side_effect=Exception("Connection refused")),
            pytest.raises(RuntimeError, match="Failed to connect to database"),
        ):
            generator.get_engine()

    def test_reflect_database_schema_success(self):
        """Successful database schema reflection."""
        database_url = "postgresql://user:password@localhost:5432/testdb"
        generator = ModelGenerator(database_url=database_url)

        # Pre-set engine to avoid database connection
        generator.db_engine = Mock()

        with patch("supabase_models.generator.MetaData") as MockMetaData:
            mock_metadata = MockMetaData.return_value

            result = generator.reflect_database_schema()

            assert result == mock_metadata
            MockMetaData.assert_called_once()  # Verify MetaData() constructor called
            mock_metadata.reflect.assert_called_once_with(bind=generator.db_engine, schema=None)

    def test_reflect_database_schema_custom_schema(self):
        """Database schema reflection with custom schema."""
        database_url = "postgresql://user:password@localhost:5432/testdb"
        generator = ModelGenerator(database_url=database_url, schema="custom_schema")

        generator.db_engine = Mock()

        with patch("supabase_models.generator.MetaData") as MockMetaData:
            mock_metadata = MockMetaData.return_value

            result = generator.reflect_database_schema()

            assert result == mock_metadata
            MockMetaData.assert_called_once()
            mock_metadata.reflect.assert_called_once_with(bind=generator.db_engine, schema="custom_schema")

    def test_reflect_database_schema_reflection_failure(self):
        """Database schema reflection with reflection failure."""
        database_url = "postgresql://user:password@localhost:5432/testdb"
        generator = ModelGenerator(database_url=database_url, schema="invalid_schema")

        generator.db_engine = Mock()

        with patch("supabase_models.generator.MetaData") as MockMetaData:
            MockMetaData.return_value.reflect.side_effect = Exception("schema does not exist")

            with pytest.raises(RuntimeError, match="Failed to reflect schema 'invalid_schema'"):
                generator.reflect_database_schema()

            MockMetaData.assert_called_once()

    def test_get_engine_none_database_url(self):
        """Engine creation with None database URL."""
        generator = ModelGenerator(database_url="postgresql://user:password@localhost:5432/testdb")
        generator.database_url = None

        with pytest.raises(RuntimeError, match="Failed to connect to database: DATABASE_URL cannot be None"):
            generator.get_engine()

    def test_engine_caching(self):
        """Engine is cached after first creation."""
        database_url = "postgresql://user:password@localhost:5432/testdb"
        generator = ModelGenerator(database_url=database_url)

        # Pre-set engine to test caching behavior
        mock_engine = Mock()
        generator.db_engine = mock_engine

        result = generator.get_engine()
        assert result is mock_engine
        assert generator.db_engine is mock_engine

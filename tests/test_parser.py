"""Tests for the constraint parser module."""

import pytest

from supabase_models.common.schemas import ColumnInfo
from supabase_models.common.schemas import PydanticFieldInfo
from supabase_models.components.constraint_parser import ConstraintParser


@pytest.fixture
def parser():
    """Create ConstraintParser instance for testing."""
    return ConstraintParser()


class TestConstraintParser:
    """Test ConstraintParser class."""

    def test_parse_sql_type_constraints_varchar(self, parser):
        """Test parsing VARCHAR constraints."""
        column = ColumnInfo(name="test", type="str", sql_type="VARCHAR(100)", nullable=True)
        field_info = parser.parse_sql_type_constraints(column)

        assert field_info.max_length == 100

    def test_parse_sql_type_constraints_char(self, parser):
        """Test parsing CHAR constraints."""
        column = ColumnInfo(name="test", type="str", sql_type="CHAR(50)", nullable=True)
        field_info = parser.parse_sql_type_constraints(column)

        assert field_info.max_length == 50

    def test_parse_sql_type_constraints_numeric(self, parser):
        """Test parsing NUMERIC constraints."""
        column = ColumnInfo(name="test", type="float", sql_type="NUMERIC(10,2)", nullable=True)
        field_info = parser.parse_sql_type_constraints(column)

        assert field_info.le is not None
        assert field_info.ge is not None

    def test_parse_check_constraints_min_length(self, parser):
        """Test parsing check constraints for minimum length."""
        column = ColumnInfo(name="username", type="str", sql_type="VARCHAR(100)", nullable=False)
        column.check_constraint = "char_length(username) >= 5"

        field_info = PydanticFieldInfo()
        parser.parse_check_constraints(column, field_info)

        assert field_info.min_length == 5

    def test_parse_check_constraints_max_length(self, parser):
        """Test parsing check constraints for maximum length."""
        column = ColumnInfo(name="username", type="str", sql_type="VARCHAR(100)", nullable=False)
        column.check_constraint = "char_length(username) <= 50"

        field_info = PydanticFieldInfo()
        parser.parse_check_constraints(column, field_info)

        assert field_info.max_length == 50

    def test_parse_check_constraints_numeric_ge(self, parser):
        """Test parsing check constraints for numeric greater-than-or-equal."""
        column = ColumnInfo(name="price", type="float", sql_type="NUMERIC(10,2)", nullable=False)
        column.check_constraint = "price >= 0"

        field_info = PydanticFieldInfo()
        parser.parse_check_constraints(column, field_info)

        assert field_info.ge == 0.0

    def test_parse_check_constraints_numeric_gt(self, parser):
        """Test parsing check constraints for numeric greater-than."""
        column = ColumnInfo(name="quantity", type="int", sql_type="INTEGER", nullable=False)
        column.check_constraint = "quantity > 0"

        field_info = PydanticFieldInfo()
        parser.parse_check_constraints(column, field_info)

        assert field_info.gt == 0.0

    def test_parse_check_constraints_length_gt(self, parser):
        """Test parsing string length greater-than: char_length(col) > 2 -> min_length=3."""
        column = ColumnInfo(name="username", type="str", sql_type="VARCHAR(100)", nullable=False)
        column.check_constraint = "char_length(username) > 2"

        field_info = PydanticFieldInfo()
        parser.parse_check_constraints(column, field_info)

        assert field_info.min_length == 3

    def test_parse_check_constraints_length_lt(self, parser):
        """Test parsing string length less-than: char_length(col) < 50 -> max_length=49."""
        column = ColumnInfo(name="username", type="str", sql_type="VARCHAR(100)", nullable=False)
        column.check_constraint = "char_length(username) < 50"

        field_info = PydanticFieldInfo()
        parser.parse_check_constraints(column, field_info)

        assert field_info.max_length == 49

    def test_parse_check_constraints_numeric_le(self, parser):
        """Test parsing numeric less-than-or-equal: price <= 100 -> le=100."""
        column = ColumnInfo(name="price", type="float", sql_type="NUMERIC(10,2)", nullable=False)
        column.check_constraint = "price <= 100"

        field_info = PydanticFieldInfo()
        parser.parse_check_constraints(column, field_info)

        assert field_info.le == 100.0

    def test_parse_check_constraints_numeric_lt(self, parser):
        """Test parsing numeric less-than: price < 50 -> lt=50."""
        column = ColumnInfo(name="price", type="float", sql_type="NUMERIC(10,2)", nullable=False)
        column.check_constraint = "price < 50"

        field_info = PydanticFieldInfo()
        parser.parse_check_constraints(column, field_info)

        assert field_info.lt == 50.0

    def test_parse_check_constraints_pattern(self, parser):
        """Test parsing check constraints for regex patterns."""
        column = ColumnInfo(name="email", type="str", sql_type="VARCHAR(255)", nullable=False)
        column.check_constraint = "email ~ '^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$'"

        field_info = PydanticFieldInfo()
        parser.parse_check_constraints(column, field_info)

        assert field_info.pattern == "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$"

    def test_parse_check_constraints_no_constraint(self, parser):
        """Test parsing when no check constraint exists."""
        column = ColumnInfo(name="test", type="str", sql_type="VARCHAR(100)", nullable=True)
        column.check_constraint = None

        field_info = PydanticFieldInfo()
        parser.parse_check_constraints(column, field_info)

        # Should not modify field_info
        assert field_info.min_length is None
        assert field_info.max_length is None

    def test_generate_description_unique(self, parser):
        """Test description generation for unique fields."""
        column = ColumnInfo(name="username", type="str", sql_type="VARCHAR(100)", nullable=False)
        column.unique = True

        description = parser.generate_description(column)
        assert "Unique" in description

    def test_generate_description_foreign_key(self, parser):
        """Test description generation for foreign key fields."""
        column = ColumnInfo(name="user_id", type="int", sql_type="INTEGER", nullable=False)
        column.foreign_key = "users.id"

        description = parser.generate_description(column)
        assert "Foreign key to users.id" in description

    def test_generate_description_default(self, parser):
        """Test description generation for fields with defaults."""
        column = ColumnInfo(name="status", type="str", sql_type="VARCHAR(20)", nullable=False)
        column.default = "active"

        description = parser.generate_description(column)
        assert "Default: active" in description

    def test_generate_description_check_constraint(self, parser):
        """Test description generation for fields with check constraints."""
        column = ColumnInfo(name="age", type="int", sql_type="INTEGER", nullable=False)
        column.check_constraint = "age >= 18"

        description = parser.generate_description(column)
        assert "Check: age >= 18" in description

    def test_generate_description_multiple_attributes(self, parser):
        """Test description generation for fields with multiple attributes."""
        column = ColumnInfo(name="email", type="str", sql_type="VARCHAR(255)", nullable=False)
        column.unique = True
        column.default = "user@example.com"
        column.check_constraint = "email LIKE '%@%.%'"

        description = parser.generate_description(column)
        assert "Unique" in description
        assert "Default: user@example.com" in description
        assert "Check: email LIKE '%@%.%'" in description

    def test_enrich_column(self, parser):
        """Test complete column enrichment process."""
        column = ColumnInfo(name="username", type="str", sql_type="VARCHAR(50)", nullable=False)
        column.check_constraint = "char_length(username) >= 3"
        column.unique = True

        enriched_column = parser.enrich_column(column)

        assert enriched_column.pydantic_field is not None
        assert enriched_column.pydantic_field.max_length == 50
        assert enriched_column.pydantic_field.min_length == 3
        assert enriched_column.pydantic_field.description is not None
        assert "Unique" in enriched_column.pydantic_field.description

"""Tests for the constraint parser module."""

from unittest.mock import Mock

import pytest
from sqlalchemy import Column
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import MetaData
from sqlalchemy import String
from sqlalchemy import Table
from sqlalchemy import text
from sqlalchemy.types import Enum as SQLEnum

from supabase_models.parser import ConstraintParser
from supabase_models.schemas import ConstraintInfo


@pytest.fixture
def parser():
    """Create ConstraintParser instance for testing."""
    return ConstraintParser()


class TestConstraintParser:
    """Test ConstraintParser class."""

    @pytest.mark.parametrize(
        "column,expected",
        [
            (Column("name", String(100), nullable=False), "str"),
            (Column("id", Integer, primary_key=True), "int"),
            (Column("status", SQLEnum("active", "inactive", name="status_enum")), "StatusEnumEnum"),
        ],
    )
    def test_get_python_type_basic(self, parser, column, expected):
        """Python type extraction for basic column types."""
        result = parser.get_python_type(column, "test_table")
        assert result == expected

    def test_get_python_type_unknown(self, parser):
        """Python type extraction for unknown type."""
        mock_column = Mock()
        mock_type = Mock()
        type(mock_type).python_type = property(lambda x: (_ for _ in ()).throw(NotImplementedError()))
        mock_type.enums = None
        mock_column.type = mock_type
        mock_column.name = "unknown_field"

        python_type = parser.get_python_type(mock_column, "test_table")
        assert python_type == "Any"

    @pytest.mark.parametrize(
        "column,expected",
        [
            (Column("test", String(50), nullable=True), False),
            (Column("test", String(50), nullable=False, default="default"), False),
            (Column("test", String(50), nullable=False, autoincrement=True), False),
        ],
    )
    def test_is_required_field_logic(self, parser, column, expected):
        """Required field detection logic."""
        assert parser.is_required_field(column) == expected

    def test_is_required_field_true_case(self, parser):
        """Required field detection for truly required field."""
        required_col = Column("test", String(50), nullable=False, default=None, autoincrement=False)
        required_col.server_default = None
        assert parser.is_required_field(required_col)

    @pytest.mark.parametrize(
        "column,expected",
        [
            (Column("id", Integer, primary_key=True), True),
            (Column("name", String(50), primary_key=False), False),
        ],
    )
    def test_is_primary_key_field(self, parser, column, expected):
        """Primary key field detection."""
        assert parser.is_primary_key_field(column) == expected

    def test_get_default_value_none(self, parser):
        """Default value extraction when none exists."""
        column = Column("test", String(50))
        column.server_default = None

        result = parser.get_default_value(column)
        assert result is None

    def test_get_default_value_identity(self, parser):
        """Default value extraction for Identity columns."""
        column = Mock()
        mock_default = Mock()
        mock_default.start = 1
        mock_default.increment = 1
        column.server_default = mock_default

        result = parser.get_default_value(column)
        assert result == "Identity(start=1, increment=1)"

    def test_get_default_value_sequence(self, parser):
        """Default value extraction for sequences."""
        column = Mock()
        mock_default = Mock()
        mock_default.arg = "nextval('test_seq'::regclass)"
        del mock_default.start
        del mock_default.increment
        column.server_default = mock_default

        result = parser.get_default_value(column)
        assert result == "nextval('test_seq')"

    def test_extract_constraints_with_type_only(self, parser):
        """Constraint extraction with type constraints only."""
        column = Column("test", String(100), nullable=False)

        constraints = parser.extract_constraints(column)
        assert constraints is not None
        assert constraints.max_length == 100

    def test_extract_constraints_no_constraints(self, parser):
        """Constraint extraction when no constraints exist."""
        column = Column("test", String(), nullable=False)

        constraints = parser.extract_constraints(column)
        assert constraints is None

    def test_extract_type_constraints_string_length(self, parser):
        """Type constraint extraction for string length."""
        column = Column("test", String(100), nullable=False)
        constraints = ConstraintInfo()

        result = parser._extract_type_constraints(column, constraints)
        assert result is True
        assert constraints.max_length == 100

    def test_extract_type_constraints_enum_values(self, parser):
        """Type constraint extraction for enum values."""
        from sqlalchemy.types import Enum as SQLEnum

        constraints = ConstraintInfo()
        enum_type = SQLEnum("active", "inactive", name="status_enum")
        column = Column("status", enum_type, nullable=False)

        result = parser._extract_type_constraints(column, constraints)
        assert result is True
        assert constraints.enum_values == ["active", "inactive"]

    @pytest.mark.parametrize(
        "constraint_text,attr,expected_value",
        [
            ("CHECK ((char_length(name) >= 5))", "min_length", 5),
            ("CHECK ((char_length(name) <= 12))", "max_length", 12),
            ("CHECK ((length(name) >= 3))", "min_value", 3.0),
            ("CHECK ((price >= 6))", "min_value", 6.0),
            ("CHECK ((price <= 10))", "max_value", 10.0),
        ],
    )
    def test_parse_constraint_text_variants(self, parser, constraint_text, attr, expected_value):
        """Constraint text parsing for various CHECK constraint types."""
        constraints = ConstraintInfo()

        result = parser._parse_constraint_text(constraint_text, constraints)
        assert result is True
        assert getattr(constraints, attr) == expected_value

    def test_parse_constraint_text_exclusive_bounds(self, parser):
        """Constraint text parsing for exclusive bounds sets exclusive flags."""
        constraints = ConstraintInfo()

        # Test exclusive minimum bound
        result = parser._parse_constraint_text("CHECK ((score > 0))", constraints)
        assert result is True
        assert constraints.min_value == 0.0
        assert constraints.min_value_exclusive is True

        # Reset for next test
        constraints = ConstraintInfo()

        # Test exclusive maximum bound
        result = parser._parse_constraint_text("CHECK ((score < 100))", constraints)
        assert result is True
        assert constraints.max_value == 100.0
        assert constraints.max_value_exclusive is True

    def test_parse_constraint_text_regex_pattern(self, parser):
        """Constraint text parsing for regex pattern."""
        constraints = ConstraintInfo()
        constraint_text = "CHECK ((email ~* '^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$'::text))"

        result = parser._parse_constraint_text(constraint_text, constraints)
        assert result is True
        assert constraints.pattern == "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$"

    def test_generate_constraint_params_string_constraints(self, parser):
        """Constraint parameter generation for string constraints."""
        constraints = ConstraintInfo(min_length=5, max_length=100, pattern="^[a-zA-Z]+$")
        params = parser.generate_constraint_params(constraints, "str")

        expected_parts = {"min_length=5", "max_length=100", 'pattern=r"^[a-zA-Z]+$"'}
        assert set(params.split(", ")) == expected_parts

    def test_generate_constraint_params_numeric_constraints(self, parser):
        """Constraint parameter generation for numeric constraints."""
        constraints = ConstraintInfo(min_value=0, max_value=999)
        params = parser.generate_constraint_params(constraints, "int")

        # Test as set to avoid order dependency
        assert set(params.split(", ")) == {"ge=0", "le=999"}

    def test_get_column_description_with_default(self, parser):
        """Column description includes default value information."""
        column = Column("status", String(50), server_default=text("'active'"), autoincrement=False)

        result = parser.get_column_description(column)
        assert result == "Default: 'active'"

    def test_get_column_description_foreign_key_success(self, parser):
        """Column description for foreign key field - happy path."""
        metadata = MetaData()
        Table("users", metadata, Column("id", Integer, primary_key=True))
        posts_table = Table("posts", metadata, Column("user_id", Integer, ForeignKey("users.id"), autoincrement=False))

        result = parser.get_column_description(posts_table.c.user_id)
        assert result == "Foreign key to 'users'"

    def test_get_column_description_with_inline_unique(self, parser):
        """Column description includes inline unique constraint information."""
        column = Column("title", String(100), unique=True, autoincrement=False)

        result = parser.get_column_description(column)
        assert result == "Unique"

    def test_get_column_description_with_table_level_unique(self, parser):
        """Column description includes table-level unique constraint information."""
        from sqlalchemy import UniqueConstraint

        metadata = MetaData()
        table = Table(
            "articles", metadata, Column("title", String(100), autoincrement=False), UniqueConstraint("title")
        )

        result = parser.get_column_description(table.c.title)
        assert result == "Unique"

    def test_get_column_description_with_autoincrement(self, parser):
        """Column description includes autoincrement information."""
        column = Column("id", Integer, primary_key=True, autoincrement=True)

        result = parser.get_column_description(column)
        assert result == "Auto-increment"

    def test_get_column_description_no_description_parts(self, parser):
        """Column description when no description parts exist."""
        column = Mock()
        column.primary_key = False
        column.foreign_keys = []
        column.unique = False
        column.autoincrement = False
        column.table = None  # No table means no table-level unique constraints
        parser.get_default_value = lambda x: None

        result = parser.get_column_description(column)
        assert result is None

    def test_extract_check_constraints_no_engine(self, parser):
        """Check constraint extraction without engine."""
        parser.engine = None
        column = Column("test", String(50))
        constraints = ConstraintInfo()

        result = parser._extract_check_constraints(column, None, constraints)
        assert result is False

    def test_extract_type_constraints_no_constraints(self, parser):
        """Type constraint extraction when no type constraints exist."""
        column = Column("test", Integer)
        constraints = ConstraintInfo()

        result = parser._extract_type_constraints(column, constraints)
        assert result is False

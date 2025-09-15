"""Parser for database constraints and field information."""

import logging
import re

from sqlalchemy import Column
from sqlalchemy import text
from sqlalchemy.engine import Engine

from supabase_models.schemas import ConstraintInfo
from supabase_models.schemas import RelationshipInfo


class ConstraintParser:
    """Parser for extracting database constraints and generating field information."""

    def __init__(self, engine: Engine | None = None) -> None:
        self.engine = engine
        self.logger = logging.getLogger(__name__)

    def get_column_description(self, column: Column) -> str | None:
        """Generate description with type info, default values and constraints."""
        description_parts = []

        # Add constraint information
        # if column.primary_key:
        #     description_parts.append("Primary key")
        if column.foreign_keys:
            # Get foreign key table reference
            try:
                fk = next(iter(column.foreign_keys))
                fk_table = fk.column.table.name
                description_parts.append(f"Foreign key to '{fk_table}'")
            except (StopIteration, AttributeError) as e:
                self.logger.warning(f"Could not resolve foreign key for column '{column.name}': {e}")
                description_parts.append("Foreign key")

        # Add unique constraint information
        if self._is_unique_column(column):
            description_parts.append("Unique")

        # Add autoincrement information
        if column.autoincrement:
            description_parts.append("Auto-increment")

        # Add default value information
        default_value = self.get_default_value(column)
        if default_value:
            description_parts.append(f"Default: {default_value}")

        return "; ".join(description_parts) if description_parts else None

    def get_python_type(self, column: Column, table_name: str) -> str:
        """Get Python type from SQLAlchemy column, converting enums to custom Enum classes."""
        try:
            python_type = column.type.python_type
            if not python_type:
                raise AttributeError("No python_type available")
        except (NotImplementedError, AttributeError):
            # Handle types without python_type mapping - this is not supposed to happen usually
            self.logger.warning(f"Unknown type '{column.type}' for column '{column.name}' in table '{table_name}', using Any")
            return "Any"

        # Check if this is an enum field and return custom enum type
        if hasattr(column.type, "enums") and column.type.enums:
            enum_type_name = getattr(column.type, 'name', None)
            if enum_type_name:
                # Convert enum type name like 'user_status' to 'UserStatusEnum'
                enum_class_name = ''.join(word.capitalize() for word in enum_type_name.split('_')) + 'Enum'
            else:
                # Fallback to column name if no type name available
                enum_class_name = f"{column.name.title().replace('_', '')}Enum"
            return enum_class_name

        python_type_name = column.type.python_type.__name__

        # Handle DECIMAL/NUMERIC fields - accept both Decimal and float for convenience
        if python_type_name == "Decimal":
            return "Decimal | float"

        # Handle TIMETZ fields - use time | str to accept both Python time objects and timezone strings
        if python_type_name == "time" and hasattr(column.type, 'timezone') and column.type.timezone:
            return "time | str"


        # Use proper type annotations for generic types
        if python_type_name == "dict":
            return "dict[str, Any]"
        return python_type_name

    def is_required_field(self, column: Column) -> bool:
        """Check if field is required (not nullable and no default)."""
        return not column.nullable and not (column.default or column.server_default or column.autoincrement)

    def is_primary_key_field(self, column: Column) -> bool:
        """Check if field is a primary key."""
        return column.primary_key

    def get_default_value(self, column: Column) -> str | None:
        """Extract default value from column (Supabase uses server_default only)."""
        server_default = column.server_default
        if server_default is None:
            return None

        # PostgreSQL Identity columns
        if hasattr(server_default, 'start') and hasattr(server_default, 'increment'):
            result = f"Identity(start={server_default.start}, increment={server_default.increment})"
        else:
            # Sequences, literals, and functions
            result = str(server_default.arg if hasattr(server_default, "arg") else server_default)

        # Clean up: '2000'::numeric -> 2000, nextval('seq')::regclass -> nextval('seq')
        result = re.sub(r'::\w+\b', '', result)

        return result

    def extract_constraints(self, column: Column) -> ConstraintInfo | None:
        """Extract constraint information from SQLAlchemy column."""
        constraints = ConstraintInfo()
        has_constraints = False

        # Extract column type constraints (length, enums, precision)
        if self._extract_type_constraints(column, constraints):
            has_constraints = True

        # Extract database check constraints (ranges, patterns)
        if self.engine and hasattr(column, "table") and column.table is not None:
            if self._extract_check_constraints(column, self.engine, constraints):
                has_constraints = True

        return constraints if has_constraints else None

    def _extract_type_constraints(self, column: Column, constraints: ConstraintInfo) -> bool:
        """Extract constraints from column type definition."""
        found = False

        # Get column length limit (e.g., VARCHAR(100) -> max_length=100)
        if hasattr(column.type, "length") and column.type.length is not None:
            constraints.max_length = column.type.length
            found = True

        # Get enum values (e.g., ENUM('active', 'inactive') -> enum_values=['active', 'inactive'])
        if hasattr(column.type, "enums") and column.type.enums:
            constraints.enum_values = list(column.type.enums)
            found = True

        # Get numeric precision bounds (e.g., NUMERIC(10,2) -> range limits)
        if hasattr(column.type, "precision") and hasattr(column.type, "scale"):
            if column.type.precision and column.type.scale is not None:
                max_digits = column.type.precision - column.type.scale
                if max_digits > 0:
                    constraints.max_value = 10 ** max_digits - 1
                    constraints.min_value = -(10 ** max_digits - 1)
                    found = True

        return found

    def _extract_check_constraints(self, column: Column, engine: Engine, constraints: ConstraintInfo) -> bool:
        """Extract check constraints from database using PostgreSQL's built-in formatter."""
        try:
            table_name = column.table.name
            schema_name = column.table.schema or "public"
            column_name = column.name

            # Query PostgreSQL system catalogs for check constraints
            # Uses pg_get_constraintdef() which formats constraints cleanly

            query = text("""
                         SELECT pg_get_constraintdef(c.oid) as constraint_def
                         FROM pg_constraint c
                                  JOIN pg_class t ON c.conrelid = t.oid
                                  JOIN pg_namespace n ON t.relnamespace = n.oid
                                  JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY (c.conkey)
                         WHERE t.relname = :table_name
                           AND n.nspname = :schema_name
                           AND a.attname = :column_name
                           AND c.contype = 'c'
                         """)

            with engine.connect() as conn:
                result = conn.execute(
                    query, {"table_name": table_name, "schema_name": schema_name, "column_name": column_name}
                )

                found = False
                for row in result:
                    constraint_def = row.constraint_def
                    self.logger.debug(f"Found constraint for {column_name}: '{constraint_def}'")

                    if self._parse_constraint_text(constraint_def, constraints):
                        found = True
                        self.logger.debug(
                            f"Parsed constraint for {column_name}: min_value={constraints.min_value}, max_value={constraints.max_value}, min_length={constraints.min_length}, max_length={constraints.max_length}, pattern={constraints.pattern}"
                        )
                    else:
                        self.logger.debug(f"Could not parse constraint for {column_name}: '{constraint_def}'")

                return found

        except Exception as e:
            self.logger.warning(f"Failed to extract constraints for column '{column.name}': {e}")
            return False

    def _parse_constraint_text(self, constraint_text: str, constraints: ConstraintInfo) -> bool:
        """Parse constraint text using simple string operations."""
        found = False

        # Handle char_length() constraints for string length limits
        if "char_length(" in constraint_text:
            # Use simpler regex that handles nested parentheses
            # Look for char_length(anything) >= number
            char_length_ge = re.search(r'char_length\(.*?\)\s*>=\s*([+-]?\d+(?:\.\d+)?)', constraint_text)
            if char_length_ge:
                constraints.min_length = int(float(char_length_ge.group(1)))
                found = True

            # Look for char_length(anything) <= number
            char_length_le = re.search(r'char_length\(.*?\)\s*<=\s*([+-]?\d+(?:\.\d+)?)', constraint_text)
            if char_length_le:
                constraints.max_length = int(float(char_length_le.group(1)))
                found = True

            # Look for char_length(anything) > number (exclusive)
            char_length_gt = re.search(r'char_length\(.*?\)\s*>\s*([+-]?\d+(?:\.\d+)?)', constraint_text)
            if char_length_gt:
                constraints.min_length = int(float(char_length_gt.group(1))) + 1
                found = True

            # Look for char_length(anything) < number (exclusive)
            char_length_lt = re.search(r'char_length\(.*?\)\s*<\s*([+-]?\d+(?:\.\d+)?)', constraint_text)
            if char_length_lt:
                constraints.max_length = int(float(char_length_lt.group(1))) - 1
                found = True

            # If we found char_length constraints, skip the regular numeric parsing
            if found:
                return found

        # Handle numeric range constraints (for field >= value, field > value, etc.)
        # Look for inclusive minimum bounds (field >= number)
        if ">=" in constraint_text:
            parts = constraint_text.split(">=")
            for part in parts[1:]:  # Skip first part (before >=)
                numbers = re.findall(r"([+-]?\d+(?:\.\d+)?)", part)
                if numbers:
                    constraints.min_value = float(numbers[0])
                    found = True
                    break

        # Look for exclusive minimum bounds (field > number)
        elif ">" in constraint_text:
            parts = constraint_text.split(">")
            for part in parts[1:]:  # Skip first part (before >)
                numbers = re.findall(r"([+-]?\d+(?:\.\d+)?)", part)
                if numbers:
                    value = float(numbers[0])
                    constraints.min_value = value
                    constraints.min_value_exclusive = True
                    found = True
                    break

        # Handle numeric maximum constraints
        # Look for inclusive maximum bounds (field <= number)
        if "<=" in constraint_text:
            parts = constraint_text.split("<=")
            for part in parts[1:]:  # Skip first part (before <=)
                numbers = re.findall(r"([+-]?\d+(?:\.\d+)?)", part)
                if numbers:
                    constraints.max_value = float(numbers[0])
                    found = True
                    break

        # Look for exclusive maximum bounds (field < number)
        elif "<" in constraint_text:
            parts = constraint_text.split("<")
            for part in parts[1:]:  # Skip first part (before <)
                numbers = re.findall(r"([+-]?\d+(?:\.\d+)?)", part)
                if numbers:
                    value = float(numbers[0])
                    constraints.max_value = value
                    constraints.max_value_exclusive = True
                    found = True
                    break

        # Handle regex pattern constraints (~ and ~* operators in PostgreSQL)
        # Look for regex patterns like: field ~* '^pattern$'
        if "~" in constraint_text:
            # Extract text between single quotes after ~ or ~*
            if "'" in constraint_text:
                start = constraint_text.find("'")
                end = constraint_text.find("'", start + 1)
                if start != -1 and end != -1:
                    pattern = constraint_text[start + 1: end]
                    # Remove PostgreSQL type casting like ::text
                    pattern = re.sub(r'::[a-zA-Z_]+\b', '', pattern).strip()
                    if pattern:  # Only set if not empty after cleaning
                        constraints.pattern = pattern
                        found = True

        return found

    def _is_unique_column(self, column: Column) -> bool:
        """Check if column has unique constraint (inline or table-level)."""
        # Check inline unique constraint
        if column.unique:
            return True

        # Check table-level unique constraints
        if hasattr(column, 'table') and column.table is not None:
            from sqlalchemy.schema import UniqueConstraint
            for constraint in column.table.constraints:
                if isinstance(constraint, UniqueConstraint):
                    # Check if this column name is in the unique constraint
                    column_names = [col.name for col in constraint.columns]
                    if column.name in column_names:
                        return True

        return False

    def generate_constraint_params(self, constraints: ConstraintInfo | None, python_type: str) -> str:
        """Generate Pydantic Field() constraint parameters as string."""
        if not constraints:
            return ""

        params = []

        # For enum fields, skip length constraints since Literal types already restrict values
        if not constraints.enum_values:
            # String length constraints (for string types only)
            if python_type == "str":
                if constraints.min_length is not None:
                    params.append(f"min_length={constraints.min_length}")
                if constraints.max_length is not None:
                    params.append(f"max_length={constraints.max_length}")

        # Numeric value constraints (for numeric types only)
        if python_type in ["int", "float", "Decimal", "Decimal | float"]:
            if constraints.min_value is not None:
                if constraints.min_value_exclusive:
                    params.append(f"gt={constraints.min_value}")
                else:
                    params.append(f"ge={constraints.min_value}")
            if constraints.max_value is not None:
                if constraints.max_value_exclusive:
                    params.append(f"lt={constraints.max_value}")
                else:
                    params.append(f"le={constraints.max_value}")

        # Regex pattern constraint (for string types only)
        if python_type == "str" and constraints.pattern is not None:
            params.append(f'pattern=r"{constraints.pattern}"')

        # Return as comma-separated parameter string for Field()
        return ", ".join(params)

    def extract_relationship_info(self, column: Column) -> RelationshipInfo | None:
        """Extract foreign key relationship information from SQLAlchemy column."""
        if not column.foreign_keys:
            return None

        try:
            fk = next(iter(column.foreign_keys))
            foreign_table = fk.column.table.name
            foreign_key_field = column.name

            # Convert table name to class name
            related_model_class = foreign_table.replace('_', ' ').title().replace(' ', '')

            return RelationshipInfo(
                foreign_table=foreign_table,
                foreign_key_field=foreign_key_field,
                related_model_class=related_model_class
            )
        except (StopIteration, AttributeError) as e:
            self.logger.warning(f"Could not extract relationship info for column '{column.name}': {e}")
            return None

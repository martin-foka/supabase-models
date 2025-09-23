"""Parser for converting SQL constraints to Pydantic Field parameters."""

import logging
import re

from supabase_models.common.schemas import ColumnInfo
from supabase_models.common.schemas import PydanticFieldInfo
from supabase_models.common.utils import clean_cast


class ConstraintParser:
    """Parses SQL constraints and enriches ColumnInfo with PydanticFieldInfo."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def parse_sql_type_constraints(self, column: ColumnInfo) -> PydanticFieldInfo:
        """Parse SQL type definition into Pydantic Field parameters."""
        field_info = PydanticFieldInfo()
        sql_type = column.sql_type.upper()

        # VARCHAR(n) -> max_length=n
        varchar_match = re.match(r"VARCHAR\((\d+)\)", sql_type)
        if varchar_match:
            field_info.max_length = int(varchar_match.group(1))

        # CHAR(n) -> max_length=n
        char_match = re.match(r"CHAR\((\d+)\)", sql_type)
        if char_match:
            field_info.max_length = int(char_match.group(1))

        # NUMERIC(precision, scale) -> ge/le bounds
        numeric_match = re.match(r"NUMERIC\((\d+),(\d+)\)", sql_type)
        if numeric_match:
            precision = int(numeric_match.group(1))
            scale = int(numeric_match.group(2))
            max_digits = precision - scale
            if max_digits > 0:
                max_val = (10**max_digits) - (10 ** (-scale))
                field_info.le = max_val
                field_info.ge = -max_val

        return field_info

    def parse_check_constraints(self, column: ColumnInfo, field_info: PydanticFieldInfo) -> None:
        """Parse CHECK constraints and update PydanticFieldInfo."""
        if not column.check_constraint:
            return

        check = column.check_constraint

        # String length: char_length(col) >= 5 -> min_length=5
        min_len = re.search(r"char_length\([^)]+\)\s*>=\s*(\d+)", check)
        if min_len:
            field_info.min_length = int(min_len.group(1))

        # String length: char_length(col) <= 100 -> max_length=100
        max_len = re.search(r"char_length\([^)]+\)\s*<=\s*(\d+)", check)
        if max_len:
            field_info.max_length = int(max_len.group(1))

        # String length: char_length(col) > 2 -> min_length=3
        min_len_gt = re.search(r"char_length\([^)]+\)\s*>\s*(\d+)", check)
        if min_len_gt:
            field_info.min_length = int(min_len_gt.group(1)) + 1

        # String length: char_length(col) < 50 -> max_length=49
        max_len_lt = re.search(r"char_length\([^)]+\)\s*<\s*(\d+)", check)
        if max_len_lt:
            field_info.max_length = int(max_len_lt.group(1)) - 1

        # Numeric: col >= 0 -> ge=0
        ge_match = re.search(rf"{re.escape(column.name)}\s*>=\s*([+-]?\d+(?:\.\d+)?)", check)
        if ge_match:
            field_info.ge = float(ge_match.group(1))

        # Numeric: col > 0 -> gt=0
        gt_match = re.search(rf"{re.escape(column.name)}\s*>\s*([+-]?\d+(?:\.\d+)?)", check)
        if gt_match:
            field_info.gt = float(gt_match.group(1))

        # Numeric: col <= 100 -> le=100
        le_match = re.search(rf"{re.escape(column.name)}\s*<=\s*([+-]?\d+(?:\.\d+)?)", check)
        if le_match:
            field_info.le = float(le_match.group(1))

        # Numeric: col < 100 -> lt=100
        lt_match = re.search(rf"{re.escape(column.name)}\s*<\s*([+-]?\d+(?:\.\d+)?)", check)
        if lt_match:
            field_info.lt = float(lt_match.group(1))

        # BETWEEN: col BETWEEN 0 AND 100 -> ge=0, le=100
        between_match = re.search(
            rf"{re.escape(column.name)}\s+BETWEEN\s+([+-]?\d+(?:\.\d+)?)\s+AND\s+([+-]?\d+(?:\.\d+)?)",
            check,
            re.IGNORECASE,
        )
        if between_match:
            field_info.ge = float(between_match.group(1))
            field_info.le = float(between_match.group(2))

        # Pattern: col ~ '^pattern$' -> pattern='^pattern$'
        pattern_match = re.search(rf"{re.escape(column.name)}[^~]*~[^\']*\'([^\']+)\'", check)
        if pattern_match:
            field_info.pattern = pattern_match.group(1)

    def generate_description(self, column: ColumnInfo) -> str:
        """Generate field description from column metadata."""
        parts = []

        if column.unique:
            parts.append("Unique")

        if column.foreign_key:
            parts.append(f"Foreign key to {column.foreign_key}")

        # Include database default in description if it exists
        if column.default:
            parts.append(f"Default: {clean_cast(str(column.default))}")

        if column.check_constraint:
            parts.append(f"Check: {clean_cast(column.check_constraint)}")

        return "; ".join(parts)

    def enrich_column(self, column: ColumnInfo) -> ColumnInfo:
        """Enrich ColumnInfo with parsed PydanticFieldInfo."""
        # Start with SQL type constraints
        field_info = self.parse_sql_type_constraints(column)

        # Add check constraints
        self.parse_check_constraints(column, field_info)

        # Generate description
        field_info.description = self.generate_description(column)

        # Add to column
        column.pydantic_field = field_info

        return column

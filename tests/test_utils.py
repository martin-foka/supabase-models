"""Tests for the utility functions."""

import pytest

from supabase_models.common.utils import clean_cast


class TestUtils:
    """Test utility functions."""

    @pytest.mark.parametrize(
        "input_value,expected",
        [
            # PostgreSQL type casts
            ("'active'::text", "'active'"),
            ("123::numeric", "123"),
            ("true::boolean", "true"),
            ("'pending'::product_status", "'pending'"),
            ("'user@example.com'::varchar", "'user@example.com'"),
            # Multiple type casts
            ("'test'::text::varchar", "'test'"),
            # No type casts
            ("'simple_value'", "'simple_value'"),
            ("42", "42"),
            ("true", "true"),
            # Edge cases
            ("", ""),
            (None, None),
            ("::text", ""),  # Just the cast
            ("value::", "value::"),  # Double colon without type
        ],
    )
    def test_clean_cast(self, input_value, expected):
        """Test cleaning PostgreSQL type casts from strings."""
        result = clean_cast(input_value)
        assert result == expected

    def test_clean_cast_with_non_string(self):
        """Test clean_cast converts non-string inputs to string first."""
        result = clean_cast(123)
        assert result == "123"

    def test_clean_cast_complex_example(self):
        """Test clean_cast with a complex real-world example."""
        input_value = "'2023-12-31'::date"
        expected = "'2023-12-31'"
        result = clean_cast(input_value)
        assert result == expected

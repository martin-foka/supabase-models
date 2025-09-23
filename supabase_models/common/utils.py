"""Utility functions for supabase-models."""

import re


def clean_cast(value: str) -> str:
    """Remove PostgreSQL type casts from strings (::numeric, ::text, etc.)."""
    if not value:
        return value
    # Remove type casting like ::numeric, ::text, ::product_status, etc.
    return re.sub(r"::[a-zA-Z_]+", "", str(value))

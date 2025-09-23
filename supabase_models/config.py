"""Configuration constants for supabase-pykit."""

# Default configuration
DEFAULT_OUTPUT_FILE = "models.py"
DEFAULT_TEMPLATE_NAME = "default.jinja2"
DEFAULT_TIMEOUT = 10

# Database connection settings
DEFAULT_SCHEMA = "public"

# SQL to Python type mapping
SQL_TYPE_MAPPING = {
    "BIGINT": "int",
    "INTEGER": "int",
    "SMALLINT": "int",
    "SERIAL": "int",
    "BIGSERIAL": "int",
    "VARCHAR": "str",
    "TEXT": "str",
    "CHAR": "str",
    "CHARACTER": "str",
    "BOOLEAN": "bool",
    "BOOL": "bool",
    "NUMERIC": "Decimal | float",
    "DECIMAL": "Decimal | float",
    "REAL": "float",
    "FLOAT": "float",
    "DOUBLE": "float",
    "TIMESTAMP": "datetime",
    "TIMESTAMPTZ": "datetime",
    "DATE": "date",
    "TIME": "time",
    "TIMETZ": "time",
    "UUID": "UUID",
    "JSON": "dict[str, Any]",
    "JSONB": "dict[str, Any]",
    "ARRAY": "list[Any]",
}

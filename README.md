# Supabase Models

[![Quality Check](https://github.com/martin-foka/supabase-models/actions/workflows/quality-check.yml/badge.svg)](https://github.com/martin-foka/supabase-models/actions/workflows/quality-check.yml)
[![PyPI version](https://img.shields.io/pypi/v/supabase-models?label=pypi%20package)](https://pypi.org/project/supabase-models/)
[![Python versions](https://img.shields.io/pypi/pyversions/supabase-models)](https://pypi.org/project/supabase-models/)
[![License](https://img.shields.io/pypi/l/supabase-models)](https://pypi.org/project/supabase-models/)
[![PyPI downloads](https://img.shields.io/pypi/dm/supabase-models?&color=yellow)](https://pypi.org/project/supabase-models/)

Generate type-safe Pydantic models from your Supabase database schema, ready to be used with [supabase-py](https://github.com/supabase/supabase-py).

## Key Features
- **Schema introspection**: Automatically extracts table structures, constraints, and relationships
- **Type-safe models**: Creates Pydantic models with type hints and validation
- **JSON serialization**: Models include `dump()` and `load()` methods for sending/receiving data via supabase-py
- **Constraint validation**: Translates database column constraints to Pydantic validators
- **Customizable output**: Uses a built-in template by default, or modify the Jinja2 template to match your needs

## Prerequisites

This package is designed to work with:
- [supabase-py](https://github.com/supabase/supabase-py) - the recommended Supabase Python client
- PostgreSQL databases (including Supabase projects)

## Installation & Setup

```bash
pip install supabase-models
# or with uv (recommended)
uv add supabase-models
```

## Quick Start Guide

### 1. Generate Models

```bash
supabase-models --database-url postgresql://user:password@host:port/db
```

**Default behavior:**
- Output file: `models.py` in current directory
- Schema: `public`
- Template: Built-in Jinja2 template

> [!TIP]
> See [CLI Reference](#cli-reference) for all available options and configuration methods


### 2. Use with supabase-py

The generated models provide `dump()` and `load()` methods to simplify working with supabase-py:
- **`dump()`** - Use when sending data to Supabase
- **`load()`** - Use when loading received data from Supabase responses

```python
from supabase import create_client, Client
from models import Product, ProductStatusEnum  # Noqa # Your generated models

# Initialize Supabase client
supabase_client: Client = ... # Noqa

# INSERT: Create and insert a new product
product = Product(name="Wireless Mouse", sku="WM-2024", price=29.99, status=ProductStatusEnum.DRAFT)
insert_response = supabase_client.table(Product.table_name).insert(product.dump()).execute()

# SELECT: Query and parse products back to typed models
select_response = supabase_client.table(Product.table_name).select("*").execute()
products: list[Product] = Product.load(select_response)
```

See the section below for details on how these models are generated.

## Generated Model Examples

Given this database schema:

```sql
-- Create enum types
CREATE TYPE product_status AS ENUM ('draft', 'active', 'archived');

-- Create tables
CREATE TABLE categories (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL
);

CREATE TABLE products (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    sku VARCHAR(20) UNIQUE NOT NULL CHECK (sku ~ '^[A-Z]{2,3}-[0-9]{3,4}$'),
    price DECIMAL(10,2) CHECK (price > 1),
    category_id BIGINT REFERENCES categories(id),
    status product_status DEFAULT 'draft',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

The tool generates the following models:

*Note: Simplified example showing key capabilities. Some code sections abbreviated for clarity.*

```python
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, ClassVar
from pydantic import BaseModel, Field


class ProductStatusEnum(str, Enum):
    """Enum for product_status values."""
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class SupabaseBaseModel(BaseModel):
    """Base model with supabase-py integration helpers."""

    ...
    # All helper logic is automatically generated
    # Main methods: load() for parsing responses, dump() for preparing data
    # Additional utilities for validation and type conversion are included


class Product(SupabaseBaseModel):
    """Model for 'products' table.

    Attributes:
        id (int | None): Primary key column; Auto-increment.
        name (str | None): Required column.
        sku (str | None): Required column; Unique.
        price (Decimal | float | None): Optional column.
        category_id (int | None): Optional column; Foreign key to 'categories'.
        status (ProductStatusEnum | None): Optional column; Default: 'draft'.
        created_at (datetime | None): Optional column; Default: now().
        categories (Category | None): Related table Category (requires categories(*) in query)
    """
    table_name: ClassVar[str] = "products"
    _required_columns: ClassVar[list[str]] = ["name", "sku"]

    # Primary key columns:
    id: int | None = Field(default=None, description="Auto-increment")

    # Required columns:
    name: str | None = Field(default=None, max_length=100)
    sku: str | None = Field(default=None, description="Unique", max_length=20, pattern=r"^[A-Z]{2,3}-[0-9]{3,4}$")

    # Optional columns:
    price: Decimal | float | None = Field(default=None, gt=1)
    category_id: int | None = Field(default=None, description="Foreign key to 'categories'")
    status: ProductStatusEnum | None = Field(default=None, description="Default: 'draft'")
    created_at: datetime | None = Field(default=None, description="Default: now()")

    # Relations:
    categories: "Category | None" = Field(default=None, description="Related table Category. Include categories(*) in query to populate.")


class Category(SupabaseBaseModel):
    """Model for 'categories' table.

    Attributes:
        id (int | None): Primary key column; Auto-increment; Default: nextval('categories_id_seq').
        name (str | None): Required column.
    """
    table_name: ClassVar[str] = "categories"
    _required_columns: ClassVar[list[str]] = ["name"]

    # Primary key columns:
    id: int | None = Field(default=None, description="Auto-increment; Default: nextval('categories_id_seq')")

    # Required columns:
    name: str | None = Field(default=None, max_length=100)
```

## Supported PostgreSQL Features

Converts PostgreSQL schemas to Pydantic models with automatic detection of primary keys, foreign keys, NOT NULL
constraints, defaults, and unique constraints.

### Data Types
| PostgreSQL Feature                 | Pydantic Output                                |
|------------------------------------|------------------------------------------------|
| `VARCHAR(n)`, `CHAR(n)`, `TEXT`    | `str` with `Field(max_length=n)`               |
| `INTEGER`, `BIGINT`, `SMALLINT`    | `int`                                          |
| `DECIMAL(p,s)`, `NUMERIC(p,s)`     | `Decimal \| float` with precision bounds       |
| `REAL`, `DOUBLE PRECISION`         | `float`                                        |
| `BOOLEAN`                          | `bool`                                         |
| `DATE`, `TIMESTAMP`, `TIMESTAMPTZ` | `datetime`                                     |
| `TIME`, `TIMETZ`                   | `time \| str` (for timezone types)             |
| `JSON`, `JSONB`                    | `dict[str, Any]`                               |
| `UUID`                             | `UUID`                                         |
| `ARRAY`                            | `list[Any]`                                    |
| `SERIAL`, `BIGSERIAL`              | `int` with auto-increment                      |
| `ENUM types`                       | `CustomEnum(str, Enum)`                        |

### Check Constraints
| PostgreSQL Feature                 | Pydantic Output                                |
|------------------------------------|------------------------------------------------|
| `CHECK (x > 0)`                    | `Field(gt=0)`                                  |
| `CHECK (x >= 10)`                  | `Field(ge=10)`                                 |
| `CHECK (x <= 1000)`                | `Field(le=1000)`                               |
| `CHECK (x < 100)`                  | `Field(lt=100)`                                |
| `CHECK (x BETWEEN 0 AND 100)`      | `Field(ge=0, le=100)`                          |
| `CHECK (char_length(x) >= 5)`      | `Field(min_length=5)`                          |
| `CHECK (char_length(x) <= 50)`     | `Field(max_length=50)`                         |
| `CHECK (char_length(x) > 2)`       | `Field(min_length=3)`                          |
| `CHECK (char_length(x) < 10)`      | `Field(max_length=9)`                          |
| `CHECK (x ~ '^.+@.+$')`            | `Field(pattern=r"^.+@.+$")`                    |

### Schema Features
| PostgreSQL Feature                 | Pydantic Output                                |
|------------------------------------|------------------------------------------------|
| `PRIMARY KEY`                      | Field descriptions                             |
| `FOREIGN KEY`                      | Relationship fields and descriptions           |
| `NOT NULL`                         | Required field detection                       |
| `DEFAULT value`                    | Field descriptions                             |
| `UNIQUE`                           | Field descriptions                             |
| `AUTOINCREMENT`                    | Field descriptions                             |

> [!NOTE]
> Constraint parsing is still work in progress. If something doesn't work as expected or you need other constraint types, please [open an issue](https://github.com/martin-foka/supabase-models/issues).

## CLI Reference

```bash
supabase-models [OPTIONS]

Options:
  --database-url TEXT    PostgreSQL connection string
  -o, --output TEXT      Output file (default: models.py)
  -s, --schema TEXT      Database schema (default: public)
  -t, --template TEXT    Custom Jinja2 template file
  -v, --verbose          Enable verbose logging
  --version              Show version
  --help                 Show help
```


### Usage Examples

```bash
# Basic usage with environment variable
export DATABASE_URL="postgresql://user:password@host:port/db"
supabase-models

# Direct database URL
supabase-models --database-url "postgresql://user:password@host:port/db"

# Custom output and schema
supabase-models --output app/models.py --schema public --verbose

# Multiple schemas
supabase-models --schema auth --output auth_models.py
supabase-models --schema public --output public_models.py
```


## Development & Testing

```bash
# Install development dependencies
uv sync

# Format and lint
uv run ruff format .
uv run ruff check .

# Type checking
uv run mypy .

# Run tests
uv run pytest

# Set up pre-commit hooks (recommended)
uv run pre-commit install

# Run all pre-commit hooks manually
uv run pre-commit run --all-files
```

## Contributing

For issues and contributions, visit the [GitHub repository](https://github.com/martin-foka/supabase-models).

import base64
from collections.abc import Callable
from datetime import date
from datetime import datetime
from datetime import time
from decimal import Decimal
from enum import Enum
from typing import Any
from typing import ClassVar
from uuid import UUID

from pydantic import BaseModel
from pydantic import Field
from pydantic import field_serializer
from pydantic import model_validator


class SupabaseBaseModel(BaseModel):
    """Base model with data loading and serialization helpers."""

    # Type serialization mapping for efficiency
    _SERIALIZERS: dict[type, Callable[[Any], str]] = {
        datetime: lambda v: v.isoformat(),
        date: lambda v: v.isoformat(),
        time: lambda v: v.isoformat(),
        Decimal: lambda v: str(v),
        UUID: lambda v: str(v),
        bytes: lambda v: base64.b64encode(v).decode("utf-8"),
    }

    @field_serializer("*", when_used="always")
    def serialize_fields(self, value: Any) -> Any:
        """Serialize special types to JSON-compatible formats."""
        serializer = self._SERIALIZERS.get(type(value))
        if serializer:
            return serializer(value)
        return value

    @model_validator(mode="after")
    def validate_required_columns(self):
        """Validate required columns are not None."""
        if hasattr(self.__class__, "_required_columns"):
            missing = [f for f in self._required_columns if getattr(self, f) is None]
            if missing:
                raise ValueError(f"Required columns cannot be None: {missing}")
        return self

    def dump(self) -> dict[str, Any]:
        """Convert model to dict excluding unset fields.

        Examples:
            >>> # Insert a new product into Supabase
            >>> supabase_client: Client = ...  # noqa
            >>> product = Product(name="Test", price=10.99)
            >>> product_data = product.dump()
            >>> supabase_client.table(Product.table_name).insert(product_data).execute()
        """
        # Only include explicitly set fields
        field_names = list(self.model_fields.keys())
        exclude_set = {f for f in field_names if f not in self.__pydantic_fields_set__}
        return self.model_dump(exclude=exclude_set if exclude_set else None)
        # return self.model_dump(exclude_unset=True)

    def __iter__(self) -> Any:
        """Enable dict(model) conversion with validation - calls dump() internally."""
        return iter(self.dump().items())

    @classmethod
    def load(cls, response_or_data: Any) -> Any:
        """Load Supabase response data into model instances.

        Examples:
            >>> # Load products from Supabase response
            >>> supabase_client: Client = ...  # noqa
            >>> response = supabase_client.table(Product.table_name).select().execute()
            >>> products: list[Product] = Product.load(response)
        """
        # Extract data from Supabase response
        data = getattr(response_or_data, "data", response_or_data)
        if isinstance(data, list):
            return [cls(**record) for record in data]
        return cls(**data)

    def __str__(self) -> str:
        """String representation showing all fields."""
        return repr(self)


class ProductStatusEnum(str, Enum):
    """Enum for ProductStatusEnum values."""

    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class Category(SupabaseBaseModel):
    """Model for 'categories' table.

    Attributes:
        id (int | None): Primary key column; Auto-increment; Default: nextval('categories_id_seq').
        name (str | None): Required column.
        nickname (str | None): Optional column.
    """

    table_name: ClassVar[str] = "categories"
    _required_columns: ClassVar[list[str]] = ["name"]

    # Primary key columns:
    id: int | None = Field(default=None, description="Default: nextval('categories_id_seq')")

    # Required columns:
    name: str | None = Field(default=None, max_length=100)

    # Optional columns:
    nickname: str | None = Field(
        default=None,
        description="Check: char_length(nickname) > 3 AND char_length(nickname) < 15",
        max_length=14,
        min_length=4,
    )


class Product(SupabaseBaseModel):
    """Model for 'products' table.

    Attributes:
        id (int | None): Primary key column; Auto-increment; Default: nextval('products_id_seq').
        name (str | None): Required column.
        sku (str | None): Required column; Unique.
        price (Decimal | float | None): Optional column; Default: '9'.
        category_id (int | None): Optional column; Foreign key to 'categories'.
        status (ProductStatusEnum | None): Optional column; Default: 'draft'.
        created_at (datetime | None): Optional column; Default: now().
        categories (Category | None): Related table Category (requires categories(*) in query).
    """

    table_name: ClassVar[str] = "products"
    _required_columns: ClassVar[list[str]] = ["name", "sku"]

    # Primary key columns:
    id: int | None = Field(default=None, description="Default: nextval('products_id_seq')")

    # Required columns:
    name: str | None = Field(default=None, description="Check: length(name) < 102", max_length=100)
    sku: str | None = Field(
        default=None,
        description="Unique; Check: sku ~ '^[A-Z]{2,3}-[0-9]{3,4}$'",
        max_length=20,
        pattern=r"^[A-Z]{2,3}-[0-9]{3,4}$",
    )

    # Optional columns:
    price: Decimal | float | None = Field(default=None, description="Default: '9'; Check: price > 1", gt=1.0)
    category_id: int | None = Field(default=None, description="Foreign key to categories.id")
    status: ProductStatusEnum | None = Field(default=None, description="Default: 'draft'", max_length=8)
    created_at: datetime | None = Field(default=None, description="Default: now()")

    # Relations:
    categories: "Category | None" = Field(
        default=None, description="Related table Category. Include categories(*) in query to populate."
    )

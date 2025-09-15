"""Schema definitions for Supabase Pydantic generation."""

from pydantic import BaseModel


class ConstraintInfo(BaseModel):
    """Information about database constraints that can be applied to Pydantic fields."""

    min_length: int | None = None
    max_length: int | None = None
    min_value: int | float | None = None
    max_value: int | float | None = None
    min_value_exclusive: bool = False  # True for > constraints, False for >=
    max_value_exclusive: bool = False  # True for < constraints, False for <=
    pattern: str | None = None
    enum_values: list[str] | None = None


class RelationshipInfo(BaseModel):
    """Information about a foreign key relationship."""

    foreign_table: str
    foreign_key_field: str
    related_model_class: str


class FieldInfo(BaseModel):
    """Information about a database field."""

    name: str
    type: str
    description: str | None = None
    is_required: bool
    is_primary_key: bool
    default_value: str | None = None
    constraints: ConstraintInfo | None = None
    constraint_params: str = ""
    relationship: RelationshipInfo | None = None


class TableModel(BaseModel):
    """Model representing a database table."""

    class_name: str
    table_name: str
    fields: list[FieldInfo]
    relationships: list[RelationshipInfo] = []

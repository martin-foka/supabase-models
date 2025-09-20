"""Schema definitions for supabase-models."""

from typing import Any

from pydantic import BaseModel


class PydanticFieldInfo(BaseModel):
    """Pydantic Field parameters parsed from database constraints."""

    default: Any | None = None
    description: str | None = None
    max_length: int | None = None
    min_length: int | None = None
    pattern: str | None = None
    gt: float | None = None
    ge: float | None = None
    lt: float | None = None
    le: float | None = None


class ColumnInfo(BaseModel):
    """Information about a database column for template rendering."""

    name: str
    type: str
    sql_type: str
    nullable: bool
    primary_key: bool = False
    foreign_key: str | None = None
    unique: bool = False
    default: Any | None = None
    enum_values: list[str] | None = None
    check_constraint: str | None = None
    pydantic_field: PydanticFieldInfo | None = None


class RelationshipInfo(BaseModel):
    """Information about a relationship field."""

    name: str
    related_model: str


class ModelInfo(BaseModel):
    """Information about a model for template rendering."""

    class_name: str
    table_name: str
    fields: list[ColumnInfo]
    relationships: list[RelationshipInfo] = []

"""Model extraction component for converting database metadata to ModelInfo objects."""

import re

import inflect
from sqlalchemy import MetaData
from sqlalchemy import inspect
from sqlalchemy.engine import Engine

from supabase_models.common.schemas import ColumnInfo
from supabase_models.common.schemas import ModelInfo
from supabase_models.common.schemas import RelationshipInfo
from supabase_models.common.utils import clean_cast
from supabase_models.components.constraint_parser import ConstraintParser
from supabase_models.config import SQL_TYPE_MAPPING


class ModelExtractor:
    """Handles extraction of model information from database metadata."""

    def __init__(self):
        self.inflect_engine = inflect.engine()
        self.constraint_parser = ConstraintParser()

    def extract_models_info(self, metadata: MetaData, db_engine: Engine) -> list[ModelInfo]:
        """Extract model information directly from metadata.
        TODO: This method is too complex and does too many things. Should be refactored into smaller methods
        """
        inspector = inspect(db_engine)
        models = []

        for table_name in metadata.tables:
            table = metadata.tables[table_name]
            fields = []

            # Get constraint information for the table
            unique_constraints = inspector.get_unique_constraints(table_name)
            check_constraints = inspector.get_check_constraints(table_name)

            # Get column information directly from inspector for better default detection
            columns_info = inspector.get_columns(table_name)

            for column in table.columns:
                # Find matching column info from inspector
                inspector_col = next((c for c in columns_info if c["name"] == column.name), None)

                # Get python type using direct mapping
                sql_type = str(column.type)
                base_type = sql_type.upper().split("(")[0]

                # Check if this is an enum type
                enum_values = None
                if hasattr(column.type, "enums") and column.type.enums and hasattr(column.type, "name"):
                    enum_name = f"{column.type.name.title().replace('_', '')}Enum"
                    python_type = enum_name
                    enum_values = list(column.type.enums)
                else:
                    python_type = SQL_TYPE_MAPPING.get(base_type, "Any")

                # Check for foreign keys
                foreign_key = None
                for fk in column.foreign_keys:
                    foreign_key = f"{fk.column.table.name}.{fk.column.name}"
                    break

                # Check for unique constraints on this column
                unique = False
                for uc in unique_constraints:
                    if len(uc["column_names"]) == 1 and uc["column_names"][0] == column.name:
                        unique = True
                        break

                # Check for check constraints on this column
                check_constraint = None
                for cc in check_constraints:
                    # Check if constraint is specifically for this column
                    sqltext = cc.get("sqltext", "")
                    if re.search(rf"\b{re.escape(column.name)}\b", sqltext):
                        check_constraint = sqltext
                        break

                # Clean default value of PostgreSQL type casts
                raw_default = inspector_col.get("default") if inspector_col else column.default
                default = clean_cast(str(raw_default)) if raw_default else None

                field_info = ColumnInfo(
                    name=column.name,
                    type=python_type,
                    sql_type=sql_type,
                    nullable=bool(column.nullable),
                    primary_key=column.primary_key,
                    foreign_key=foreign_key,
                    unique=unique,
                    default=default,
                    enum_values=enum_values,
                    check_constraint=check_constraint,
                )

                # Enrich field with constraint parsing during extraction
                field_info = self.constraint_parser.enrich_column(field_info)
                fields.append(field_info)

            # Extract relationships from foreign keys
            relationships = []
            for field in fields:
                if field.foreign_key:
                    # Parse foreign key: "categories.id" -> table_name = "categories"
                    related_table = field.foreign_key.split(".")[0]
                    related_class = self.get_class_name_from_table(related_table)

                    relationship = RelationshipInfo(name=related_table, related_model=related_class)
                    relationships.append(relationship)

            class_name = self.get_class_name_from_table(table_name)
            model_info = ModelInfo(
                class_name=class_name, table_name=table_name, fields=fields, relationships=relationships
            )
            models.append(model_info)

        return models

    def collect_enum_info(self, models: list[ModelInfo]) -> dict[str, list[str]]:
        """Collect enum information from all models."""
        enums = {}
        for model in models:
            for field in model.fields:
                if field.enum_values:
                    enums[field.type] = field.enum_values
        return enums

    def get_class_name_from_table(self, table_name: str) -> str:
        """Convert table name to singular class name using inflect.

        Examples:
            - products -> Product
            - article_categories -> ArticleCategory
        """
        table_parts: list[str] = table_name.split("_")
        singular_parts: list[str] = []

        for part in table_parts:
            singular: str | bool = self.inflect_engine.singular_noun(part)  # type: ignore[arg-type]
            # singular_noun returns False if word is already singular or not recognized
            singular_parts.append(str(singular) if singular else part)

        return "".join(word.title() for word in singular_parts)

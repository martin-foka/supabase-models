"""Tests for the model extractor component.

TODO: Missing tests for extract_models_info() method.
This method is currently too complex to test easily - requires extensive SQLAlchemy mocking.
"""

import pytest

from supabase_models.common.schemas import ColumnInfo
from supabase_models.common.schemas import ModelInfo
from supabase_models.components.model_extractor import ModelExtractor


class TestModelExtractor:
    """Test ModelExtractor class."""

    @pytest.mark.parametrize(
        "table_name,expected_class",
        [
            ("users", "User"),
            ("user_profiles", "UserProfile"),
            ("article_categories", "ArticleCategory"),
            ("posts", "Post"),
            ("order_items", "OrderItem"),
        ],
    )
    def test_get_class_name_from_table(self, table_name, expected_class):
        """Test table name to class name conversion."""
        extractor = ModelExtractor()
        assert extractor.get_class_name_from_table(table_name) == expected_class

    def test_collect_enum_info(self):
        """Test enum collection from models."""
        extractor = ModelExtractor()

        models = [
            ModelInfo(
                class_name="User",
                table_name="users",
                fields=[
                    ColumnInfo(
                        name="status",
                        type="StatusEnum",
                        sql_type="status_enum",
                        nullable=False,
                        enum_values=["active", "inactive"],
                    ),
                    ColumnInfo(name="name", type="str", sql_type="VARCHAR(100)", nullable=False),
                ],
                relationships=[],
            ),
            ModelInfo(
                class_name="Task",
                table_name="tasks",
                fields=[
                    ColumnInfo(
                        name="priority",
                        type="PriorityEnum",
                        sql_type="priority_enum",
                        nullable=False,
                        enum_values=["low", "high"],
                    )
                ],
                relationships=[],
            ),
        ]

        enums = extractor.collect_enum_info(models)

        assert len(enums) == 2
        assert enums["StatusEnum"] == ["active", "inactive"]
        assert enums["PriorityEnum"] == ["low", "high"]

    def test_collect_enum_info_empty(self):
        """Test enum collection when no enums exist."""
        extractor = ModelExtractor()

        models = [
            ModelInfo(
                class_name="User",
                table_name="users",
                fields=[ColumnInfo(name="id", type="int", sql_type="INTEGER", nullable=False)],
                relationships=[],
            )
        ]

        enums = extractor.collect_enum_info(models)
        assert len(enums) == 0

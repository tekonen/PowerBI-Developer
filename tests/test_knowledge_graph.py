"""Tests for the persistent knowledge graph store."""

from __future__ import annotations

from pathlib import Path

from pbi_developer.knowledge_graph import KnowledgeGraphStore


class TestKnowledgeGraphStore:
    def _make_store(self, tmp_path: Path) -> KnowledgeGraphStore:
        return KnowledgeGraphStore(path=tmp_path / "kg.json")

    def test_add_entity_and_retrieve(self, tmp_path: Path):
        kg = self._make_store(tmp_path)
        kg.add_entity("Sales", "table", schema="dbo")
        tables = kg.get_tables()
        assert len(tables) == 1
        assert tables[0]["name"] == "Sales"
        assert tables[0]["entity_type"] == "table"
        assert tables[0]["schema"] == "dbo"

    def test_add_relationship(self, tmp_path: Path):
        kg = self._make_store(tmp_path)
        kg.add_entity("Sales", "table")
        kg.add_entity("Date", "table")
        kg.add_relationship(
            "Sales",
            "Date",
            relationship_type="foreign_key",
            from_column="DateKey",
            to_column="DateKey",
            cardinality="ManyToOne",
        )
        rels = kg.get_relationships()
        assert len(rels) == 1
        assert rels[0]["from_entity"] == "Sales"
        assert rels[0]["to_entity"] == "Date"
        assert rels[0]["cardinality"] == "ManyToOne"

    def test_get_entity(self, tmp_path: Path):
        kg = self._make_store(tmp_path)
        kg.add_entity("Customers", "table", description="Main customer table")
        entity = kg.get_entity("Customers")
        assert entity is not None
        assert entity["name"] == "Customers"
        assert entity["description"] == "Main customer table"

    def test_get_entity_not_found(self, tmp_path: Path):
        kg = self._make_store(tmp_path)
        assert kg.get_entity("NonExistent") is None

    def test_persistence_round_trip(self, tmp_path: Path):
        kg1 = self._make_store(tmp_path)
        kg1.add_entity("Sales", "table")
        kg1.add_entity("Date", "table")
        kg1.add_relationship("Sales", "Date", relationship_type="foreign_key")
        kg1.save()

        # Load into a new instance
        kg2 = KnowledgeGraphStore(path=tmp_path / "kg.json")
        tables = kg2.get_tables()
        rels = kg2.get_relationships()
        assert len(tables) == 2
        assert len(rels) == 1
        assert rels[0]["from_entity"] == "Sales"

    def test_merge_from_svg_interpretation(self, tmp_path: Path):
        kg = self._make_store(tmp_path)
        interpretation = {
            "diagram_type": "physical_model",
            "entities": [
                {
                    "name": "Customers",
                    "entity_type": "table",
                    "columns": [
                        {"name": "CustomerID", "data_type": "INT"},
                        {"name": "Name", "data_type": "VARCHAR"},
                    ],
                },
                {
                    "name": "Orders",
                    "entity_type": "table",
                    "columns": [
                        {"name": "OrderID", "data_type": "INT"},
                        {"name": "CustomerID", "data_type": "INT"},
                    ],
                },
            ],
            "relationships": [
                {
                    "from_entity": "Orders",
                    "to_entity": "Customers",
                    "cardinality": "ManyToOne",
                    "from_column": "CustomerID",
                    "to_column": "CustomerID",
                },
            ],
        }
        kg.merge_from_svg_interpretation(interpretation)

        tables = kg.get_tables()
        assert len(tables) == 2
        table_names = {t["name"] for t in tables}
        assert table_names == {"Customers", "Orders"}

        rels = kg.get_relationships()
        assert len(rels) == 1
        assert rels[0]["from_entity"] == "Orders"

        # Columns should be added as separate nodes
        assert kg.get_entity("Customers.CustomerID") is not None
        assert kg.get_entity("Customers.Name") is not None

    def test_merge_is_additive(self, tmp_path: Path):
        kg = self._make_store(tmp_path)

        # First merge
        kg.merge_from_svg_interpretation(
            {
                "entities": [{"name": "Sales", "entity_type": "table"}],
                "relationships": [],
            }
        )
        assert len(kg.get_tables()) == 1

        # Second merge adds more
        kg.merge_from_svg_interpretation(
            {
                "entities": [{"name": "Products", "entity_type": "table"}],
                "relationships": [
                    {"from_entity": "Sales", "to_entity": "Products", "cardinality": "ManyToOne"},
                ],
            }
        )
        assert len(kg.get_tables()) == 2
        assert len(kg.get_relationships()) == 1

    def test_find_path(self, tmp_path: Path):
        kg = self._make_store(tmp_path)
        kg.add_entity("A", "table")
        kg.add_entity("B", "table")
        kg.add_entity("C", "table")
        kg.add_relationship("A", "B", relationship_type="fk")
        kg.add_relationship("B", "C", relationship_type="fk")

        path = kg.find_path("A", "C")
        assert path == ["A", "B", "C"]

    def test_find_path_no_path(self, tmp_path: Path):
        kg = self._make_store(tmp_path)
        kg.add_entity("A", "table")
        kg.add_entity("B", "table")
        # No edge between them
        assert kg.find_path("A", "B") == []

    def test_find_path_unknown_node(self, tmp_path: Path):
        kg = self._make_store(tmp_path)
        assert kg.find_path("X", "Y") == []

    def test_clear(self, tmp_path: Path):
        kg = self._make_store(tmp_path)
        kg.add_entity("Sales", "table")
        kg.clear()
        assert kg.get_tables() == []

    def test_to_metadata_markdown_format(self, tmp_path: Path):
        kg = self._make_store(tmp_path)
        kg.add_entity("Sales", "table")
        kg.add_entity("Sales.Revenue", "column", table="Sales", data_type="DECIMAL")
        kg.add_relationship("Sales", "Sales.Revenue", relationship_type="has_column")
        kg.add_entity("Date", "table")
        kg.add_relationship(
            "Sales",
            "Date",
            relationship_type="foreign_key",
            from_column="DateKey",
            to_column="DateKey",
            cardinality="ManyToOne",
        )

        md = kg.to_metadata_markdown()
        assert "## Table: Sales" in md
        assert "Revenue" in md
        assert "DECIMAL" in md
        assert "## Relationships" in md
        assert "Sales[DateKey]" in md
        assert "Date[DateKey]" in md
        assert "ManyToOne" in md

    def test_to_metadata_markdown_empty(self, tmp_path: Path):
        kg = self._make_store(tmp_path)
        assert kg.to_metadata_markdown() == ""

    def test_to_brief_context(self, tmp_path: Path):
        kg = self._make_store(tmp_path)
        kg.add_entity("Sales", "table")
        kg.add_entity("Date", "table")
        kg.add_relationship("Sales", "Date", relationship_type="fk", cardinality="ManyToOne")

        ctx = kg.to_brief_context()
        assert "2 tables" in ctx
        assert "1 relationships" in ctx
        assert "Sales" in ctx
        assert "Date" in ctx

    def test_to_brief_context_empty(self, tmp_path: Path):
        kg = self._make_store(tmp_path)
        assert kg.to_brief_context() == ""

    def test_relationships_exclude_structural(self, tmp_path: Path):
        """get_relationships() should exclude has_column and has_measure edges."""
        kg = self._make_store(tmp_path)
        kg.add_entity("Sales", "table")
        kg.add_entity("Sales.Amount", "column", table="Sales")
        kg.add_relationship("Sales", "Sales.Amount", relationship_type="has_column")
        kg.add_entity("Date", "table")
        kg.add_relationship("Sales", "Date", relationship_type="foreign_key")

        rels = kg.get_relationships()
        assert len(rels) == 1
        assert rels[0]["to_entity"] == "Date"

    def test_corrupt_json_handled(self, tmp_path: Path):
        """Should handle corrupt JSON gracefully."""
        path = tmp_path / "kg.json"
        path.write_text("{invalid json")
        kg = KnowledgeGraphStore(path=path)
        assert kg.graph.number_of_nodes() == 0

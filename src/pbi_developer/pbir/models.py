"""Pydantic models for PBIR structures.

These models represent the Power BI Enhanced Report Format (PBIR) which stores
each visual, page, and bookmark as individual JSON files. PBIR is the default
format since March 2026.

Folder structure:
    <ReportName>.Report/
        definition.pbir
        report.json
        definition/
            pages/
                <page-folder>/
                    page.json
                    visuals/
                        <visual-folder>/
                            visual.json
"""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field


def _generate_id() -> str:
    """Generate a 20-char hex ID matching PBIR naming convention."""
    return uuid.uuid4().hex[:20]


# --- Visual Models ---


class VisualPosition(BaseModel):
    """Position and size of a visual on the canvas."""

    x: int = 0
    y: int = 0
    width: int = 300
    height: int = 200
    z: int = 0
    tab_order: int = 0


class DataFieldBinding(BaseModel):
    """Binding a data field to a visual role (e.g., Category, Values)."""

    table: str
    column: str | None = None
    measure: str | None = None

    @property
    def expression(self) -> dict[str, Any]:
        if self.measure:
            return {
                "Measure": {
                    "Expression": {"SourceRef": {"Entity": self.table}},
                    "Property": self.measure,
                }
            }
        return {
            "Column": {
                "Expression": {"SourceRef": {"Entity": self.table}},
                "Property": self.column,
            }
        }


class VisualDataRole(BaseModel):
    """A visual data role with its field bindings."""

    role: str  # e.g., "Category", "Values", "Series"
    bindings: list[DataFieldBinding] = Field(default_factory=list)


class VisualFilter(BaseModel):
    """A filter applied to a visual."""

    table: str
    column: str
    filter_type: str = "basic"  # basic, advanced, relative_date, top_n
    operator: str = "In"
    values: list[Any] = Field(default_factory=list)
    is_hidden_in_view_mode: bool = False


class VisualFormatting(BaseModel):
    """Visual formatting properties."""

    title: str | None = None
    show_title: bool = True
    background_color: str | None = None
    border: bool = False
    font_family: str = "Segoe UI"
    font_size: int = 10
    font_color: str = "#333333"
    custom_properties: dict[str, Any] = Field(default_factory=dict)


class PBIRVisual(BaseModel):
    """A single Power BI visual definition.

    Each visual becomes a visual.json file in the PBIR folder structure.
    """

    id: str = Field(default_factory=_generate_id)
    visual_type: str  # e.g., "card", "clusteredBarChart", "lineChart", "tableEx", "slicer"
    position: VisualPosition = Field(default_factory=VisualPosition)
    data_roles: list[VisualDataRole] = Field(default_factory=list)
    filters: list[VisualFilter] = Field(default_factory=list)
    formatting: VisualFormatting = Field(default_factory=VisualFormatting)

    def to_pbir_json(self) -> dict[str, Any]:
        """Convert to PBIR visual.json format."""
        visual_json: dict[str, Any] = {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/1.0.0/schema.json",
            "name": self.id,
            "position": {
                "x": self.position.x,
                "y": self.position.y,
                "width": self.position.width,
                "height": self.position.height,
                "z": self.position.z,
                "tabOrder": self.position.tab_order,
            },
            "visual": {
                "visualType": self.visual_type,
                "query": self._build_query(),
                "objects": self._build_objects(),
            },
        }
        if self.filters:
            visual_json["filters"] = [self._build_filter(f) for f in self.filters]
        return visual_json

    def _build_query(self) -> dict[str, Any]:
        """Build the visual query with data role bindings."""
        query: dict[str, Any] = {"queryState": {}}
        for role in self.data_roles:
            projections = []
            for binding in role.bindings:
                query_ref = {
                    "queryRef": f"{binding.table}.{binding.measure or binding.column}",
                }
                projections.append(query_ref)
            query["queryState"][role.role] = {"projections": projections}
        return query

    def _build_objects(self) -> dict[str, Any]:
        """Build visual formatting objects."""
        objects: dict[str, Any] = {}
        fmt = self.formatting
        if fmt.title is not None or not fmt.show_title:
            objects["title"] = [
                {
                    "properties": {
                        "show": {"expr": {"Literal": {"Value": str(fmt.show_title).lower()}}},
                    }
                }
            ]
            if fmt.title:
                objects["title"][0]["properties"]["text"] = {"expr": {"Literal": {"Value": f"'{fmt.title}'"}}}
        if fmt.background_color:
            objects["background"] = [
                {
                    "properties": {
                        "color": {"solid": {"color": fmt.background_color}},
                    }
                }
            ]
        objects.update(fmt.custom_properties)
        return objects

    def _build_filter(self, f: VisualFilter) -> dict[str, Any]:
        return {
            "name": f"{f.table}_{f.column}_filter",
            "expression": {
                "Column": {
                    "Expression": {"SourceRef": {"Entity": f.table}},
                    "Property": f.column,
                }
            },
            "type": f.filter_type,
            "isHiddenInViewMode": f.is_hidden_in_view_mode,
        }


# --- Page Models ---


class PageBackground(BaseModel):
    """Page background settings."""

    color: str | None = None
    transparency: int = 0


class PBIRPage(BaseModel):
    """A report page containing visuals.

    Each page becomes a folder with page.json + visuals/ subfolder.
    """

    id: str = Field(default_factory=_generate_id)
    display_name: str = "Page 1"
    width: int = 1280
    height: int = 720
    background: PageBackground = Field(default_factory=PageBackground)
    visuals: list[PBIRVisual] = Field(default_factory=list)

    def to_pbir_json(self) -> dict[str, Any]:
        """Convert to PBIR page.json format."""
        page_json: dict[str, Any] = {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/1.0.0/schema.json",
            "name": self.id,
            "displayName": self.display_name,
            "displayOption": "FitToPage",
            "height": self.height,
            "width": self.width,
        }
        if self.background.color:
            page_json["background"] = {
                "color": self.background.color,
                "transparency": self.background.transparency,
            }
        return page_json


# --- Report Models ---


class SemanticModelReference(BaseModel):
    """Reference to the semantic model used by the report."""

    by_connection: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        if self.by_connection:
            return {"byConnection": self.by_connection}
        return {}


class PBIRDefinition(BaseModel):
    """The definition.pbir file linking the report to a semantic model."""

    version: str = "1.0"
    dataset_reference: SemanticModelReference = Field(default_factory=SemanticModelReference)

    def to_pbir_json(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "version": self.version,
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/definition/1.0.0/schema.json",
        }
        ds = self.dataset_reference.to_dict()
        if ds:
            result["datasetReference"] = ds
        return result


class ReportSettings(BaseModel):
    """Report-level settings stored in report.json."""

    theme_name: str = "default"
    filter_pane_visible: bool = True
    custom_settings: dict[str, Any] = Field(default_factory=dict)

    def to_pbir_json(self) -> dict[str, Any]:
        report: dict[str, Any] = {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/1.0.0/schema.json",
            "themeCollection": {
                "baseTheme": {
                    "name": self.theme_name,
                    "reportVersionAtImport": "5.53",
                    "type": "SharedResources",
                }
            },
            "filterPaneConfig": {
                "visible": self.filter_pane_visible,
            },
        }
        report.update(self.custom_settings)
        return report


class PBIRReport(BaseModel):
    """Top-level model for a complete PBIR report.

    Composes all pages, visuals, settings, and semantic model reference.
    """

    name: str = "Report"
    definition: PBIRDefinition = Field(default_factory=PBIRDefinition)
    settings: ReportSettings = Field(default_factory=ReportSettings)
    pages: list[PBIRPage] = Field(default_factory=list)

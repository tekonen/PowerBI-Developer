"""Tests for src/pbi_developer/inputs/pptx_parser.py.

Uses mocked python-pptx objects since real .pptx files are not available.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from pbi_developer.inputs.pptx_parser import (
    PptxParseResult,
    ShapeInfo,
    SlideInfo,
    _build_summary,
    parse_pptx,
    slides_to_text,
)

# ---------------------------------------------------------------------------
# Helpers to build mock pptx objects
# ---------------------------------------------------------------------------


def _make_shape(
    name: str = "Shape1",
    text: str = "hello",
    shape_type: int = 1,
    has_text_frame: bool = True,
    left: int = 914400,
    top: int = 914400,
    width: int = 1828800,
    height: int = 914400,
    fill_type: object | None = None,
    fill_color_rgb: str | None = None,
) -> MagicMock:
    shape = MagicMock()
    shape.name = name
    shape.text = text
    shape.shape_type = shape_type
    shape.has_text_frame = has_text_frame
    shape.left = left
    shape.top = top
    shape.width = width
    shape.height = height

    # Fill mock
    shape.fill.type = fill_type
    if fill_color_rgb is not None:
        shape.fill.fore_color.rgb = fill_color_rgb
    else:
        shape.fill.fore_color = None
    return shape


def _make_slide(
    shapes: list | None = None,
    title_text: str | None = None,
    notes_text: str | None = None,
) -> MagicMock:
    slide = MagicMock()
    shape_list = shapes or []
    slide.shapes.__iter__ = lambda self: iter(shape_list)

    if title_text is not None:
        slide.shapes.title.text = title_text
    else:
        slide.shapes.title = None

    if notes_text is not None:
        slide.has_notes_slide = True
        slide.notes_slide.notes_text_frame.text = notes_text
    else:
        slide.has_notes_slide = False

    return slide


# ---------------------------------------------------------------------------
# Dataclass tests
# ---------------------------------------------------------------------------


class TestDataclasses:
    def test_shape_info_defaults(self) -> None:
        s = ShapeInfo(shape_type="1", name="S", text="", left=0, top=0, width=0, height=0)
        assert s.fill_color is None

    def test_slide_info_defaults(self) -> None:
        s = SlideInfo(index=0)
        assert s.shapes == []
        assert s.title == ""
        assert s.notes == ""

    def test_pptx_parse_result_defaults(self) -> None:
        r = PptxParseResult()
        assert r.slides == []
        assert r.slide_images == []
        assert r.summary == ""


# ---------------------------------------------------------------------------
# parse_pptx (mocked Presentation)
# ---------------------------------------------------------------------------


class TestParsePptx:
    @patch("pbi_developer.inputs.pptx_parser.Presentation", create=True)
    def test_parses_single_slide(self, mock_pres_cls: MagicMock, tmp_path) -> None:
        # Patch the import inside parse_pptx
        shape = _make_shape(name="Title1", text="Sales Chart")
        slide = _make_slide(shapes=[shape], title_text="Revenue")

        mock_prs = MagicMock()
        mock_prs.slides = [slide]

        # Direct approach: mock the import inside the function
        mock_pptx = MagicMock()
        mock_pptx.Presentation.return_value = mock_prs
        with patch.dict("sys.modules", {"pptx": mock_pptx}):
            result = parse_pptx(tmp_path / "test.pptx")

        assert len(result.slides) == 1
        assert result.slides[0].title == "Revenue"
        assert len(result.slides[0].shapes) == 1
        assert result.slides[0].shapes[0].name == "Title1"
        assert "1 slide" in result.summary

    @patch("pbi_developer.inputs.pptx_parser.Presentation", create=True)
    def test_parses_multiple_slides(self, mock_pres_cls: MagicMock, tmp_path) -> None:
        slide1 = _make_slide(title_text="Page 1")
        slide2 = _make_slide(title_text="Page 2", notes_text="Some notes")
        mock_prs = MagicMock()
        mock_prs.slides = [slide1, slide2]

        mock_pptx = MagicMock()
        mock_pptx.Presentation.return_value = mock_prs
        with patch.dict("sys.modules", {"pptx": mock_pptx}):
            result = parse_pptx(tmp_path / "multi.pptx")

        assert len(result.slides) == 2
        assert result.slides[1].notes == "Some notes"
        assert "2 slide" in result.summary

    @patch("pbi_developer.inputs.pptx_parser.Presentation", create=True)
    def test_handles_no_title(self, mock_pres_cls: MagicMock, tmp_path) -> None:
        slide = _make_slide(title_text=None)
        mock_prs = MagicMock()
        mock_prs.slides = [slide]

        mock_pptx = MagicMock()
        mock_pptx.Presentation.return_value = mock_prs
        with patch.dict("sys.modules", {"pptx": mock_pptx}):
            result = parse_pptx(tmp_path / "notitle.pptx")

        assert result.slides[0].title == ""

    @patch("pbi_developer.inputs.pptx_parser.Presentation", create=True)
    def test_fill_color_extraction(self, mock_pres_cls: MagicMock, tmp_path) -> None:
        shape = _make_shape(
            name="Colored",
            fill_type="SOLID",
            fill_color_rgb="FF0000",
        )
        slide = _make_slide(shapes=[shape], title_text="Colors")
        mock_prs = MagicMock()
        mock_prs.slides = [slide]

        mock_pptx = MagicMock()
        mock_pptx.Presentation.return_value = mock_prs
        with patch.dict("sys.modules", {"pptx": mock_pptx}):
            result = parse_pptx(tmp_path / "colors.pptx")

        assert result.slides[0].shapes[0].fill_color == "#FF0000"

    @patch("pbi_developer.inputs.pptx_parser.Presentation", create=True)
    def test_fill_color_error_handled(self, mock_pres_cls: MagicMock, tmp_path) -> None:
        shape = _make_shape(name="BadFill")
        shape.fill.type = "SOLID"
        shape.fill.fore_color = MagicMock()
        shape.fill.fore_color.rgb = property(lambda s: (_ for _ in ()).throw(ValueError("bad")))
        # Make fore_color.rgb raise
        type(shape.fill.fore_color).rgb = property(lambda s: (_ for _ in ()).throw(ValueError("bad")))

        slide = _make_slide(shapes=[shape], title_text="Error")
        mock_prs = MagicMock()
        mock_prs.slides = [slide]

        mock_pptx = MagicMock()
        mock_pptx.Presentation.return_value = mock_prs
        with patch.dict("sys.modules", {"pptx": mock_pptx}):
            result = parse_pptx(tmp_path / "bad.pptx")

        # Should not crash; fill_color may be None
        assert len(result.slides) == 1


# ---------------------------------------------------------------------------
# slides_to_text
# ---------------------------------------------------------------------------


class TestSlidesToText:
    def test_basic_output(self) -> None:
        shape = ShapeInfo(
            shape_type="1",
            name="Card1",
            text="Revenue: $1M",
            left=9525 * 10,
            top=9525 * 20,
            width=9525 * 100,
            height=9525 * 50,
            fill_color="#AABBCC",
        )
        slide = SlideInfo(index=0, shapes=[shape], title="Dashboard", notes="Key metrics")
        result = PptxParseResult(slides=[slide])

        text = slides_to_text(result)
        assert "## Slide 1: Dashboard" in text
        assert "Notes: Key metrics" in text
        assert "Card1" in text
        assert "Revenue: $1M" in text
        assert "(color: #AABBCC)" in text

    def test_untitled_slide(self) -> None:
        slide = SlideInfo(index=0, shapes=[], title="")
        result = PptxParseResult(slides=[slide])
        text = slides_to_text(result)
        assert "(untitled)" in text

    def test_shape_without_text_excluded(self) -> None:
        shape = ShapeInfo(shape_type="1", name="Empty", text="", left=0, top=0, width=0, height=0)
        slide = SlideInfo(index=0, shapes=[shape], title="Test")
        result = PptxParseResult(slides=[slide])
        text = slides_to_text(result)
        assert "Empty" not in text

    def test_emu_to_pixel_conversion(self) -> None:
        # 9525 EMU = 1 pixel
        shape = ShapeInfo(
            shape_type="1",
            name="Pos",
            text="text",
            left=9525 * 50,
            top=9525 * 100,
            width=9525 * 200,
            height=9525 * 150,
        )
        slide = SlideInfo(index=0, shapes=[shape], title="T")
        result = PptxParseResult(slides=[slide])
        text = slides_to_text(result)
        assert "(50,100) 200x150px" in text


# ---------------------------------------------------------------------------
# _build_summary
# ---------------------------------------------------------------------------


class TestBuildSummary:
    def test_summary_content(self) -> None:
        s1 = SlideInfo(index=0, shapes=[ShapeInfo("1", "S1", "", 0, 0, 0, 0)], title="A")
        s2 = SlideInfo(index=1, shapes=[], title="B")
        result = PptxParseResult(slides=[s1, s2])
        summary = _build_summary(result)
        assert "2 slide(s)" in summary
        assert "1 total shapes" in summary
        assert "A" in summary
        assert "B" in summary

    def test_empty_result(self) -> None:
        result = PptxParseResult()
        summary = _build_summary(result)
        assert "0 slide(s)" in summary

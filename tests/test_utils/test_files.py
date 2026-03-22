"""Tests for src/pbi_developer/utils/files.py."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pbi_developer.utils.files import ensure_dir, read_json, write_json

# ---------------------------------------------------------------------------
# write_json
# ---------------------------------------------------------------------------


class TestWriteJson:
    """Tests for write_json."""

    def test_writes_valid_json(self, tmp_path: Path) -> None:
        target = tmp_path / "out.json"
        data = {"key": "value", "num": 42}
        write_json(target, data)

        assert target.exists()
        with open(target) as f:
            assert json.load(f) == data

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        target = tmp_path / "a" / "b" / "c" / "out.json"
        write_json(target, {"nested": True})

        assert target.exists()
        assert json.loads(target.read_text()) == {"nested": True}

    def test_default_indent_is_two(self, tmp_path: Path) -> None:
        target = tmp_path / "indented.json"
        write_json(target, {"a": 1})

        raw = target.read_text()
        # Two-space indent means the key line starts with two spaces
        assert "\n  " in raw

    def test_custom_indent(self, tmp_path: Path) -> None:
        target = tmp_path / "indented4.json"
        write_json(target, {"a": 1}, indent=4)

        raw = target.read_text()
        assert "\n    " in raw

    def test_handles_unicode(self, tmp_path: Path) -> None:
        target = tmp_path / "unicode.json"
        data = {"emoji": "\u00e9\u00e8\u00ea", "jp": "\u65e5\u672c\u8a9e"}
        write_json(target, data)

        # ensure_ascii=False so characters should be written literally
        raw = target.read_text(encoding="utf-8")
        assert "\u00e9" in raw
        assert "\u65e5\u672c\u8a9e" in raw

    def test_overwrites_existing_file(self, tmp_path: Path) -> None:
        target = tmp_path / "overwrite.json"
        write_json(target, {"v": 1})
        write_json(target, {"v": 2})

        assert read_json(target) == {"v": 2}

    def test_writes_list(self, tmp_path: Path) -> None:
        target = tmp_path / "list.json"
        write_json(target, [1, 2, 3])
        assert read_json(target) == [1, 2, 3]


# ---------------------------------------------------------------------------
# read_json
# ---------------------------------------------------------------------------


class TestReadJson:
    """Tests for read_json."""

    def test_reads_valid_json(self, tmp_path: Path) -> None:
        target = tmp_path / "data.json"
        expected = {"hello": "world"}
        target.write_text(json.dumps(expected))

        assert read_json(target) == expected

    def test_raises_on_missing_file(self, tmp_path: Path) -> None:
        missing = tmp_path / "does_not_exist.json"
        with pytest.raises(FileNotFoundError):
            read_json(missing)

    def test_raises_on_invalid_json(self, tmp_path: Path) -> None:
        target = tmp_path / "bad.json"
        target.write_text("not json {{{")

        with pytest.raises(json.JSONDecodeError):
            read_json(target)

    def test_reads_list(self, tmp_path: Path) -> None:
        target = tmp_path / "list.json"
        target.write_text("[1, 2, 3]")
        assert read_json(target) == [1, 2, 3]

    def test_reads_empty_object(self, tmp_path: Path) -> None:
        target = tmp_path / "empty.json"
        target.write_text("{}")
        assert read_json(target) == {}


# ---------------------------------------------------------------------------
# ensure_dir
# ---------------------------------------------------------------------------


class TestEnsureDir:
    """Tests for ensure_dir."""

    def test_creates_directory(self, tmp_path: Path) -> None:
        new_dir = tmp_path / "newdir"
        result = ensure_dir(new_dir)

        assert new_dir.is_dir()
        assert result == new_dir

    def test_creates_nested_directories(self, tmp_path: Path) -> None:
        nested = tmp_path / "a" / "b" / "c"
        result = ensure_dir(nested)

        assert nested.is_dir()
        assert result == nested

    def test_existing_directory_is_noop(self, tmp_path: Path) -> None:
        existing = tmp_path / "existing"
        existing.mkdir()
        result = ensure_dir(existing)

        assert existing.is_dir()
        assert result == existing

    def test_returns_path(self, tmp_path: Path) -> None:
        d = tmp_path / "ret"
        returned = ensure_dir(d)
        assert isinstance(returned, Path)
        assert returned == d


# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------


class TestRoundTrip:
    """Integration: write_json then read_json."""

    def test_round_trip(self, tmp_path: Path) -> None:
        data = {"list": [1, 2], "nested": {"a": True}}
        target = tmp_path / "rt.json"
        write_json(target, data)
        assert read_json(target) == data

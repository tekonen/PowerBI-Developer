"""Tests for src/pbi_developer/inputs/brief.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from pbi_developer.inputs.brief import load_brief, load_multiple_inputs, parse_user_questions

# ---------------------------------------------------------------------------
# load_brief
# ---------------------------------------------------------------------------


class TestLoadBrief:
    def test_loads_utf8_content(self, tmp_path: Path) -> None:
        f = tmp_path / "brief.md"
        f.write_text("# My Brief\nSome requirements here.", encoding="utf-8")
        assert load_brief(f) == "# My Brief\nSome requirements here."

    def test_loads_unicode_content(self, tmp_path: Path) -> None:
        f = tmp_path / "brief.md"
        f.write_text("Ünïcödé content — with em-dashes", encoding="utf-8")
        assert "Ünïcödé" in load_brief(f)

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_brief(tmp_path / "does_not_exist.md")

    def test_empty_file(self, tmp_path: Path) -> None:
        f = tmp_path / "empty.md"
        f.write_text("", encoding="utf-8")
        assert load_brief(f) == ""


# ---------------------------------------------------------------------------
# load_multiple_inputs
# ---------------------------------------------------------------------------


class TestLoadMultipleInputs:
    def test_concatenates_files(self, tmp_path: Path) -> None:
        a = tmp_path / "a.md"
        b = tmp_path / "b.md"
        a.write_text("alpha", encoding="utf-8")
        b.write_text("beta", encoding="utf-8")
        result = load_multiple_inputs([a, b])
        assert "--- a.md ---" in result
        assert "alpha" in result
        assert "--- b.md ---" in result
        assert "beta" in result

    def test_empty_list(self) -> None:
        assert load_multiple_inputs([]) == ""

    def test_single_file(self, tmp_path: Path) -> None:
        f = tmp_path / "only.md"
        f.write_text("single", encoding="utf-8")
        result = load_multiple_inputs([f])
        assert "--- only.md ---" in result
        assert "single" in result


# ---------------------------------------------------------------------------
# parse_user_questions
# ---------------------------------------------------------------------------


class TestParseUserQuestions:
    def test_extracts_questions(self) -> None:
        text = (
            "# Requirements\n"
            "- What is the total revenue by region?\n"
            "- How does churn vary over time?\n"
            "Some plain text.\n"
        )
        qs = parse_user_questions(text)
        assert len(qs) == 2
        assert "What is the total revenue by region?" in qs
        assert "How does churn vary over time?" in qs

    def test_strips_bullet_prefixes(self) -> None:
        text = "* What is the average order value?\n"
        qs = parse_user_questions(text)
        assert qs == ["What is the average order value?"]

    def test_strips_numbered_prefixes(self) -> None:
        text = "1. What is the margin trend?\n"
        qs = parse_user_questions(text)
        assert qs == ["What is the margin trend?"]

    def test_ignores_short_questions(self) -> None:
        text = "Why?\nWhat is the total cost?\n"
        qs = parse_user_questions(text)
        # "Why?" is only 4 chars, should be ignored (threshold > 5)
        assert len(qs) == 1
        assert "What is the total cost?" in qs

    def test_no_questions(self) -> None:
        text = "This is just a paragraph.\nNo questions here."
        assert parse_user_questions(text) == []

    def test_empty_input(self) -> None:
        assert parse_user_questions("") == []

    def test_bullet_prefix_variants(self) -> None:
        text = "• What is the growth rate?\n- What are top products?\n"
        qs = parse_user_questions(text)
        assert len(qs) == 2

"""Text brief / requirements parser.

Accepts markdown/text requirements, user questions, and interview transcripts.
Parses into a structured brief that downstream agents consume.
"""

from __future__ import annotations

from pathlib import Path


def load_brief(path: Path) -> str:
    """Load a text brief from file."""
    return path.read_text(encoding="utf-8")


def load_multiple_inputs(paths: list[Path]) -> str:
    """Concatenate multiple input files into a single brief."""
    parts: list[str] = []
    for p in paths:
        parts.append(f"--- {p.name} ---\n{p.read_text(encoding='utf-8')}\n")
    return "\n".join(parts)


def parse_user_questions(text: str) -> list[str]:
    """Extract user questions from text (lines ending with ?)."""
    questions = []
    for line in text.splitlines():
        line = line.strip()
        if line.endswith("?") and len(line) > 5:
            # Strip bullet points, numbering
            for prefix in ("-", "*", "•"):
                line = line.lstrip(prefix).strip()
            if line and line[0].isdigit():
                line = line.lstrip("0123456789.").strip()
            questions.append(line)
    return questions

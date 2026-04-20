"""Lightweight documentation checks."""

from pathlib import Path


def test_readme_credits_codex_as_contributor():
    readme = (
        Path(__file__).parent.parent / "README.md"
    ).read_text(encoding="utf-8")
    assert "Contributors" in readme
    assert "Codex" in readme

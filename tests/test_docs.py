"""Lightweight documentation checks."""

from pathlib import Path


def test_readme_credits_codex_as_contributor():
    readme = (
        Path(__file__).parent.parent / "README.md"
    ).read_text(encoding="utf-8")
    assert "Contributors" in readme
    assert "Codex" in readme


def test_live_llama_integration_tests_require_explicit_opt_in():
    live_test = (
        Path(__file__).parent / "integration" / "test_llama_cpp_live.py"
    ).read_text(encoding="utf-8")

    assert "BOURDON_RUN_LIVE_LLAMA" in live_test
    assert "explicitly enabled" in live_test

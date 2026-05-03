"""Tests for core.inference_protocol."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from core.inference_protocol import (
    BackendCapabilities,
    BackendUnsupported,
    InferenceBackend,
    Slot,
    register_backend,
)

# ---- Test helpers -----------------------------------------------------------


class _FakeBackend:
    """Minimal compliant backend. Methods are no-ops; tests only exercise
    the registration + capability surface, not actual generation."""

    def __init__(self, caps: BackendCapabilities) -> None:
        self._caps = caps

    def capabilities(self) -> BackendCapabilities:
        return self._caps

    async def slots(self) -> list[Slot]:
        return []

    async def stream_completion(
        self, prompt: str, *, slot_id: int | None = None
    ) -> AsyncIterator[str]:
        for token in []:  # noqa: B007 -- empty async generator on purpose
            yield token

    async def cancel(self, slot_id: int) -> None:
        return None


def _caps(
    *,
    streaming: bool = True,
    cancel: bool = False,
    concurrent_slots: int = 1,
    kv_cache_reuse: bool = False,
) -> BackendCapabilities:
    return BackendCapabilities(
        streaming=streaming,
        cancel=cancel,
        concurrent_slots=concurrent_slots,
        kv_cache_reuse=kv_cache_reuse,
    )


# ---- BackendUnsupported -----------------------------------------------------


def test_backend_unsupported_singular_message():
    err = BackendUnsupported(["cancel"])
    assert str(err) == "Backend missing required capability: cancel"
    assert err.missing == ("cancel",)


def test_backend_unsupported_plural_message():
    err = BackendUnsupported(["cancel", "kv_cache_reuse"])
    assert "capabilities" in str(err)
    assert "cancel" in str(err)
    assert "kv_cache_reuse" in str(err)
    assert err.missing == ("cancel", "kv_cache_reuse")


def test_backend_unsupported_dedupes_and_sorts():
    err = BackendUnsupported(["streaming", "cancel", "streaming"])
    assert err.missing == ("cancel", "streaming")


# ---- BackendCapabilities.supports -------------------------------------------


def test_supports_streaming_true():
    assert _caps(streaming=True).supports("streaming") is True


def test_supports_streaming_false():
    assert _caps(streaming=False).supports("streaming") is False


def test_supports_cancel_both_polarities():
    assert _caps(cancel=True).supports("cancel") is True
    assert _caps(cancel=False).supports("cancel") is False


def test_supports_concurrent_slots_requires_gt_one():
    assert _caps(concurrent_slots=4).supports("concurrent_slots") is True
    assert _caps(concurrent_slots=2).supports("concurrent_slots") is True


def test_supports_concurrent_slots_one_is_false():
    assert _caps(concurrent_slots=1).supports("concurrent_slots") is False


def test_supports_kv_cache_reuse_both_polarities():
    assert _caps(kv_cache_reuse=True).supports("kv_cache_reuse") is True
    assert _caps(kv_cache_reuse=False).supports("kv_cache_reuse") is False


def test_supports_unknown_capability_returns_false():
    """Forward-compat: querying a not-yet-defined capability never raises."""
    assert _caps().supports("transmogrify") is False
    assert _caps().supports("") is False


# ---- Slot -------------------------------------------------------------------


def test_slot_is_frozen():
    slot = Slot(id=0, busy=False)
    with pytest.raises(AttributeError):
        slot.busy = True  # type: ignore[misc]


def test_slot_default_prefix_hash_is_none():
    assert Slot(id=0, busy=False).prompt_prefix_hash is None


def test_slot_carries_prefix_hash():
    slot = Slot(id=2, busy=True, prompt_prefix_hash="abc123")
    assert slot.id == 2
    assert slot.busy is True
    assert slot.prompt_prefix_hash == "abc123"


# ---- register_backend -------------------------------------------------------


def test_register_backend_accepts_compliant_backend():
    backend = _FakeBackend(_caps(streaming=True))
    out = register_backend(backend)
    # Returns the same instance for fluent use.
    assert out is backend


def test_register_backend_default_requires_streaming():
    backend = _FakeBackend(_caps(streaming=False))
    with pytest.raises(BackendUnsupported) as exc:
        register_backend(backend)
    assert exc.value.missing == ("streaming",)


def test_register_backend_streaming_only_passes_when_other_caps_missing():
    """Default required set is just streaming -- absent cancel/kv_cache_reuse is fine."""
    backend = _FakeBackend(_caps(streaming=True, cancel=False, kv_cache_reuse=False))
    register_backend(backend)  # does not raise


def test_register_backend_raises_when_required_cap_missing():
    backend = _FakeBackend(_caps(streaming=True, cancel=False))
    with pytest.raises(BackendUnsupported) as exc:
        register_backend(backend, required_capabilities={"streaming", "cancel"})
    assert exc.value.missing == ("cancel",)


def test_register_backend_lists_all_missing_capabilities_sorted():
    backend = _FakeBackend(_caps(streaming=False, cancel=False, kv_cache_reuse=False))
    with pytest.raises(BackendUnsupported) as exc:
        register_backend(
            backend,
            required_capabilities={"streaming", "cancel", "kv_cache_reuse"},
        )
    assert exc.value.missing == ("cancel", "kv_cache_reuse", "streaming")


def test_register_backend_concurrent_slots_treated_as_capability():
    backend = _FakeBackend(_caps(streaming=True, concurrent_slots=1))
    with pytest.raises(BackendUnsupported) as exc:
        register_backend(
            backend,
            required_capabilities={"streaming", "concurrent_slots"},
        )
    assert exc.value.missing == ("concurrent_slots",)


def test_register_backend_concurrent_slots_passes_when_gt_one():
    backend = _FakeBackend(_caps(streaming=True, concurrent_slots=4))
    register_backend(
        backend, required_capabilities={"streaming", "concurrent_slots"}
    )  # does not raise


def test_register_backend_rejects_non_protocol_with_typeerror():
    class _NotABackend:
        pass

    with pytest.raises(TypeError) as exc:
        register_backend(_NotABackend())
    assert "InferenceBackend" in str(exc.value)
    assert "_NotABackend" in str(exc.value)


def test_register_backend_returned_object_is_runtime_checkable():
    backend = _FakeBackend(_caps(streaming=True))
    out = register_backend(backend)
    assert isinstance(out, InferenceBackend)


def test_register_backend_unknown_capability_in_required_set_fails_fast():
    """Unknown capability strings in required_capabilities are treated as
    unsupported (BackendCapabilities.supports returns False), so registration
    fails. Prevents typos from silently passing."""
    backend = _FakeBackend(_caps(streaming=True))
    with pytest.raises(BackendUnsupported) as exc:
        register_backend(backend, required_capabilities={"streaming", "transmogrify"})
    assert exc.value.missing == ("transmogrify",)


def test_register_backend_rejects_bare_string_required_capability():
    backend = _FakeBackend(_caps(streaming=True, cancel=True))
    with pytest.raises(TypeError) as exc:
        register_backend(backend, required_capabilities="cancel")
    assert "required_capabilities" in str(exc.value)

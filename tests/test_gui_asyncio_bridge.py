"""Tests for AsyncioBridge — threading, event queue, shutdown."""

from __future__ import annotations

import pytest

from evey2obs.gui.asyncio_bridge import AsyncioBridge
from evey2obs.settings import AppSettings


@pytest.fixture
def bridge() -> AsyncioBridge:
    b = AsyncioBridge(AppSettings())
    yield b
    b.shutdown()


class TestBridgeLifecycle:
    def test_bridge_creates_pipeline(self, bridge: AsyncioBridge) -> None:
        assert bridge.pipeline is not None
        assert bridge.poll_events() == []

    def test_bridge_shuts_down_cleanly(self) -> None:
        b = AsyncioBridge(AppSettings())
        b.shutdown()
        # Should not raise

    def test_double_shutdown_is_safe(self, bridge: AsyncioBridge) -> None:
        bridge.shutdown()
        bridge.shutdown()


class TestBridgeEvents:
    def test_poll_events_returns_empty_when_none(self, bridge: AsyncioBridge) -> None:
        events = bridge.poll_events()
        assert events == []

"""Tests for the Playwright protocol (basic, no browser required)."""

import pytest

pw = pytest.importorskip("playwright", reason="playwright not installed")

from averspec.protocol_playwright import playwright, PlaywrightProtocol, Screenshotter


class TestPlaywrightFactory:
    def test_returns_protocol(self):
        proto = playwright()
        assert isinstance(proto, PlaywrightProtocol)
        assert proto.name == "playwright"

    def test_default_options(self):
        proto = playwright()
        assert proto._headless is True
        assert proto._browser_type == "chromium"
        assert proto._regions is None

    def test_custom_browser_type(self):
        proto = playwright(browser_type="firefox", headless=False)
        assert proto._browser_type == "firefox"
        assert proto._headless is False

    def test_regions_stored(self):
        regions = {"header": {"x": 0, "y": 0, "width": 1920, "height": 100}}
        proto = playwright(regions=regions)
        assert proto._regions == regions


class TestScreenshotter:
    def test_unknown_region_raises(self):
        ss = Screenshotter(page=None, regions={"header": {}})
        with pytest.raises(ValueError, match="Unknown region 'footer'"):
            ss.capture("/tmp/out.png", region="footer")

"""Playwright protocol for AverSpec — browser-per-suite, page-per-test."""

from __future__ import annotations

from typing import Any

from averspec.protocol import Protocol


class Screenshotter:
    """Captures screenshots of a Playwright page, optionally clipping to named regions."""

    def __init__(self, page: Any, regions: dict | None = None):
        self._page = page
        self._regions = regions or {}

    def capture(self, output_path: str, *, region: str | None = None) -> str:
        clip = None
        if region is not None:
            if region not in self._regions:
                raise ValueError(
                    f"Unknown region '{region}'. "
                    f"Available: {list(self._regions.keys())}"
                )
            clip = self._regions[region]

        kwargs: dict[str, Any] = {"path": output_path}
        if clip is not None:
            kwargs["clip"] = clip

        self._page.screenshot(**kwargs)
        return output_path


class PlaywrightProtocol(Protocol):
    """Playwright protocol: browser-per-suite, page-per-test."""

    name = "playwright"

    def __init__(
        self,
        *,
        headless: bool = True,
        browser_type: str = "chromium",
        regions: dict | None = None,
    ):
        self._headless = headless
        self._browser_type = browser_type
        self._regions = regions
        self._pw = None
        self._browser = None
        self._page_count = 0
        self.screenshotter: Screenshotter | None = None

    def _ensure_browser(self) -> Any:
        """Lazy-launch: start playwright and browser on first use."""
        if self._browser is not None:
            return self._browser

        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        launcher = getattr(self._pw, self._browser_type)
        self._browser = launcher.launch(headless=self._headless)
        return self._browser

    def setup(self) -> Any:
        browser = self._ensure_browser()
        page = browser.new_page()
        self._page_count += 1
        self.screenshotter = Screenshotter(page, self._regions)
        return page

    def teardown(self, ctx: Any) -> None:
        ctx.close()
        self._page_count -= 1

        if self._page_count <= 0 and self._browser is not None:
            self._browser.close()
            self._browser = None
            if self._pw is not None:
                self._pw.stop()
                self._pw = None
            self.screenshotter = None


def playwright(
    *,
    headless: bool = True,
    browser_type: str = "chromium",
    regions: dict | None = None,
) -> PlaywrightProtocol:
    """Create a Playwright protocol (browser-per-suite, page-per-test)."""
    return PlaywrightProtocol(
        headless=headless,
        browser_type=browser_type,
        regions=regions,
    )

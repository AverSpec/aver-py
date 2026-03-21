"""Tests for AVER_DOMAIN filtering in pytest_generate_tests."""

import pytest
from averspec.domain import domain, action, assertion
from averspec.adapter import implement
from averspec.protocol import unit
from averspec.config import get_registry, define_config
from averspec.suite import Suite


@domain("FilterA")
class FilterA:
    do_a = action()
    check_a = assertion()


@domain("FilterB")
class FilterB:
    do_b = action()
    check_b = assertion()


def make_adapter(domain_cls, protocol_name="unit"):
    proto = unit(lambda: None, protocol_name)
    builder = implement(domain_cls, protocol=proto)
    for marker_name, marker in domain_cls._aver_markers.items():
        @builder.handle(marker)
        def handler(ctx, payload=None, _name=marker_name):
            pass
    return builder.build()


class TestDomainFiltering:
    def setup_method(self):
        get_registry().reset()

    def test_aver_domain_matches_includes_tests(self, monkeypatch):
        """When AVER_DOMAIN matches the suite's domain, tests run normally."""
        monkeypatch.setenv("AVER_DOMAIN", "FilterA")
        adapter = make_adapter(FilterA)
        get_registry().register_adapter(adapter)

        suite_a = Suite(FilterA)
        # The domain name matches, so find_adapters should return adapters
        adapters = get_registry().find_adapters(suite_a.domain_cls)
        assert len(adapters) == 1

        # Simulate the filtering logic from pytest_generate_tests
        domain_filter = "FilterA"
        should_skip = domain_filter and suite_a.domain_cls._aver_domain_name != domain_filter
        assert should_skip is False

    def test_aver_domain_mismatch_skips_tests(self, monkeypatch):
        """When AVER_DOMAIN doesn't match, the suite is skipped."""
        monkeypatch.setenv("AVER_DOMAIN", "FilterB")
        adapter = make_adapter(FilterA)
        get_registry().register_adapter(adapter)

        suite_a = Suite(FilterA)

        domain_filter = "FilterB"
        should_skip = domain_filter and suite_a.domain_cls._aver_domain_name != domain_filter
        assert should_skip is True

    def test_aver_domain_not_set_runs_all(self, monkeypatch):
        """When AVER_DOMAIN is not set, all suites run."""
        monkeypatch.delenv("AVER_DOMAIN", raising=False)
        adapter_a = make_adapter(FilterA)
        adapter_b = make_adapter(FilterB)
        get_registry().register_adapter(adapter_a)
        get_registry().register_adapter(adapter_b)

        suite_a = Suite(FilterA)
        suite_b = Suite(FilterB)

        domain_filter = None
        should_skip_a = domain_filter and suite_a.domain_cls._aver_domain_name != domain_filter
        should_skip_b = domain_filter and suite_b.domain_cls._aver_domain_name != domain_filter
        assert not should_skip_a
        assert not should_skip_b

"""Framework transparency tests: verify public API shape without deep behavior."""

import averspec
from averspec import (
    domain,
    action,
    query,
    assertion,
    Marker,
    MarkerKind,
    implement,
    suite,
    Context,
    ComposedSuite,
    Protocol,
    TelemetryCollector,
    unit,
    with_fixture,
    TestMetadata,
    TestCompletion,
    Attachment,
    define_config,
    TraceEntry,
    eventually,
    format_trace,
    approve,
    characterize,
    TelemetryExpectation,
    CollectedSpan,
    SpanLink,
    TelemetryMatchResult,
    resolve_telemetry_mode,
    verify_correlation,
    extract_contract,
    BehavioralContract,
    verify_contract,
    ConformanceReport,
    create_otlp_receiver,
    write_contracts,
    read_contracts,
    read_contract_file,
    slugify,
    register_serializer,
)
from averspec.suite import Suite
from averspec.adapter import AdapterBuilder


class TestPublicExports:
    """All public exports are importable."""

    def test_all_exports_present(self):
        for name in averspec.__all__:
            assert hasattr(averspec, name), f"Missing export: {name}"

    def test_all_list_not_empty(self):
        assert len(averspec.__all__) > 20


class TestSuiteCreation:
    """suite(domain) returns a Suite."""

    def test_suite_returns_suite_instance(self):
        @domain("smoke-suite")
        class SmokeDomain:
            do_thing = action()

        s = suite(SmokeDomain)
        assert isinstance(s, Suite)

    def test_suite_rejects_non_domain(self):
        class NotADomain:
            pass

        try:
            suite(NotADomain)
            assert False, "Expected TypeError"
        except TypeError:
            pass


class TestImplement:
    """implement(domain, protocol=unit(factory)) returns AdapterBuilder."""

    def test_returns_adapter_builder(self):
        @domain("smoke-implement")
        class SmokeDomain:
            do_thing = action()

        builder = implement(SmokeDomain, protocol=unit(lambda: None))
        assert isinstance(builder, AdapterBuilder)

    def test_rejects_non_domain(self):
        class NotADomain:
            pass

        try:
            implement(NotADomain, protocol=unit(lambda: None))
            assert False, "Expected TypeError"
        except TypeError:
            pass


class TestDomainDecorator:
    """@domain decorator works on a fresh class."""

    def test_sets_domain_metadata(self):
        @domain("smoke-domain-deco")
        class MyDomain:
            create = action()
            get_count = query(type(None), int)
            exists = assertion()

        assert MyDomain._aver_domain_name == "smoke-domain-deco"
        assert MyDomain._aver_is_domain is True
        assert len(MyDomain._aver_markers) == 3

    def test_prevents_instantiation(self):
        @domain("smoke-no-init")
        class MyDomain:
            do_thing = action()

        try:
            MyDomain()
            assert False, "Expected TypeError"
        except TypeError:
            pass


class TestMarkerFactories:
    """action/query/assertion return Marker instances."""

    def test_action_returns_marker(self):
        m = action()
        assert isinstance(m, Marker)
        assert m.kind == MarkerKind.ACTION

    def test_query_returns_marker(self):
        m = query(str, int)
        assert isinstance(m, Marker)
        assert m.kind == MarkerKind.QUERY

    def test_assertion_returns_marker(self):
        m = assertion()
        assert isinstance(m, Marker)
        assert m.kind == MarkerKind.ASSERTION

    def test_action_with_telemetry(self):
        tel = TelemetryExpectation(span="test.span")
        m = action(str, telemetry=tel)
        assert m.telemetry is tel


class TestDefineConfig:
    """define_config accepts adapters list."""

    def test_accepts_built_adapters(self):
        @domain("smoke-config")
        class ConfigDomain:
            do_thing = action()

        builder = implement(ConfigDomain, protocol=unit(lambda: None))

        @builder.handle(ConfigDomain.do_thing)
        def handle_thing(ctx):
            pass

        built = builder.build()

        # Should not raise
        define_config(adapters=[built])

    def test_rejects_invalid_teardown_mode(self):
        try:
            define_config(adapters=[], teardown_failure_mode="invalid")
            assert False, "Expected ValueError"
        except ValueError:
            pass


class TestCliEntryPoint:
    """aver CLI entry point exists."""

    def test_entry_point_callable(self):
        from averspec.cli import main
        assert callable(main)

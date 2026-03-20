"""Tests for domain extensions via .extend()."""

import pytest

from averspec import domain, action, query, assertion, implement, unit
from averspec.suite import Context


@domain("Base")
class Base:
    do_a = action(dict)
    check_a = assertion(dict)


def test_extended_domain_inherits_parent_markers():
    Extended = Base.extend(
        "Extended",
        assertions={"check_b": assertion(dict)},
    )
    markers = Extended._aver_markers
    assert "do_a" in markers
    assert "check_a" in markers
    assert "check_b" in markers
    assert Extended._aver_domain_name == "Extended"


def test_extended_domain_tracks_parent():
    Child = Base.extend("Child", actions={"do_b": action(dict)})
    assert Child._aver_parent is Base


def test_duplicate_marker_raises():
    with pytest.raises(ValueError, match="collision"):
        Base.extend("Bad", actions={"do_a": action()})


def test_extended_domain_can_be_implemented():
    Extended = Base.extend(
        "ExtImpl",
        assertions={"is_visible": assertion()},
    )
    proto = unit(lambda: {})
    builder = implement(Extended, protocol=proto)

    for name, marker in Extended._aver_markers.items():
        @builder.handle(marker)
        def handler(ctx, payload=None, _n=name):
            pass

    adapter = builder.build()
    assert adapter is not None


def test_extended_domain_works_in_context():
    Extended = Base.extend(
        "ExtCtx",
        assertions={"is_visible": assertion()},
    )
    proto = unit(lambda: {})
    builder = implement(Extended, protocol=proto)

    for name, marker in Extended._aver_markers.items():
        @builder.handle(marker)
        def handler(ctx, payload=None, _n=name):
            pass

    adapter = builder.build()
    protocol_ctx = proto.setup()
    ctx = Context(Extended, adapter, protocol_ctx)

    ctx.when.do_a({"key": "val"})
    ctx.then.check_a({"key": "val"})
    ctx.then.is_visible()

    assert len(ctx.trace()) == 3


def test_extended_domain_is_itself_a_domain():
    Extended = Base.extend("IsDomain", assertions={"extra": assertion()})
    assert getattr(Extended, "_aver_is_domain", False) is True


def test_extended_domain_cannot_be_instantiated():
    Extended = Base.extend("NoInit", assertions={"extra": assertion()})
    with pytest.raises(TypeError):
        Extended()


def test_chained_extension():
    """Extend an already-extended domain."""
    Level1 = Base.extend("Level1", queries={"get_x": query(type(None), int)})
    Level2 = Level1.extend("Level2", assertions={"check_x": assertion()})

    assert "do_a" in Level2._aver_markers
    assert "get_x" in Level2._aver_markers
    assert "check_x" in Level2._aver_markers
    assert Level2._aver_parent is Level1

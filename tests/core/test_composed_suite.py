"""Tests for multi-domain composed suites."""

import pytest

from averspec import domain, action, query, assertion, implement, unit
from averspec.suite import ComposedSuite


# --- Test domains ---

@domain("Admin")
class Admin:
    create_project = action(dict)
    project_count = query(type(None), int)
    project_exists = assertion(dict)


@domain("User")
class UserDomain:
    add_task = action(dict)
    task_count = query(type(None), int)
    access_denied = assertion(dict)


def _build_admin_adapter(log: list):
    proto = unit(lambda: {"log": log})
    builder = implement(Admin, protocol=proto)

    @builder.handle(Admin.create_project)
    def create_project(ctx, payload):
        ctx["log"].append(f"create:{payload['name']}")

    @builder.handle(Admin.project_count)
    def project_count(ctx):
        return 3

    @builder.handle(Admin.project_exists)
    def project_exists(ctx, payload):
        pass

    return builder.build()


def _build_user_adapter(log: list):
    proto = unit(lambda: {"log": log})
    builder = implement(UserDomain, protocol=proto)

    @builder.handle(UserDomain.add_task)
    def add_task(ctx, payload):
        ctx["log"].append(f"task:{payload['project']}:{payload['title']}")

    @builder.handle(UserDomain.task_count)
    def task_count(ctx):
        return 5

    @builder.handle(UserDomain.access_denied)
    def access_denied(ctx, payload):
        pass

    return builder.build()


def test_each_namespace_dispatches_to_own_adapter():
    admin_log: list[str] = []
    user_log: list[str] = []
    admin_adapter = _build_admin_adapter(admin_log)
    user_adapter = _build_user_adapter(user_log)

    cs = ComposedSuite({
        "admin": (Admin, admin_adapter),
        "user": (UserDomain, user_adapter),
    })

    def body(ctx):
        ctx.admin.when.create_project({"name": "Restricted"})
        ctx.user.when.add_task({"project": "Restricted", "title": "Task"})

    cs.run_test(body)

    assert "create:Restricted" in admin_log
    assert "task:Restricted:Task" in user_log


def test_all_domains_share_single_trace():
    admin_adapter = _build_admin_adapter([])
    user_adapter = _build_user_adapter([])

    cs = ComposedSuite({
        "admin": (Admin, admin_adapter),
        "user": (UserDomain, user_adapter),
    })

    traces = []

    def body(ctx):
        ctx.admin.when.create_project({"name": "P1"})
        ctx.user.when.add_task({"project": "P1", "title": "T1"})
        traces.extend(ctx.trace())

    cs.run_test(body)

    assert len(traces) == 2
    assert "Admin.create_project" in traces[0].name
    assert "User.add_task" in traces[1].name


def test_given_when_then_aliases_per_namespace():
    admin_adapter = _build_admin_adapter([])
    user_adapter = _build_user_adapter([])

    cs = ComposedSuite({
        "admin": (Admin, admin_adapter),
        "user": (UserDomain, user_adapter),
    })

    traces = []

    def body(ctx):
        ctx.admin.given.create_project({"name": "Setup"})
        ctx.user.when.add_task({"project": "Setup", "title": "Trigger"})
        ctx.user.then.access_denied({"project": "Setup"})
        traces.extend(ctx.trace())

    cs.run_test(body)

    assert traces[0].category == "given"
    assert "Admin" in traces[0].name
    assert traces[1].category == "when"
    assert "User" in traces[1].name
    assert traces[2].category == "then"
    assert "User" in traces[2].name


def test_query_return_values_per_namespace():
    admin_adapter = _build_admin_adapter([])
    user_adapter = _build_user_adapter([])

    cs = ComposedSuite({
        "admin": (Admin, admin_adapter),
        "user": (UserDomain, user_adapter),
    })

    results = {}

    def body(ctx):
        results["projects"] = ctx.admin.query.project_count()
        results["tasks"] = ctx.user.query.task_count()

    cs.run_test(body)

    assert results["projects"] == 3
    assert results["tasks"] == 5


def test_teardown_runs_even_on_failure():
    teardown_log: list[str] = []

    class TrackingProto:
        name = "tracking"

        def __init__(self, label):
            self._label = label

        def setup(self):
            return {}

        def teardown(self, ctx):
            teardown_log.append(f"teardown:{self._label}")

    @domain("D1")
    class D1:
        boom = action()

    @domain("D2")
    class D2:
        pass

    proto1 = TrackingProto("p1")
    proto2 = TrackingProto("p2")

    b1 = implement(D1, protocol=proto1)

    @b1.handle(D1.boom)
    def boom(ctx):
        raise RuntimeError("kaboom")

    a1 = b1.build()

    b2 = implement(D2, protocol=proto2)
    a2 = b2.build()

    cs = ComposedSuite({
        "d1": (D1, a1),
        "d2": (D2, a2),
    })

    with pytest.raises(RuntimeError, match="kaboom"):
        cs.run_test(lambda ctx: ctx.d1.when.boom())

    assert "teardown:p1" in teardown_log
    assert "teardown:p2" in teardown_log


def test_teardown_in_reverse_order():
    order: list[str] = []

    class OrderProto:
        def __init__(self, label):
            self.name = label
            self._label = label

        def setup(self):
            return {}

        def teardown(self, ctx):
            order.append(f"teardown:{self._label}")

    @domain("A")
    class A:
        pass

    @domain("B")
    class B:
        pass

    @domain("C")
    class C:
        pass

    a_adapter = implement(A, protocol=OrderProto("p1")).build()
    b_adapter = implement(B, protocol=OrderProto("p2")).build()
    c_adapter = implement(C, protocol=OrderProto("p3")).build()

    cs = ComposedSuite({
        "a": (A, a_adapter),
        "b": (B, b_adapter),
        "c": (C, c_adapter),
    })

    cs.run_test(lambda ctx: None)

    assert order == ["teardown:p3", "teardown:p2", "teardown:p1"]

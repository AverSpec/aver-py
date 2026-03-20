"""Domain declaration via @domain decorator and typed markers."""

from __future__ import annotations

from enum import Enum
from typing import Generic, TypeVar, Any

P = TypeVar("P")
R = TypeVar("R")


class MarkerKind(Enum):
    ACTION = "action"
    QUERY = "query"
    ASSERTION = "assertion"


class Marker(Generic[P]):
    """A domain operation marker. Created by action(), query(), assertion()."""

    def __init__(
        self,
        kind: MarkerKind,
        payload_type: type,
        return_type: type = type(None),
        *,
        telemetry=None,
    ):
        self.kind = kind
        self.payload_type = payload_type
        self.return_type = return_type
        self.telemetry = telemetry
        # Set by @domain:
        self.name: str | None = None
        self.domain_name: str | None = None

    def __repr__(self):
        return f"<{self.kind.value} '{self.name}'>"


def action(payload_type: type = type(None), *, telemetry=None) -> Any:
    """Declare an action marker."""
    return Marker(MarkerKind.ACTION, payload_type, telemetry=telemetry)


def query(payload_type: type, return_type: type, *, telemetry=None) -> Any:
    """Declare a query marker."""
    return Marker(MarkerKind.QUERY, payload_type, return_type, telemetry=telemetry)


def assertion(payload_type: type = type(None), *, telemetry=None) -> Any:
    """Declare an assertion marker."""
    return Marker(MarkerKind.ASSERTION, payload_type, telemetry=telemetry)


def domain(name: str):
    """Class decorator that turns a class with marker attributes into a domain."""

    def decorator(cls):
        # Guard against domain subclassing
        if getattr(cls, "_aver_is_domain", False):
            raise TypeError(
                f"Cannot decorate {cls.__name__} with @domain — "
                f"it already is a domain. Domain subclassing is not supported."
            )

        markers: dict[str, Marker] = {}

        for attr_name in list(vars(cls)):
            value = vars(cls)[attr_name]
            if isinstance(value, Marker):
                value.name = attr_name
                value.domain_name = name
                markers[attr_name] = value

        cls._aver_domain_name = name
        cls._aver_markers = markers
        cls._aver_is_domain = True

        # Prevent instantiation — domain classes are structural, not behavioral
        original_init = cls.__init__ if hasattr(cls, "__init__") else None

        def _no_init(self, *args, **kwargs):
            raise TypeError(
                f"{cls.__name__} is a domain declaration and should not be instantiated. "
                f"Use it as a reference: {cls.__name__}.{next(iter(markers), 'marker_name')}"
            )

        cls.__init__ = _no_init

        # Add extend() class method
        @classmethod
        def _extend(
            klass,
            ext_name: str,
            *,
            actions: dict[str, Any] | None = None,
            queries: dict[str, Any] | None = None,
            assertions: dict[str, Any] | None = None,
        ):
            """Create a new domain that inherits this domain's markers plus new ones."""
            new_markers = {}
            for source, kind in [
                (actions or {}, MarkerKind.ACTION),
                (queries or {}, MarkerKind.QUERY),
                (assertions or {}, MarkerKind.ASSERTION),
            ]:
                for mk_name, mk in source.items():
                    if not isinstance(mk, Marker):
                        raise TypeError(
                            f"Extension value for '{mk_name}' must be a Marker, "
                            f"got {type(mk).__name__}"
                        )
                    if mk_name in markers:
                        raise ValueError(
                            f"Domain extension collision: '{mk_name}' already exists "
                            f"in parent domain '{name}'"
                        )
                    new_markers[mk_name] = mk

            # Build a new class dynamically
            child_cls = type(ext_name, (), {})

            # Copy parent markers
            all_markers: dict[str, Marker] = {}
            for mk_name, mk in markers.items():
                setattr(child_cls, mk_name, mk)
                all_markers[mk_name] = mk

            # Add new markers, setting their name and domain_name
            for mk_name, mk in new_markers.items():
                mk.name = mk_name
                mk.domain_name = ext_name
                setattr(child_cls, mk_name, mk)
                all_markers[mk_name] = mk

            child_cls._aver_domain_name = ext_name
            child_cls._aver_markers = all_markers
            child_cls._aver_is_domain = True
            child_cls._aver_parent = klass

            def _child_no_init(self, *args, **kwargs):
                raise TypeError(
                    f"{ext_name} is a domain declaration and should not be instantiated."
                )

            child_cls.__init__ = _child_no_init

            # Give child the extend ability too (recursive)
            child_cls.extend = classmethod(
                lambda child_klass, cn, *, actions=None, queries=None, assertions=None: _make_extend(
                    child_cls, ext_name, all_markers
                )(cn, actions=actions, queries=queries, assertions=assertions)
            )

            return child_cls

        cls.extend = _extend

        return cls

    return decorator


def _make_extend(parent_cls, parent_name, parent_markers):
    """Build an extend function for a dynamically-created child domain."""

    def _extend_child(
        ext_name: str,
        *,
        actions: dict[str, Any] | None = None,
        queries: dict[str, Any] | None = None,
        assertions: dict[str, Any] | None = None,
    ):
        new_markers = {}
        for source, kind in [
            (actions or {}, MarkerKind.ACTION),
            (queries or {}, MarkerKind.QUERY),
            (assertions or {}, MarkerKind.ASSERTION),
        ]:
            for mk_name, mk in source.items():
                if not isinstance(mk, Marker):
                    raise TypeError(
                        f"Extension value for '{mk_name}' must be a Marker, "
                        f"got {type(mk).__name__}"
                    )
                if mk_name in parent_markers:
                    raise ValueError(
                        f"Domain extension collision: '{mk_name}' already exists "
                        f"in parent domain '{parent_name}'"
                    )
                new_markers[mk_name] = mk

        child_cls = type(ext_name, (), {})
        all_markers: dict[str, Marker] = {}

        for mk_name, mk in parent_markers.items():
            setattr(child_cls, mk_name, mk)
            all_markers[mk_name] = mk

        for mk_name, mk in new_markers.items():
            mk.name = mk_name
            mk.domain_name = ext_name
            setattr(child_cls, mk_name, mk)
            all_markers[mk_name] = mk

        child_cls._aver_domain_name = ext_name
        child_cls._aver_markers = all_markers
        child_cls._aver_is_domain = True
        child_cls._aver_parent = parent_cls

        def _child_no_init(self, *args, **kwargs):
            raise TypeError(
                f"{ext_name} is a domain declaration and should not be instantiated."
            )

        child_cls.__init__ = _child_no_init
        child_cls.extend = classmethod(
            lambda klass, cn, *, actions=None, queries=None, assertions=None: _make_extend(
                child_cls, ext_name, all_markers
            )(cn, actions=actions, queries=queries, assertions=assertions)
        )

        return child_cls

    return _extend_child

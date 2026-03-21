"""Cross-step telemetry correlation verification."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from averspec.trace import TraceEntry


@dataclass
class CorrelationGroup:
    """A group of steps that share a (key, value) attribute pair."""

    key: str
    value: str
    steps: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class CorrelationViolation:
    """A single correlation violation."""

    kind: str  # "attribute-mismatch" or "causal-break"
    key: str
    value: str = ""
    steps: list[str] = field(default_factory=list)
    message: str = ""


@dataclass
class CorrelationResult:
    """Result of cross-step correlation verification."""

    groups: list[CorrelationGroup] = field(default_factory=list)
    violations: list[CorrelationViolation] = field(default_factory=list)


def verify_correlation(trace: list[TraceEntry]) -> CorrelationResult:
    """Verify cross-step telemetry correlation after all steps complete.

    Groups steps by shared (attribute key, expected value) pairs.
    Two verification levels:
    1. Attribute correlation: each matched span carries the expected attribute value
    2. Causal correlation (opt-in via causes): spans are in the same trace or linked
    """
    # Collect steps with telemetry that have expected attributes and matched
    steps_with_telemetry = []
    for i, entry in enumerate(trace):
        if entry.telemetry is None:
            continue
        if not entry.telemetry.expected.attributes:
            continue
        if not entry.telemetry.matched:
            continue
        steps_with_telemetry.append({
            "name": entry.name,
            "index": i,
            "expected": entry.telemetry.expected.attributes,
            "causes": entry.telemetry.expected.causes,
            "matched_span": entry.telemetry.matched_span,
        })

    # Group by shared (attribute key, expected value)
    key_value_map: dict[str, list[dict]] = {}
    for step in steps_with_telemetry:
        for key, value in step["expected"].items():
            composite_key = f"{key}={value}"
            if composite_key not in key_value_map:
                key_value_map[composite_key] = []
            key_value_map[composite_key].append(step)

    groups: list[CorrelationGroup] = []
    violations: list[CorrelationViolation] = []

    for composite_key, steps in key_value_map.items():
        # Only check groups with 2+ steps
        if len(steps) < 2:
            continue

        eq_idx = composite_key.index("=")
        key = composite_key[:eq_idx]
        value = composite_key[eq_idx + 1:]

        groups.append(CorrelationGroup(
            key=key,
            value=value,
            steps=[{"name": s["name"], "index": s["index"]} for s in steps],
        ))

        step_names = [s["name"] for s in steps]

        # Attribute correlation: verify each matched span carries the attribute
        for step in steps:
            matched_span = step["matched_span"]
            if matched_span is None:
                violations.append(CorrelationViolation(
                    kind="attribute-mismatch",
                    key=key,
                    value=value,
                    steps=step_names,
                    message=(
                        f"Expected attribute '{key}' on span for step "
                        f"'{step['name']}' but span was not matched"
                    ),
                ))
                continue

            actual = matched_span.attributes.get(key)
            if actual is None:
                violations.append(CorrelationViolation(
                    kind="attribute-mismatch",
                    key=key,
                    value=value,
                    steps=step_names,
                    message=(
                        f"Expected attribute '{key}' on span '{matched_span.name}' "
                        f"for step '{step['name']}' but not found"
                    ),
                ))
            elif str(actual) != value:
                violations.append(CorrelationViolation(
                    kind="attribute-mismatch",
                    key=key,
                    value=value,
                    steps=step_names,
                    message=(
                        f"Expected attribute '{key}' = '{value}' on span "
                        f"'{matched_span.name}' for step '{step['name']}' "
                        f"but got '{actual}'"
                    ),
                ))

        # Causal correlation: only when a step declares causes
        for step in steps:
            causes = step.get("causes") or []
            if not causes:
                continue
            matched_span = step["matched_span"]
            if matched_span is None or not matched_span.trace_id:
                continue

            for target_span_name in causes:
                # Find the target step in this correlation group
                target = None
                for s in steps:
                    if s["matched_span"] is not None and s["matched_span"].name == target_span_name:
                        target = s
                        break

                if target is None or target["matched_span"] is None:
                    continue
                if not target["matched_span"].trace_id:
                    continue

                # Same trace = causally connected
                if matched_span.trace_id == target["matched_span"].trace_id:
                    continue

                # Different trace: check for span links
                linked = False

                # Check if target links back to source
                for link in (target["matched_span"].links or []):
                    if link.span_id == matched_span.span_id:
                        linked = True
                        break

                # Check if source links to target
                if not linked:
                    for link in (matched_span.links or []):
                        if link.span_id == target["matched_span"].span_id:
                            linked = True
                            break

                if not linked:
                    violations.append(CorrelationViolation(
                        kind="causal-break",
                        key=key,
                        value=value,
                        steps=[step["name"], target_span_name],
                        message=(
                            f"'{matched_span.name}' declares causes: "
                            f"['{target_span_name}'] but spans are in different "
                            f"traces ({matched_span.trace_id}, "
                            f"{target['matched_span'].trace_id}) with no link. "
                            f"Propagate trace context or add a span link at the "
                            f"async boundary."
                        ),
                    ))

    return CorrelationResult(groups=groups, violations=violations)

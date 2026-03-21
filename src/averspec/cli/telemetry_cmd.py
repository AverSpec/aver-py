"""aver telemetry — diagnose and verify telemetry configuration."""

from __future__ import annotations

import json
import os
import socket
import sys
from pathlib import Path
from typing import Any

from averspec.telemetry_mode import resolve_telemetry_mode


def _check_port_available(port: int) -> bool:
    """Check if a TCP port is available for binding."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            s.bind(("127.0.0.1", port))
            return True
    except OSError:
        return False


def _resolve_source() -> str:
    """Determine where the telemetry mode came from."""
    if os.environ.get("AVER_TELEMETRY_MODE"):
        return "env"
    if os.environ.get("CI"):
        return "CI default"
    return "default"


def execute_diagnose() -> None:
    """Print telemetry diagnostic information."""
    mode = resolve_telemetry_mode()
    source = _resolve_source()
    is_ci = bool(os.environ.get("CI"))
    otlp_port = 4318
    port_available = _check_port_available(otlp_port)

    print(f"Telemetry mode: {mode} (source: {source})")
    print(f"CI detected: {is_ci}")
    print(f"OTLP receiver port {otlp_port}: {'available' if port_available else 'in use'}")


def _load_traces(path: str) -> list[dict[str, Any]]:
    """Load production traces from a JSON file or directory of JSON files."""
    from averspec.telemetry_verify import ProductionSpan, ProductionTrace

    p = Path(path)
    raw_traces: list[dict[str, Any]] = []

    if p.is_file():
        data = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(data, list):
            raw_traces = data
        else:
            raw_traces = [data]
    elif p.is_dir():
        for f in sorted(p.iterdir()):
            if f.suffix == ".json":
                data = json.loads(f.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    raw_traces.extend(data)
                else:
                    raw_traces.append(data)
    else:
        print(f"Error: traces path does not exist: {path}")
        sys.exit(1)

    traces: list[ProductionTrace] = []
    for raw in raw_traces:
        spans = []
        for s in raw.get("spans", []):
            spans.append(ProductionSpan(
                name=s["name"],
                attributes=s.get("attributes", {}),
                span_id=s.get("spanId"),
                parent_span_id=s.get("parentSpanId"),
            ))
        traces.append(ProductionTrace(
            trace_id=raw.get("traceId", "unknown"),
            spans=spans,
        ))

    return traces


def execute_verify(args) -> None:
    """Verify contracts against production traces."""
    from averspec.contract_io import read_contracts, read_contract_file
    from averspec.telemetry_contract import BehavioralContract
    from averspec.telemetry_verify import verify_contract

    contract_path = args.contract
    traces_path = args.traces
    verbose = args.verbose

    if not contract_path:
        print("Error: --contract is required")
        sys.exit(1)

    if not traces_path:
        print("Error: --traces is required")
        sys.exit(1)

    # Load contracts
    p = Path(contract_path)
    contracts: list[BehavioralContract] = []
    if p.is_file():
        result = read_contract_file(str(p))
        contracts.append(BehavioralContract(
            domain=result["domain"],
            entries=[result["entry"]],
        ))
    elif p.is_dir():
        contracts = read_contracts(str(p))
    else:
        print(f"Error: contract path does not exist: {contract_path}")
        sys.exit(1)

    if not contracts:
        print("No contracts found.")
        sys.exit(1)

    # Load traces
    traces = _load_traces(traces_path)

    if not traces:
        print("No traces found.")
        sys.exit(1)

    # Verify each contract
    total_violations = 0
    for contract in contracts:
        report = verify_contract(contract, traces)
        total_violations += report.total_violations

        print(f"Domain: {report.domain}")
        for result in report.results:
            status = "PASS" if not result.violations else "FAIL"
            print(f"  {status} {result.test_name} ({result.traces_matched}/{result.traces_checked} traces)")

            if verbose:
                for v in result.violations:
                    if v.kind == "missing-span":
                        print(f"    - missing span: {v.span_name} (trace: {v.trace_id})")
                    elif v.kind == "literal-mismatch":
                        print(f"    - literal mismatch: {v.span}.{v.attribute} expected={v.expected!r} actual={v.actual!r}")
                    elif v.kind == "correlation-violation":
                        print(f"    - correlation violation: {v.symbol}")
                    elif v.kind == "no-matching-traces":
                        print(f"    - {v.message}")

    print()
    if total_violations == 0:
        print("All contracts verified.")
        sys.exit(0)
    else:
        print(f"{total_violations} violation(s) found.")
        sys.exit(1)

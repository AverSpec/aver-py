"""Contract I/O: read and write behavioral contracts to disk."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from averspec.telemetry_contract import (
    AttributeBinding,
    BehavioralContract,
    ContractEntry,
    SpanExpectation,
)


def slugify(text: str) -> str:
    """Convert text to a URL-safe slug for filenames."""
    slug = text.lower()
    slug = re.sub(r"\s+", "-", slug)
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    slug = re.sub(r"-{2,}", "-", slug)
    slug = slug.strip("-")
    return slug


def _entry_to_dict(entry: ContractEntry) -> dict[str, Any]:
    """Serialize a ContractEntry to a JSON-compatible dict."""
    spans = []
    for span in entry.spans:
        s: dict[str, Any] = {"name": span.name}
        if span.attributes:
            attrs = {}
            for k, binding in span.attributes.items():
                b: dict[str, Any] = {"kind": binding.kind}
                if binding.kind == "literal" and binding.value is not None:
                    b["value"] = binding.value
                if binding.kind == "correlated" and binding.symbol is not None:
                    b["symbol"] = binding.symbol
                attrs[k] = b
            s["attributes"] = attrs
        if span.parent_name is not None:
            s["parentName"] = span.parent_name
        spans.append(s)
    return {"testName": entry.test_name, "spans": spans}


def _dict_to_entry(data: dict[str, Any]) -> ContractEntry:
    """Deserialize a dict to a ContractEntry."""
    spans = []
    for s in data.get("spans", []):
        attributes: dict[str, AttributeBinding] = {}
        for k, b in s.get("attributes", {}).items():
            attributes[k] = AttributeBinding(
                kind=b["kind"],
                value=b.get("value"),
                symbol=b.get("symbol"),
            )
        spans.append(SpanExpectation(
            name=s["name"],
            attributes=attributes,
            parent_name=s.get("parentName"),
        ))
    return ContractEntry(test_name=data["testName"], spans=spans)


def write_contracts(contract: BehavioralContract, base_dir: str) -> list[str]:
    """Write contract entries as individual JSON files.

    Creates one {slug}.contract.json per entry under base_dir/{domain}/.
    Returns list of written file paths.
    """
    domain_dir = Path(base_dir) / contract.domain
    domain_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc).isoformat()
    paths: list[str] = []

    for entry in contract.entries:
        slug = slugify(entry.test_name)
        file_path = domain_dir / f"{slug}.contract.json"

        file_data = {
            "version": 1,
            "domain": contract.domain,
            "testName": entry.test_name,
            "extractedAt": now,
            "entry": _entry_to_dict(entry),
        }

        file_path.write_text(
            json.dumps(file_data, indent=2) + "\n", encoding="utf-8"
        )
        paths.append(str(file_path))

    return paths


def read_contract_file(file_path: str) -> dict[str, Any]:
    """Read a single contract file with schema validation.

    Returns {"domain": str, "entry": ContractEntry}.
    """
    path = Path(file_path)
    raw = path.read_text(encoding="utf-8")

    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"Invalid JSON in contract file {file_path}") from exc

    if parsed.get("version") != 1:
        raise ValueError(
            f"Unsupported contract version {parsed.get('version')} in {file_path}"
        )

    if not isinstance(parsed.get("domain"), str) or parsed["domain"] == "":
        raise ValueError(f"Invalid contract file {file_path}: missing domain")

    if not parsed.get("entry"):
        raise ValueError(f"Invalid contract file {file_path}: missing entry")

    entry_raw = parsed["entry"]

    if not isinstance(entry_raw.get("testName"), str):
        raise ValueError(
            f"Invalid contract file {file_path}: missing entry.testName"
        )

    if not isinstance(entry_raw.get("spans"), list):
        raise ValueError(
            f"Invalid contract file {file_path}: missing entry.spans"
        )

    return {"domain": parsed["domain"], "entry": _dict_to_entry(entry_raw)}


def read_contracts(base_dir: str) -> list[BehavioralContract]:
    """Read all contract files from base_dir, grouped by domain.

    Returns empty list if directory doesn't exist.
    """
    base = Path(base_dir)
    if not base.exists():
        return []

    domain_map: dict[str, list[ContractEntry]] = {}

    for subdir in sorted(base.iterdir()):
        if not subdir.is_dir():
            continue

        for file in sorted(subdir.iterdir()):
            if not file.name.endswith(".contract.json"):
                continue

            result = read_contract_file(str(file))
            domain = result["domain"]
            entry = result["entry"]

            if domain not in domain_map:
                domain_map[domain] = []
            domain_map[domain].append(entry)

    contracts: list[BehavioralContract] = []
    for domain_name, entries in domain_map.items():
        contracts.append(BehavioralContract(domain=domain_name, entries=entries))

    return contracts

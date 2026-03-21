"""Tests for contract I/O: write, read, slugify, validation."""

import json

from averspec.contract_io import (
    slugify,
    write_contracts,
    read_contracts,
    read_contract_file,
)
from averspec.telemetry_contract import (
    AttributeBinding,
    BehavioralContract,
    ContractEntry,
    SpanExpectation,
)


sample_entry = ContractEntry(
    test_name="signup creates account",
    spans=[
        SpanExpectation(
            name="user.signup",
            attributes={
                "user.email": AttributeBinding(kind="correlated", symbol="$email"),
            },
        ),
        SpanExpectation(
            name="account.created",
            attributes={
                "account.email": AttributeBinding(kind="correlated", symbol="$email"),
            },
            parent_name="user.signup",
        ),
    ],
)

sample_contract = BehavioralContract(
    domain="signup-flow",
    entries=[sample_entry],
)


def test_slugify_spaces_to_hyphens():
    assert slugify("signup creates account") == "signup-creates-account"


def test_slugify_strips_special_chars():
    assert slugify("signup with 'special' chars & symbols!") == "signup-with-special-chars-symbols"


def test_slugify_collapses_hyphens():
    assert slugify("foo---bar   baz") == "foo-bar-baz"


def test_write_single_entry(tmp_path):
    paths = write_contracts(sample_contract, str(tmp_path))
    assert len(paths) == 1
    assert paths[0].endswith("signup-creates-account.contract.json")
    assert "signup-flow" in paths[0]


def test_write_multiple_entries(tmp_path):
    contract = BehavioralContract(
        domain="auth",
        entries=[
            ContractEntry(test_name="login succeeds", spans=[]),
            ContractEntry(test_name="login fails", spans=[]),
        ],
    )
    paths = write_contracts(contract, str(tmp_path))
    assert len(paths) == 2
    names = [p.split("/")[-1] for p in paths]
    assert "login-succeeds.contract.json" in names
    assert "login-fails.contract.json" in names


def test_read_back_matches_written(tmp_path):
    write_contracts(sample_contract, str(tmp_path))
    contracts = read_contracts(str(tmp_path))

    assert len(contracts) == 1
    assert contracts[0].domain == "signup-flow"
    assert len(contracts[0].entries) == 1
    entry = contracts[0].entries[0]
    assert entry.test_name == "signup creates account"
    assert len(entry.spans) == 2
    assert entry.spans[0].name == "user.signup"
    assert entry.spans[1].parent_name == "user.signup"


def test_file_format_validation(tmp_path):
    write_contracts(sample_contract, str(tmp_path))
    domain_dir = tmp_path / "signup-flow"
    files = list(domain_dir.glob("*.contract.json"))
    assert len(files) == 1

    raw = json.loads(files[0].read_text())
    assert raw["version"] == 1
    assert raw["domain"] == "signup-flow"
    assert raw["testName"] == "signup creates account"
    assert "extractedAt" in raw
    assert isinstance(raw["entry"]["spans"], list)


def test_missing_dir_creation(tmp_path):
    nested = tmp_path / "deeply" / "nested"
    paths = write_contracts(sample_contract, str(nested))
    assert len(paths) == 1
    # File should exist
    raw = json.loads(open(paths[0]).read())
    assert raw["version"] == 1


def test_read_contracts_nonexistent_dir(tmp_path):
    result = read_contracts(str(tmp_path / "does-not-exist"))
    assert result == []


def test_read_contract_file_invalid_json(tmp_path):
    bad = tmp_path / "bad.contract.json"
    bad.write_text("not valid json!!!")
    try:
        read_contract_file(str(bad))
        assert False, "Should have raised"
    except ValueError as e:
        assert "Invalid JSON" in str(e)

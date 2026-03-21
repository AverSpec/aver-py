"""Tests for the OTLP HTTP JSON receiver."""

import json
import urllib.request

import pytest

from averspec.otlp_receiver import create_otlp_receiver


@pytest.fixture
def receiver():
    r = create_otlp_receiver()
    port = r.start()
    yield r, port
    r.stop()


def _post(port: int, path: str, body: dict, content_type: str = "application/json") -> tuple[int, dict]:
    """Helper to POST JSON to the receiver."""
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=data,
        headers={"Content-Type": content_type},
        method="POST",
    )
    try:
        resp = urllib.request.urlopen(req)
        return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_start_stop():
    r = create_otlp_receiver()
    port = r.start()
    assert port > 0
    r.stop()


def test_post_traces_parsed_into_collected_spans(receiver):
    r, port = receiver

    body = {
        "resourceSpans": [{
            "scopeSpans": [{
                "spans": [
                    {
                        "traceId": "abc123",
                        "spanId": "span001",
                        "name": "order.checkout",
                        "attributes": [
                            {"key": "order.id", "value": {"stringValue": "ORD-42"}},
                            {"key": "amount", "value": {"intValue": "100"}},
                        ],
                    },
                    {
                        "traceId": "abc123",
                        "spanId": "span002",
                        "parentSpanId": "span001",
                        "name": "payment.charge",
                        "attributes": [
                            {"key": "price", "value": {"doubleValue": 29.99}},
                        ],
                    },
                ],
            }],
        }],
    }

    status, resp = _post(port, "/v1/traces", body)
    assert status == 200

    spans = r.get_spans()
    assert len(spans) == 2

    assert spans[0].trace_id == "abc123"
    assert spans[0].span_id == "span001"
    assert spans[0].name == "order.checkout"
    assert spans[0].attributes["order.id"] == "ORD-42"
    assert spans[0].attributes["amount"] == 100

    assert spans[1].parent_span_id == "span001"
    assert spans[1].attributes["price"] == 29.99


def test_reset_clears_spans(receiver):
    r, port = receiver

    body = {
        "resourceSpans": [{
            "scopeSpans": [{
                "spans": [
                    {"traceId": "a", "spanId": "1", "name": "test.span", "attributes": []},
                ],
            }],
        }],
    }

    _post(port, "/v1/traces", body)
    assert len(r.get_spans()) == 1

    r.reset()
    assert len(r.get_spans()) == 0


def test_415_on_protobuf_content_type(receiver):
    _, port = receiver

    data = json.dumps({}).encode()
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/v1/traces",
        data=data,
        headers={"Content-Type": "application/x-protobuf"},
        method="POST",
    )
    try:
        urllib.request.urlopen(req)
        assert False, "Expected HTTPError"
    except urllib.error.HTTPError as e:
        assert e.code == 415
        body = json.loads(e.read())
        assert "Unsupported content-type" in body["error"]
        assert "application/json" in body["error"]

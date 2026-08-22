from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .domain.models import new_id, utc_now

PROTOCOL_VERSION = 1


@dataclass(slots=True)
class ProtocolError(Exception):
    code: str
    message: str
    details: dict[str, Any] | None = None

    def __str__(self) -> str:
        return self.message


def parse_request(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ProtocolError("invalid_request", "request must be a JSON object")
    if value.get("protocol_version") != PROTOCOL_VERSION:
        raise ProtocolError("unsupported_protocol", "protocol_version must be 1")
    request_id = value.get("request_id")
    method = value.get("method")
    params = value.get("params", {})
    if not isinstance(request_id, str) or not request_id:
        raise ProtocolError("invalid_request", "request_id is required")
    if not isinstance(method, str) or not method:
        raise ProtocolError("invalid_request", "method is required")
    if not isinstance(params, dict):
        raise ProtocolError("invalid_params", "params must be an object")
    return {"request_id": request_id, "method": method, "params": params}


def response_ok(request_id: str, result: Any) -> dict[str, Any]:
    return {
        "protocol_version": PROTOCOL_VERSION,
        "request_id": request_id,
        "ok": True,
        "result": result,
    }


def response_error(request_id: str, error: ProtocolError) -> dict[str, Any]:
    return {
        "protocol_version": PROTOCOL_VERSION,
        "request_id": request_id,
        "ok": False,
        "error": {"code": error.code, "message": error.message, "details": error.details},
    }


def event(
    event_type: str,
    payload: dict[str, Any] | None = None,
    *,
    session_id: str | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    value: dict[str, Any] = {
        "protocol_version": PROTOCOL_VERSION,
        "event_id": new_id("evt"),
        "type": event_type,
        "occurred_at": utc_now(),
        "payload": payload or {},
    }
    if session_id is not None:
        value["session_id"] = session_id
    if run_id is not None:
        value["run_id"] = run_id
    return value

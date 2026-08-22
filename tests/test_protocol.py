from demo_agent.protocol import ProtocolError, event, parse_request, response_error, response_ok


def test_protocol_envelopes() -> None:
    request = parse_request({"protocol_version": 1, "request_id": "req_1", "method": "session.list", "params": {}})
    assert request["method"] == "session.list"
    assert response_ok("req_1", {"x": 1})["result"] == {"x": 1}
    assert response_error("req_1", ProtocolError("bad", "Bad"))["error"]["code"] == "bad"
    value = event("run.started", {}, session_id="s", run_id="r")
    assert value["event_id"].startswith("evt_")
    assert value["session_id"] == "s"


def test_protocol_rejects_bad_input() -> None:
    for value in (None, {}, {"protocol_version": 2, "request_id": "x", "method": "x"}):
        try:
            parse_request(value)
        except ProtocolError:
            pass
        else:
            raise AssertionError("invalid request accepted")

import json

from tradingagents.dataflows import alpha_vantage_common


def test_alpha_vantage_requests_use_timeout(monkeypatch):
    captured = {}

    class Response:
        text = json.dumps({})

        @staticmethod
        def raise_for_status():
            return None

    def fake_get(url, params, timeout):
        captured["url"] = url
        captured["params"] = params
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setenv("ALPHA_VANTAGE_API_KEY", "test-key")
    monkeypatch.setattr(alpha_vantage_common.requests, "get", fake_get)

    alpha_vantage_common._make_api_request("OVERVIEW", {"symbol": "AAPL"})

    assert captured["timeout"] == 30
    assert captured["params"]["apikey"] == "test-key"

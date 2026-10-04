import json
from pathlib import Path

import pytest
import requests

from backend import providers
from backend.schemas import ContentBrief, Settings


@pytest.mark.parametrize("use_proxy", [True, False])
@pytest.mark.parametrize("operation", ["brief", "style", "scripts"])
def test_text_operations_use_selected_route_once(monkeypatch, use_proxy, operation):
    settings = Settings(
        llm_base_url="https://text.example/v1",
        llm_model="test-model",
        llm_api_key="test-secret",
        llm_use_env_proxy=use_proxy,
    ).model_dump()
    result = {
        "brief": ContentBrief(
            narration="测试旁白",
            audience="读者",
            source_notes="梗概",
            promise="反差",
            opening="测试旁白",
            payoff="兑现",
            cliffhanger="悬念",
        ).model_dump(),
        "style": {"name": "漫画", "style": "二维漫画", "reason": "原文为校园故事"},
        "scripts": {
            "scripts": json.loads(
                (Path(__file__).parent / "fixtures/story.json").read_text()
            )
        },
    }[operation]
    calls = []

    class Response:
        ok = True

        def json(self):
            return {"choices": [{"message": {"content": json.dumps(result)}}]}

    def record(route, url, kwargs):
        calls.append(route)
        assert url == "https://text.example/v1/chat/completions"
        assert kwargs["headers"]["Authorization"] == "Bearer test-secret"
        assert kwargs["json"]["model"] == "test-model"
        return Response()

    class Session:
        trust_env = True

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def post(self, url, **kwargs):
            return record(self.trust_env, url, kwargs)

    monkeypatch.setenv("HTTPS_PROXY", "http://unavailable.invalid:8888")
    monkeypatch.setattr(providers.requests, "Session", Session)
    monkeypatch.setattr(
        providers.requests, "post", lambda url, **kw: record(True, url, kw)
    )
    if operation == "brief":
        providers.content_brief("原文", settings, story_format="narration")
    elif operation == "style":
        providers.recommend_style("原文", settings)
    else:
        providers.scripts("原文", "漫画", settings)
    assert calls == [use_proxy]


@pytest.mark.parametrize(
    "error,expected",
    [
        (requests.exceptions.ProxyError, "代理连接失败"),
        (requests.exceptions.SSLError, "TLS 连接失败"),
        (requests.ConnectTimeout, "请求超时"),
        (requests.ReadTimeout, "请求超时"),
        (requests.ConnectionError, "连接失败"),
    ],
)
def test_text_errors_are_specific_redacted_and_not_retried(
    monkeypatch, error, expected
):
    calls = []

    def post(*args, **kwargs):
        calls.append(1)
        raise error("secret-key and private URL must not appear")

    monkeypatch.setattr(providers.requests, "post", post)
    with pytest.raises(ValueError) as caught:
        providers.text_request(Settings().model_dump(), {})
    assert expected in str(caught.value)
    assert "未自动重试" in str(caught.value)
    assert "secret-key" not in str(caught.value)
    assert calls == [1]


def test_invalid_response_json_is_not_reported_as_connection_failure(monkeypatch):
    class Response:
        ok = True

        def json(self):
            raise requests.exceptions.JSONDecodeError("Invalid", "<html>", 0)

    monkeypatch.setattr(providers.requests, "post", lambda *a, **kw: Response())
    settings = Settings(llm_api_key="test", llm_model="test").model_dump()
    with pytest.raises(ValueError, match="不是有效 JSON"):
        providers.content_brief("原文", settings)

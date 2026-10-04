import copy
import json
import time

import pytest
from fastapi.testclient import TestClient

from backend import providers, workflow
from backend.api import create_app
from backend.schemas import ContentBrief, Script, Settings
from backend.services import signature, video_prompt


def brief_fixture(fmt="dialogue"):
    return ContentBrief(
        format=fmt,
        audience="甜宠读者",
        source_notes="第一章：妻子入病房，丈夫认出同桌。",
        promise="嚷着离婚变成舍不得放手",
        opening="丈夫拒绝婚姻，妻子推门",
        payoff="认出妻子后改口",
        cliffhanger="妻子会留下吗？",
        target_duration=20,
        beats=[
            {
                "scene": "医院病房·日",
                "action": "池渊抱着枕头抗议",
                "speaker": "池渊",
                "line": "这婚我不结！",
                "emotion": "嘴硬，急躁",
            },
            {
                "scene": "医院病房·日",
                "action": "姜晚音推门，池渊突然安静",
                "speaker": "",
                "line": "",
                "emotion": "惊讶，停顿",
            },
            {
                "scene": "医院病房·日",
                "action": "姜晚音站在门口看着他",
                "speaker": "姜晚音",
                "line": "你要离婚？",
                "emotion": "平静，略带试探",
            },
            {
                "scene": "医院病房·日",
                "action": "池渊伸手挽留",
                "speaker": "池渊",
                "line": "我不知道是你。",
                "emotion": "害羞，放轻声音",
            },
        ],
    ).model_dump()


def script_fixture(brief):
    return Script.model_validate(
        {
            "title": "认出同桌",
            "hook": brief["opening"],
            "synopsis": brief["promise"],
            "characters": [
                {
                    "name": "池渊",
                    "appearance": "成年男性，短发，病服",
                    "voice": "voice-a",
                    "voice_description": "青年男声，清亮，普通话",
                },
                {
                    "name": "姜晚音",
                    "appearance": "成年女性，黑色西装",
                    "voice": "voice-b",
                    "voice_description": "沉稳女声，语速舒缓",
                },
            ],
            "shots": [
                {
                    "title": f"表演{i}",
                    "scene": b["scene"],
                    "visual": b["action"],
                    "speaker": b["speaker"],
                    "narration": b["line"],
                    "delivery": b["emotion"],
                    "beat_index": i,
                    "duration": 4,
                    "characters": ["池渊", "姜晚音"],
                    "purpose": "推进关系反转",
                    "start_state": "妻子在门边，丈夫在床上",
                    "end_state": "妻子在门边，丈夫在床上",
                }
                for i, b in enumerate(brief["beats"], 1)
            ],
        }
    ).model_dump()


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path), headers={"X-Drama-Client": "1"}) as c:
        yield c


def wait(c, pid):
    for _ in range(100):
        p = c.get(f"/api/projects/{pid}").json()
        if p["job"].get("status") != "running":
            return p
        time.sleep(0.05)
    pytest.fail("job did not finish")


def make_project(c):
    p = c.post(
        "/api/projects",
        json={"title": "对话测试", "premise": "失忆丈夫认出妻子", "style": "都市漫画"},
    ).json()
    assert p["story_format"] == p["workflow"]["brief"]["format"] == "dialogue"
    return p


def test_dialogue_import_review_animatic_and_format_change(client, monkeypatch):
    p = make_project(client)
    pid = p["id"]
    endpoint = f"/api/projects/{pid}"
    brief = brief_fixture()
    assert client.put(endpoint + "/brief", json=brief).status_code == 200
    review = client.post(
        endpoint + "/workflow/review",
        json={"stage": "content", "notes": "台词与原文关系一致"},
    )
    assert review.status_code == 200, review.text
    script = script_fixture(brief)
    p = client.post(endpoint + "/scripts", json=script).json()
    p = client.post(endpoint + f"/scripts/{p['scripts'][0]['id']}/select").json()
    for stage in ("script", "characters", "shots"):
        assert client.post(endpoint + f"/approve/{stage}").status_code == 200
    assert (
        client.post(
            endpoint + "/export", json={"kind": "animatic", "voice": False}
        ).status_code
        == 200
    )
    p = wait(client, pid)
    assert p["job"]["status"] == "done", p["job"]
    assert len(p["exports"][-1]["audio_sources"]) == 4
    assert all(a["source"] == "silent" for a in p["exports"][-1]["audio_sources"])
    p = client.post(
        endpoint + "/workflow/review",
        json={
            "stage": "preview",
            "artifact_id": p["exports"][-1]["id"],
            "notes": "动作反应与角色对白衔接正确",
        },
    ).json()
    assert p["workflow_status"]["preview_ok"]
    assert not p["workflow_status"]["blockers"]
    # Swap the speaker while keeping exactly the same words: must fail production checks.
    shot = p["shots"][0]
    p = client.put(
        endpoint + f"/shots/{shot['id']}", json={**shot, "speaker": "姜晚音"}
    ).json()
    assert any("说话人不符" in s for s in p["workflow_status"]["blockers"])
    assert not p["workflow_status"]["preview_ok"]
    before = copy.deepcopy(p["workflow"]["brief"])
    p = client.put(endpoint, json={**p, "story_format": "mixed"}).json()
    assert p["workflow"]["brief"] == before  # no silent rewrite of user content
    assert not p["workflow_status"]["content_ok"]
    assert not p["script_approved"]
    assert client.post(endpoint + "/plan", json={"mode": "ai"}).status_code == 400


@pytest.mark.parametrize(
    "change,match",
    [
        ("speaker", "说话人"),
        ("line", "台词"),
        ("missing", "全部剧本段落"),
        ("order", "顺序"),
        ("index", "编号"),
        ("scene", "场景"),
    ],
)
def test_dialogue_drift_is_rejected(change, match):
    brief = brief_fixture()
    shots = script_fixture(brief)["shots"]
    if change == "speaker":
        shots[0]["speaker"] = "旁白"
    if change == "line":
        shots[0]["narration"] += "我爱你"
    if change == "missing":
        shots.pop(1)
    if change == "order":
        shots.reverse()
    if change == "index":
        shots[0]["beat_index"] = None
    if change == "scene":
        shots[0]["scene"] = "家中"
    assert any(match in e for e in workflow.script_errors(brief, shots))


def test_split_dialogue_and_reaction_shots_are_allowed():
    brief = brief_fixture()
    shots = script_fixture(brief)["shots"]
    head = shots.pop(0)
    shots[:0] = [
        {**head, "narration": "这婚"},
        {**head, "narration": "", "speaker": ""},
        {**head, "narration": "我不结！"},
    ]
    assert not workflow.script_errors(brief, shots)


def test_mixed_allows_narration_but_dialogue_does_not():
    brief = brief_fixture()
    brief["beats"][0]["speaker"] = "旁白"
    p = {"story_format": "dialogue", "workflow": {"brief": brief}}
    assert any("需要旁白" in e for e in workflow.brief_errors(p))
    p["story_format"] = brief["format"] = "mixed"
    assert not workflow.brief_errors(p)
    assert not workflow.script_errors(brief, script_fixture(brief)["shots"])


def test_legacy_project_stays_narration_when_updated(client):
    p = make_project(client)
    pid = p["id"]
    store = client.app.state.studio.store

    def legacy(current):
        current.pop("story_format")
        current["workflow"]["brief"] = {"narration": "已有旁白"}

    store.change(pid, legacy)
    p = client.put(
        f"/api/projects/{pid}",
        json={"title": "只改名字", "premise": p["premise"], "style": p["style"]},
    ).json()
    assert p["workflow_status"]["story_format"] == "narration"
    assert p["workflow"]["brief"]["narration"] == "已有旁白"
    assert "story_format" not in store.read(pid)


def test_video_prompt_uses_character_voice_delivery_and_silent_reactions():
    brief = brief_fixture()
    script = script_fixture(brief)
    p = {**script, "style": "漫画"}
    prompt = video_prompt(p, p["shots"][0])
    assert "青年男声" in prompt and "嘴硬，急躁" in prompt and "口型同步" in prompt
    silent = video_prompt(p, p["shots"][1])
    assert "不要对白" in silent and "准确且只说一次" not in silent
    p["shots"][0]["characters"] = ["姜晚音"]
    assert "画外声音" in video_prompt(p, p["shots"][0])
    before = signature(p, p["shots"][0])
    p["characters"][0]["voice_description"] = "低沉男声"
    assert signature(p, p["shots"][0]) != before
    # Empty added fields must not stale old video candidates.
    for c in p["characters"]:
        c.pop("voice_description")
    before = signature(p, p["shots"][0])
    for c in p["characters"]:
        c["voice_description"] = ""
    assert signature(p, p["shots"][0]) == before


def test_ai_preserves_format_and_rejects_wrong_attribution(monkeypatch):
    brief = brief_fixture()
    script = script_fixture(brief)
    calls = []
    outputs = [brief, {"scripts": [script]}]

    class Response:
        ok = True

        def json(self):
            return {"choices": [{"message": {"content": json.dumps(outputs.pop(0))}}]}

    def post(*args, **kwargs):
        calls.append(kwargs["json"])
        return Response()

    monkeypatch.setattr(providers.requests, "post", post)
    settings = Settings(llm_api_key="fake", llm_model="fake").model_dump()
    drafted = providers.content_brief("原文", settings)
    assert drafted["format"] == "dialogue" and not drafted["narration"]
    assert (
        providers.scripts("原文", "漫画", settings, brief=drafted)[0]["shots"][0][
            "speaker"
        ]
        == "池渊"
    )
    assert "format填写dialogue" in calls[0]["messages"][0]["content"]
    script["shots"][0]["speaker"] = "旁白"
    outputs.append({"scripts": [script]})
    with pytest.raises(ValueError, match="说话人"):
        providers.scripts("原文", "漫画", settings, brief=drafted)
    outputs.append({**brief, "format": "narration", "narration": "错误旁白"})
    with pytest.raises(ValueError, match="所选形式"):
        providers.content_brief("原文", settings)

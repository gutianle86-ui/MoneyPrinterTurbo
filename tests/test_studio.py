import array
import io
import json
import math
import re
import subprocess
import threading
import time
import wave
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend import media, providers
from backend.api import create_app
from backend.schemas import Character, Script, Settings
from backend.services import Studio
from backend.storage import Store

HEADERS = {"X-Drama-Client": "1"}


def fixture_scripts():
    path = Path(__file__).parent / "fixtures" / "story.json"
    return [
        Script.model_validate(item).model_dump()
        for item in json.loads(path.read_text("utf-8"))
    ]


@pytest.mark.parametrize("fallback", [False, True])
def test_ark_download_direct_with_proxy_fallback_is_atomic(
    tmp_path, monkeypatch, fallback
):
    target = tmp_path / "clip.mp4"
    target.write_bytes(b"old")
    routes = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def raise_for_status(self):
            pass

        def iter_content(self, size):
            yield b"new"
            assert target.read_bytes() == b"old"
            yield b"-complete"

    class Session(Response):
        trust_env = True

        def get(self, *args, **kwargs):
            routes.append(self.trust_env)
            if fallback and not self.trust_env:
                raise providers.requests.ConnectionError("direct unavailable")
            return Response()

    monkeypatch.setattr(providers.requests, "Session", Session)
    providers.download(
        "https://ark-acg-cn-beijing.tos-cn-beijing.volces.com/clip", target
    )
    assert routes == ([False, True] if fallback else [False])
    assert target.read_bytes() == b"new-complete"
    assert not target.with_name("clip.mp4.part").exists()
    target.write_bytes(b"old")
    routes.clear()
    providers.download("https://media.example.com/clip", tmp_path / "other.mp4")
    assert routes == [True]


def test_frontend_build_and_schema_are_served(client):
    """FastAPI serves the Vue build without exposing frontend source or config."""
    page = client.get("/")
    assert page.status_code == 200
    assert 'type="module"' in page.text
    assets = re.findall(r'(?:src|href)="(/static/[^"]+)"', page.text)
    assert assets, "Run npm ci and npm run build in frontend before tests"
    for path in assets:
        response = client.get(path)
        assert response.status_code == 200
        assert response.content
    for path in ("/src/main.ts", "/src/api.ts", "/package.json", "/app.js"):
        assert client.get(path).status_code == 404
    schema = client.get("/openapi.json").json()
    assert "/api/quick-films" not in schema["paths"]
    assert "/api/projects/{pid}/quick-film/resume" not in schema["paths"]
    assert "/api/projects/{pid}/export" in schema["paths"]


def test_missing_vue_build_keeps_api_available_and_explains_setup(tmp_path):
    app = create_app(tmp_path / "storage", frontend_root=tmp_path / "missing-dist")
    with TestClient(app, headers=HEADERS) as client:
        response = client.get("/")
        assert response.status_code == 503
        assert "npm run build" in response.json()["detail"]
        assert client.get("/api/status").status_code == 200
        assert client.get("/src/main.ts").status_code == 404


def test_production_preserves_native_sound_and_full_hd_with_captions(tmp_path):
    source = tmp_path / "native.mp4"
    output = tmp_path / "production.mp4"
    media.run(
        [
            "-f",
            "lavfi",
            "-i",
            "color=c=navy:s=1080x1920:r=24",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=48000",
            "-t",
            "1.6",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-c:a",
            "aac",
            source,
        ]
    )
    duration = media.render_shot(
        source,
        output,
        {"duration": 1, "narration": "声音和高清画面都应保留"},
        tmp_path / "work",
        production=True,
    )
    assert duration == pytest.approx(1.6, abs=0.05)
    assert media.info(output)["duration"] == pytest.approx(1.6, abs=0.08)
    probe = subprocess.run(
        [media.ffmpeg(), "-hide_banner", "-i", str(output)],
        capture_output=True,
        check=False,
    )
    assert "1080x1920" in probe.stderr.decode()
    audio = subprocess.run(
        [
            media.ffmpeg(),
            "-v",
            "error",
            "-i",
            str(output),
            "-map",
            "0:a:0",
            "-f",
            "s16le",
            "-ac",
            "1",
            "-",
        ],
        capture_output=True,
        check=True,
    )
    samples = array.array("h", audio.stdout)
    rms = math.sqrt(sum(x * x for x in samples) / len(samples))
    assert rms > 1000, "Native audio was replaced with silence"


@pytest.fixture
def client(tmp_path):
    app = create_app(tmp_path)
    with TestClient(app, headers=HEADERS) as client:
        yield client
    app.state.studio.pool.shutdown(wait=True)


def wait(client, pid, timeout=30):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        p = client.get(f"/api/projects/{pid}").json()
        if p["job"].get("status") != "running":
            return p
        time.sleep(0.03)
    raise AssertionError("job did not finish")


def setup_project(client, approved=True, budget=100, guided=False):
    p = client.post(
        "/api/projects",
        json={
            "title": "测试剧",
            "story_format": "narration",
            "premise": "电梯里的秘密",
            "budget": budget,
            "style": "二维悬疑漫剧，蓝黑色调，电影光影",
        },
    ).json()
    pid = p["id"]
    if not guided:
        # Existing regression cases cover projects created before guided workflow.
        client.app.state.studio.store.change(pid, lambda p: p.pop("workflow"))
    script = fixture_scripts()[0]
    script["shots"] = script["shots"][:2]
    for shot in script["shots"]:
        shot["duration"] = 2
    p = client.post(f"/api/projects/{pid}/scripts", json=script).json()
    p = client.post(
        f"/api/projects/{pid}/scripts/{p['scripts'][0]['id']}/select"
    ).json()
    if approved:
        for stage in ("script", "characters", "shots"):
            response = client.post(f"/api/projects/{pid}/approve/{stage}")
            assert response.status_code == 200, response.text
            p = response.json()
    return p


def generate_preview(client, p):
    result = client.post(
        f"/api/projects/{p['id']}/generate",
        json={
            "mode": "preview",
            "shot_ids": [s["id"] for s in p["shots"]],
            "variants": 2,
        },
    )
    assert result.status_code == 200, result.text
    p = wait(client, p["id"])
    assert p["job"]["status"] == "done", p["job"]
    return client.post(f"/api/projects/{p['id']}/select-first").json()


def test_preview_complete_loop_with_actual_mp4_and_subtitles(client, monkeypatch):
    def reject_system_speech(*args, **kwargs):
        raise AssertionError("Default export must not replace audio with system speech")

    monkeypatch.setattr(media, "speech", reject_system_speech)
    p = generate_preview(client, setup_project(client))
    assert all(len(s["candidates"]) == 2 for s in p["shots"])
    assert p["reserved_cost"] == 0
    shot = p["shots"][0]
    corrected = "与实际配音一致的字幕"
    selected = client.post(
        f"/api/projects/{p['id']}/shots/{shot['id']}/select",
        json={"candidate_id": shot["selected"], "subtitle_text": corrected},
    )
    assert selected.status_code == 200
    assert selected.json()["shots"][0]["narration"] == shot["narration"]
    response = client.post(f"/api/projects/{p['id']}/export", json={"kind": "preview"})
    assert response.status_code == 200
    p = wait(client, p["id"])
    assert p["job"]["status"] == "done", p["job"]
    output = p["exports"][0]
    video = client.get(f"/assets/{p['id']}/{output['file']}")
    assert video.status_code == 200 and b"ftyp" in video.content[:40]
    path = client.app.state.studio.store.directory(p["id"]) / output["file"]
    details = media.info(path)
    assert details["video"] and details["audio"]
    assert 3.9 <= details["duration"] <= 4.2
    subtitles = client.get(f"/assets/{p['id']}/{output['subtitle']}").text
    assert "00:00:02,000 --> 00:00:04,000" in subtitles
    assert corrected in subtitles
    assert shot["narration"] not in subtitles
    manifest = client.get(f"/assets/{p['id']}/{output['manifest']}").json()
    assert manifest["shots"][0]["selected"] == p["shots"][0]["selected"]
    assert manifest["export_settings"]["voice"] is False
    assert {a["source"] for a in manifest["audio_sources"]} == {"silent"}
    assert output["audio_sources"] == manifest["audio_sources"]
    assert output["cost_summary"] == manifest["cost_summary"]
    assert output["cost_summary"]["estimated_video_cost"] == 0
    # Future production spending must not rewrite the exported version's costs.
    client.app.state.studio.store.change(
        p["id"], lambda current: current.update(reserved_cost=10)
    )
    later = client.get(f"/api/projects/{p['id']}").json()
    assert later["cost_summary"]["estimated_video_cost"] == 10
    assert later["exports"][0]["cost_summary"] == output["cost_summary"]


@pytest.mark.parametrize(
    "model", ["doubao-seedance-2-0-mini-260615", "doubao-seedance-2-5-260628"]
)
def test_manual_generation_sends_dialogue_and_native_audio(client, monkeypatch, model):
    p = setup_project(client)
    studio = client.app.state.studio

    def set_shot(current):
        shot = current["shots"][0]
        shot.update(
            duration=6,
            speaker="陈默",
            characters=["林夏"],
            narration="别出电梯。外面那个人不是我。",
        )

    studio.store.change(p["id"], set_shot)

    def set_reference(current):
        current["characters"][0]["reference_uri"] = "asset://asset-fictional-linxia"

    studio.store.change(p["id"], set_reference)
    settings = Settings(
        seedance_api_key="fake", seedance_model=model, estimate_per_second=1
    ).model_dump()
    monkeypatch.setattr(providers, "load_settings", lambda path: settings)
    payloads = []

    class Response:
        ok = True
        status_code = 200

        def json(self):
            return {"id": "fake-task"}

    def post(url, **kwargs):
        payloads.append(kwargs["json"])
        return Response()

    def stop_before_download(*args):
        raise ValueError("Test stops after submission; no real video service is called")

    monkeypatch.setattr(providers.requests, "post", post)
    monkeypatch.setattr(providers, "wait_video", stop_before_download)
    response = client.post(
        f"/api/projects/{p['id']}/generate",
        json={
            "mode": "seedance",
            "shot_ids": [p["shots"][0]["id"]],
            "confirm_paid": True,
        },
    )
    assert response.status_code == 200, response.text
    p = wait(client, p["id"])
    candidate = p["shots"][0]["candidates"][0]
    assert len(payloads) == 1
    assert payloads[0] == candidate["request"]
    assert payloads[0]["generate_audio"] is True
    assert payloads[0]["content"][1] == {
        "type": "image_url",
        "image_url": {"url": "asset://asset-fictional-linxia"},
        "role": "reference_image",
    }
    assert candidate["reference_uris"] == ["asset://asset-fictional-linxia"]
    assert candidate["dialogue_requested"] is True
    prompt = payloads[0]["content"][0]["text"]
    assert "别出电梯。外面那个人不是我。" in prompt
    assert "说话人是陈默" in prompt
    assert "说话人不在画面中" in prompt
    assert "参考图1对应角色林夏" in prompt


def test_character_reference_upload_is_archived_and_invalidates_related_shots(client):
    p = setup_project(client)
    buffer = io.BytesIO()
    Image.new("RGB", (900, 1200), "gray").save(buffer, format="PNG")
    endpoint = f"/api/projects/{p['id']}"
    response = client.post(
        endpoint + "/characters/0/reference",
        files={"file": ("character.png", buffer.getvalue(), "image/png")},
    )
    assert response.status_code == 200, response.text
    changed = response.json()
    filename = changed["characters"][0]["reference_file"]
    assert re.fullmatch(r"[a-f0-9]{32}\.png", filename)
    assert client.get(f"/assets/{p['id']}/{filename}").status_code == 200
    assert not changed["characters_approved"]
    related = [
        shot
        for shot in changed["shots"]
        if changed["characters"][0]["name"] in shot["characters"]
    ]
    assert related and all(not shot["approved"] for shot in related)


def test_reference_uri_validation_rejects_local_paths_and_http():
    base = {"name": "池渊", "appearance": "成年男性"}
    for invalid in (
        "/tmp/person.png",
        "file:///tmp/person.png",
        "http://example.com/a.png",
    ):
        with pytest.raises(ValueError):
            Character(**base, reference_uri=invalid)
    assert Character(**base, reference_uri="asset://asset-fictional").reference_uri
    assert Character(**base, reference_uri="https://example.com/a.png").reference_uri


def test_local_reference_is_rejected_before_seedance_submission(client, monkeypatch):
    p = setup_project(client)
    studio = client.app.state.studio
    shot = next(shot for shot in p["shots"] if shot["characters"])

    def set_local_reference(current):
        character_name = shot["characters"][0]
        next(
            character
            for character in current["characters"]
            if character["name"] == character_name
        )["reference_file"] = "character.png"

    studio.store.change(p["id"], set_local_reference)
    settings = Settings(seedance_api_key="fake", estimate_per_second=1).model_dump()
    monkeypatch.setattr(providers, "load_settings", lambda path: settings)
    called = False

    def post(*args, **kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(providers.requests, "post", post)
    response = client.post(
        f"/api/projects/{p['id']}/generate",
        json={
            "mode": "seedance",
            "shot_ids": [shot["id"]],
            "confirm_paid": True,
        },
    )
    assert response.status_code == 400
    assert "公网 HTTPS" in response.json()["detail"]
    assert not called


def test_provider_error_surfaces_code_and_message_without_request_content():
    class Response:
        def json(self):
            return {
                "error": {
                    "code": "InvalidParameter",
                    "message": "image_url only supports HTTPS or asset URI",
                }
            }

    assert providers.provider_error(Response()) == (
        "InvalidParameter · image_url only supports HTTPS or asset URI"
    )


def test_review_gates_and_stale_candidate_after_edit(client):
    p = setup_project(client, approved=False)
    endpoint = f"/api/projects/{p['id']}"
    assert (
        client.post(
            endpoint + "/generate",
            json={"mode": "preview", "shot_ids": [p["shots"][0]["id"]]},
        ).status_code
        == 400
    )
    for stage in ("script", "characters", "shots"):
        client.post(endpoint + "/approve/" + stage)
    p = generate_preview(client, client.get(endpoint).json())
    shot = p["shots"][0]
    response = client.put(
        endpoint + f"/shots/{shot['id']}", json={**shot, "visual": "修改后的新画面"}
    )
    assert response.status_code == 200
    changed = response.json()["shots"][0]
    assert not changed["approved"] and all(c["stale"] for c in changed["candidates"])
    assert (
        client.post(
            endpoint + f"/shots/{shot['id']}/select",
            json={"candidate_id": shot["selected"]},
        ).status_code
        == 400
    )
    assert (
        client.post(
            endpoint + "/export", json={"kind": "preview", "voice": False}
        ).status_code
        == 400
    )


def test_signed_reference_query_refresh_does_not_stale_candidate(client):
    p = setup_project(client)
    endpoint = f"/api/projects/{p['id']}"
    characters = p["characters"]
    characters[0]["reference_uri"] = (
        "https://bucket.example.com/roles/lead.png?X-Tos-Date=first&signature=old"
    )
    p = client.put(endpoint + "/characters", json=characters).json()
    for stage in ("characters", "shots"):
        client.post(endpoint + "/approve/" + stage)
    p = generate_preview(client, client.get(endpoint).json())
    characters = p["characters"]
    characters[0]["reference_uri"] = (
        "https://bucket.example.com/roles/lead.png?X-Tos-Date=second&signature=new"
    )
    refreshed = client.put(endpoint + "/characters", json=characters).json()
    assert not refreshed["shots"][0]["candidates"][0]["stale"]


def test_different_reference_object_stales_candidate(client):
    p = setup_project(client)
    endpoint = f"/api/projects/{p['id']}"
    characters = p["characters"]
    characters[0]["reference_uri"] = "https://bucket.example.com/roles/lead-a.png"
    p = client.put(endpoint + "/characters", json=characters).json()
    for stage in ("characters", "shots"):
        client.post(endpoint + "/approve/" + stage)
    p = generate_preview(client, client.get(endpoint).json())
    characters = p["characters"]
    characters[0]["reference_uri"] = "https://bucket.example.com/roles/lead-b.png"
    changed = client.put(endpoint + "/characters", json=characters).json()
    assert changed["shots"][0]["candidates"][0]["stale"]


def test_production_rejects_preview_and_accepts_uploaded_media(client):
    p = generate_preview(client, setup_project(client))
    endpoint = f"/api/projects/{p['id']}"
    assert (
        client.post(
            endpoint + "/export", json={"kind": "production", "voice": False}
        ).status_code
        == 400
    )
    buffer = io.BytesIO()
    Image.new("RGB", (100, 160), "navy").save(buffer, format="PNG")
    for shot in p["shots"]:
        response = client.post(
            endpoint + f"/shots/{shot['id']}/upload/visual",
            files={"file": ("frame.png", buffer.getvalue(), "image/png")},
        )
        assert response.status_code == 200, response.text
        current = next(s for s in response.json()["shots"] if s["id"] == shot["id"])
        client.post(
            endpoint + f"/shots/{shot['id']}/select",
            json={"candidate_id": current["candidates"][-1]["id"]},
        )
    response = client.post(
        endpoint + "/export", json={"kind": "production", "voice": False}
    )
    assert response.status_code == 200
    p = wait(client, p["id"])
    assert p["job"]["status"] == "done", p["job"]
    assert p["exports"][0]["kind"] == "production"


def test_uploaded_audio_extends_shot_instead_of_truncating(client):
    p = generate_preview(client, setup_project(client))
    audio = io.BytesIO()
    with wave.open(audio, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(8000)
        wav.writeframes(b"\0\0" * 8000 * 3)
    endpoint = f"/api/projects/{p['id']}"
    result = client.post(
        endpoint + f"/shots/{p['shots'][0]['id']}/upload/audio",
        files={"file": ("voice.wav", audio.getvalue(), "audio/wav")},
    )
    assert result.status_code == 200, result.text
    client.post(endpoint + "/export", json={"kind": "preview", "voice": False})
    result = wait(client, p["id"])
    assert result["job"]["status"] == "done", result["job"]
    assert result["exports"][0]["duration"] >= 5.2


def test_budget_and_confirmation_block_paid_submission(client, monkeypatch):
    p = setup_project(client, budget=1)
    settings = Settings(
        seedance_api_key="fake-secret", estimate_per_second=1
    ).model_dump()
    monkeypatch.setattr(providers, "load_settings", lambda path: settings)
    called = []
    monkeypatch.setattr(providers, "submit_video", lambda *a: called.append(a))
    data = {"mode": "seedance", "shot_ids": [p["shots"][0]["id"]]}
    endpoint = f"/api/projects/{p['id']}/generate"
    assert client.post(endpoint, json=data).status_code == 400
    assert client.post(endpoint, json={**data, "confirm_paid": True}).status_code == 400
    assert not called


def test_unknown_paid_submission_persists_and_blocks_retry(client, monkeypatch):
    p = setup_project(client)
    settings = Settings(
        seedance_api_key="fake-secret", estimate_per_second=1
    ).model_dump()
    monkeypatch.setattr(providers, "load_settings", lambda path: settings)
    calls = []

    def submit(*args, **kwargs):
        calls.append(1)
        raise providers.UncertainSubmission("提交结果未知，请核对")

    monkeypatch.setattr(providers, "submit_video", submit)
    data = {"mode": "seedance", "shot_ids": [p["shots"][0]["id"]], "confirm_paid": True}
    endpoint = f"/api/projects/{p['id']}/generate"
    assert client.post(endpoint, json=data).status_code == 200
    p = wait(client, p["id"])
    assert p["shots"][0]["candidates"][0]["status"] == "uncertain"
    assert p["reserved_cost"] == 2
    assert client.post(endpoint, json=data).status_code == 400
    assert calls == [1]


def test_definitive_rejection_before_task_id_releases_budget(client, monkeypatch):
    p = setup_project(client)
    settings = Settings(
        seedance_api_key="fake-secret", estimate_per_second=1
    ).model_dump()
    monkeypatch.setattr(providers, "load_settings", lambda path: settings)

    def reject(*args, **kwargs):
        raise ValueError("视频服务拒绝请求（HTTP 400）：InvalidParameter")

    monkeypatch.setattr(providers, "submit_video", reject)
    endpoint = f"/api/projects/{p['id']}"
    client.post(
        endpoint + "/generate",
        json={
            "mode": "seedance",
            "shot_ids": [p["shots"][0]["id"]],
            "confirm_paid": True,
        },
    )
    p = wait(client, p["id"])
    assert p["shots"][0]["candidates"][0]["status"] == "failed"
    assert p["reserved_cost"] == 0

    candidate = p["shots"][0]["candidates"][0]
    delete = client.delete(
        endpoint + f"/shots/{p['shots'][0]['id']}/candidates/{candidate['id']}"
    )
    assert delete.status_code == 200, delete.text
    assert delete.json()["shots"][0]["candidates"] == []


def test_candidate_delete_refuses_ready_or_remote_records(client):
    p = setup_project(client)
    studio = client.app.state.studio
    shot = p["shots"][0]

    def add_records(current):
        stored = current["shots"][0]
        stored["candidates"].extend(
            [
                {
                    "id": "ready-candidate",
                    "provider": "preview",
                    "status": "ready",
                    "signature": "test",
                    "file": "frame.png",
                    "task_id": None,
                    "created_at": "2026-01-01T00:00:00+00:00",
                    "estimated_cost": 0,
                },
                {
                    "id": "remote-failure",
                    "provider": "seedance",
                    "status": "failed",
                    "signature": "test",
                    "file": None,
                    "task_id": "remote-123",
                    "created_at": "2026-01-01T00:00:00+00:00",
                    "estimated_cost": 2,
                },
            ]
        )

    studio.store.change(p["id"], add_records)
    base = f"/api/projects/{p['id']}/shots/{shot['id']}/candidates"
    assert client.delete(base + "/ready-candidate").status_code == 400
    assert client.delete(base + "/remote-failure").status_code == 400


def test_known_remote_id_saved_before_poll_and_resume_does_not_resubmit(
    client, monkeypatch
):
    p = setup_project(client)
    settings = Settings(
        seedance_api_key="fake-secret", estimate_per_second=1
    ).model_dump()
    monkeypatch.setattr(providers, "load_settings", lambda path: settings)
    calls = []
    monkeypatch.setattr(
        providers,
        "submit_video",
        lambda *args, **kwargs: calls.append(1) or "remote-123",
    )

    def fail_poll(*args):
        stored = client.app.state.studio.store.read(p["id"])
        assert stored["shots"][0]["candidates"][0]["task_id"] == "remote-123"
        raise ValueError("查询暂时失败")

    monkeypatch.setattr(providers, "wait_video", fail_poll)
    endpoint = f"/api/projects/{p['id']}"
    client.post(
        endpoint + "/generate",
        json={
            "mode": "seedance",
            "shot_ids": [p["shots"][0]["id"]],
            "confirm_paid": True,
        },
    )
    p = wait(client, p["id"])
    c = p["shots"][0]["candidates"][0]
    assert c["status"] == "interrupted"
    client.post(endpoint + f"/shots/{p['shots'][0]['id']}/candidates/{c['id']}/resume")
    wait(client, p["id"])
    assert calls == [1]
    assert client.get(endpoint).json()["reserved_cost"] == 2


def test_active_job_blocks_edit_and_second_job(client):
    p = setup_project(client)
    event = threading.Event()
    studio = client.app.state.studio
    studio.job(p["id"], "blocking test", lambda: event.wait(5))
    try:
        endpoint = f"/api/projects/{p['id']}"
        assert (
            client.put(
                endpoint + f"/shots/{p['shots'][0]['id']}", json=p["shots"][0]
            ).status_code
            == 400
        )
        client.put(
            "/api/settings",
            json=Settings(llm_model="test-model", llm_api_key="test-key").model_dump(),
        )
        assert client.post(endpoint + "/plan", json={"mode": "ai"}).status_code == 400
    finally:
        event.set()


def test_restart_recovers_job_without_discarding_candidates(client):
    p = generate_preview(client, setup_project(client))
    store = client.app.state.studio.store
    original = store.read(p["id"])
    original["job"]["status"] = "running"
    original["shots"][0]["candidates"][0]["status"] = "generating"
    store.save(original)
    Store(store.root).recover()
    recovered = store.read(p["id"])
    assert recovered["job"]["status"] == "interrupted"
    assert recovered["shots"][0]["candidates"][0]["status"] == "interrupted"
    assert recovered["shots"][0]["candidates"][1]["status"] == "ready"


def test_settings_never_return_secrets_and_files_are_not_public(client):
    settings = Settings(
        llm_api_key="secret-a", seedance_api_key="secret-b"
    ).model_dump()
    response = client.put("/api/settings", json=settings)
    assert response.status_code == 200
    assert "secret-a" not in response.text and "secret-b" not in response.text
    assert "secret-a" not in client.get("/api/status").text
    assert client.get("/settings.json").status_code == 404
    p = setup_project(client)
    assert client.get(f"/assets/{p['id']}/project.json").status_code == 404
    assert (
        client.post(
            "/api/projects",
            headers={"Origin": "https://evil.example"},
            json={"title": "x", "premise": "x"},
        ).status_code
        == 403
    )


def test_model_switch_remembers_each_estimate_and_preserves_keys(client):
    large = "doubao-seedance-2-5-260628"
    mini = "doubao-seedance-2-0-mini-260615"
    settings = Settings(
        llm_base_url="https://api.deepseek.com",
        llm_model="deepseek-v4-pro",
        llm_api_key="text-secret",
        llm_use_env_proxy=False,
        seedance_api_key="video-secret",
        seedance_model=large,
        estimate_per_second=10,
    ).model_dump()
    assert client.put("/api/settings", json=settings).status_code == 200
    public = client.get("/api/status").json()
    assert set(public["video_models"]) == {large, mini}
    first = public["settings"]
    assert first["seedance_estimates"][large] == 10
    second = client.put(
        "/api/settings",
        json={
            **first,
            "seedance_model": mini,
            "estimate_per_second": 0.6,
        },
    ).json()
    assert second["seedance_estimates"][large] == 10
    assert second["seedance_estimates"][mini] == 0.6
    assert second["llm_api_key_configured"] and second["seedance_api_key_configured"]
    third = client.put(
        "/api/settings",
        json={
            **second,
            "seedance_model": large,
            "estimate_per_second": second["seedance_estimates"][large],
        },
    ).json()
    assert third["estimate_per_second"] == 10
    saved = providers.load_settings(client.app.state.studio.settings_path)
    assert saved["llm_api_key"] == "text-secret"
    assert saved["seedance_api_key"] == "video-secret"
    assert saved["llm_base_url"] == "https://api.deepseek.com"
    assert saved["llm_use_env_proxy"] is False
    assert "video-secret" not in str(third)


def test_invalid_upload_is_rejected_and_not_saved(client):
    p = setup_project(client)
    folder = client.app.state.studio.store.directory(p["id"])
    before = set(folder.iterdir())
    response = client.post(
        f"/api/projects/{p['id']}/shots/{p['shots'][0]['id']}/upload/visual",
        files={"file": ("broken.mp4", b"not a video", "video/mp4")},
    )
    assert response.status_code == 400
    assert set(folder.iterdir()) == before


def test_unknown_character_in_script_is_rejected(client):
    p = setup_project(client)
    script = fixture_scripts()[0]
    script["shots"][0]["characters"] = ["不存在的人"]
    assert (
        client.post(f"/api/projects/{p['id']}/scripts", json=script).status_code == 422
    )


def test_second_server_cannot_recover_or_modify_live_projects(client):
    p = setup_project(client)
    store = client.app.state.studio.store
    with pytest.raises(RuntimeError, match="已有工作台"):
        Studio(store.root)
    assert store.read(p["id"])["job"] == {}


def prepare_guided(client):
    p = setup_project(client, guided=True)
    pid = p["id"]
    characters = [
        {**c, "reference_uri": f"https://example.com/{i}.png"}
        for i, c in enumerate(p["characters"])
    ]
    p = client.put(f"/api/projects/{pid}/characters", json=characters).json()
    for s in p["shots"]:
        data = {
            **s,
            "duration": 4,
            "purpose": "呈现新的异常",
            "start_state": "主角站在电梯左侧，手握手机",
            "end_state": "主角站在电梯左侧，手握手机",
        }
        response = client.put(f"/api/projects/{pid}/shots/{s['id']}", json=data)
        assert response.status_code == 200, response.text
    p = client.get(f"/api/projects/{pid}").json()
    brief = {
        "audience": "悬疑小说读者",
        "source_notes": "测试梗概：只有十二层的楼出现十三层。",
        "promise": "熟悉的日常出现异常",
        "opening": p["shots"][0]["narration"],
        "payoff": "本条揭示楼层异常",
        "cliffhanger": "门外是谁？",
        "narration": "".join(s["narration"] for s in p["shots"]),
        "target_duration": 15,
    }
    p = client.put(f"/api/projects/{pid}/brief", json=brief).json()
    response = client.post(
        f"/api/projects/{pid}/workflow/review",
        json={"stage": "content", "notes": "已核对事实和核心反差"},
    )
    assert response.status_code == 200, response.text
    for stage in ("script", "characters", "shots"):
        p = client.post(f"/api/projects/{pid}/approve/{stage}").json()
    return p


def approve_animatic(client, p):
    pid = p["id"]
    response = client.post(
        f"/api/projects/{pid}/export", json={"kind": "animatic", "voice": False}
    )
    assert response.status_code == 200, response.text
    p = wait(client, pid)
    assert p["job"]["status"] == "done", p["job"]
    response = client.post(
        f"/api/projects/{pid}/workflow/review",
        json={
            "stage": "preview",
            "artifact_id": p["exports"][-1]["id"],
            "notes": "已观看预演，信息与节奏连贯",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_new_workflow_stops_unreviewed_paid_work_before_submission(client, monkeypatch):
    p = setup_project(client, guided=True)
    client.put(
        "/api/settings",
        json=Settings(seedance_api_key="fake", estimate_per_second=1).model_dump(),
    )

    def must_not_submit(*args, **kwargs):
        pytest.fail("unreviewed work reached paid provider")

    monkeypatch.setattr(providers, "submit_video", must_not_submit)
    response = client.post(
        f"/api/projects/{p['id']}/generate",
        json={
            "mode": "seedance",
            "shot_ids": [p["shots"][0]["id"]],
            "confirm_paid": True,
        },
    )
    assert response.status_code == 400
    assert "策划" in response.text
    assert client.get(f"/api/projects/{p['id']}").json()["reserved_cost"] == 0
    response = client.post(f"/api/projects/{p['id']}/plan", json={"mode": "ai"})
    assert response.status_code == 400
    assert "策划" in response.text


def test_animatic_does_not_change_candidates_and_invalidates_after_revision(client):
    p = prepare_guided(client)
    # Existing selections are not overwritten by the free complete preview.
    p = generate_preview(client, p)
    before = [(s["selected"], len(s["candidates"])) for s in p["shots"]]
    p = approve_animatic(client, p)
    assert p["workflow_status"]["preview_ok"]
    assert not p["workflow_status"]["blockers"]
    assert [(s["selected"], len(s["candidates"])) for s in p["shots"]] == before
    assert p["reserved_cost"] == 0
    old_preview = p["exports"][-1]["id"]
    shot = p["shots"][0]
    response = client.put(
        f"/api/projects/{p['id']}/shots/{shot['id']}",
        json={**shot, "start_state": "主角站在电梯右侧"},
    )
    updated = response.json()
    assert updated["workflow_status"]["content_ok"]
    assert not updated["workflow_status"]["preview_ok"]
    assert (
        client.post(
            f"/api/projects/{p['id']}/workflow/review",
            json={
                "stage": "preview",
                "artifact_id": old_preview,
                "notes": "尝试复用过期预演记录",
            },
        ).status_code
        == 400
    )
    brief = {**p["workflow"]["brief"], "promise": "新的情绪承诺"}
    updated = client.put(f"/api/projects/{p['id']}/brief", json=brief).json()
    assert not updated["workflow_status"]["content_ok"]


def test_guided_pilot_before_batch_and_reject_before_retry(
    client, monkeypatch, tmp_path
):
    p = approve_animatic(client, prepare_guided(client))
    pid = p["id"]
    client.put(
        "/api/settings",
        json=Settings(seedance_api_key="fake", estimate_per_second=1).model_dump(),
    )
    sample = tmp_path / "pilot.mp4"
    media.run(
        [
            "-f",
            "lavfi",
            "-i",
            "color=blue:s=160x284:r=24",
            "-t",
            "0.5",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            sample,
        ]
    )
    submitted = []
    monkeypatch.setattr(
        providers, "submit_video", lambda *a, **kw: submitted.append(a) or "test-task"
    )
    monkeypatch.setattr(providers, "wait_video", lambda *a: "https://example.com/video")
    monkeypatch.setattr(
        providers, "download", lambda url, path: path.write_bytes(sample.read_bytes())
    )
    request = {
        "mode": "seedance",
        "confirm_paid": True,
        "shot_ids": [s["id"] for s in p["shots"]],
    }
    assert client.post(f"/api/projects/{pid}/generate", json=request).status_code == 400
    assert submitted == []
    single = {**request, "shot_ids": [p["shots"][0]["id"]]}
    assert client.post(f"/api/projects/{pid}/generate", json=single).status_code == 200
    p = wait(client, pid)
    assert p["job"]["status"] == "done"
    assert len(submitted) == 1
    assert "开场状态" in submitted[0][0]
    # A second single-shot submission also cannot skip sample review.
    assert client.post(f"/api/projects/{pid}/generate", json=single).status_code == 400
    c = p["shots"][0]["candidates"][-1]
    response = client.post(
        f"/api/projects/{pid}/workflow/review",
        json={
            "stage": "pilot",
            "artifact_id": c["id"],
            "notes": "已查看人物动作和声音，满足样片要求",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["workflow_status"]["pilot_ok"]
    assert client.post(f"/api/projects/{pid}/generate", json=request).status_code == 200
    p = wait(client, pid)
    assert p["job"]["status"] == "done"
    assert len(submitted) == 3
    brief = {**p["workflow"]["brief"], "target_duration": 20}
    updated = client.put(f"/api/projects/{pid}/brief", json=brief).json()
    assert not updated["workflow_status"]["pilot_ok"]
    assert client.post(f"/api/projects/{pid}/generate", json=request).status_code == 400


def test_guided_text_drift_and_still_image_cannot_pass_pilot(client):
    p = approve_animatic(client, prepare_guided(client))
    p = generate_preview(client, p)
    response = client.post(
        f"/api/projects/{p['id']}/workflow/review",
        json={
            "stage": "pilot",
            "artifact_id": p["shots"][0]["candidates"][0]["id"],
            "notes": "不能将文字卡当作视频样片",
        },
    )
    assert response.status_code == 400
    shot = p["shots"][0]
    p = client.put(
        f"/api/projects/{p['id']}/shots/{shot['id']}",
        json={**shot, "narration": "未经文案审核的新故事"},
    ).json()
    assert any("不一致" in b for b in p["workflow_status"]["blockers"])


def test_explicit_clip_edit_trims_actual_frames_and_invalidates_export(
    client, tmp_path
):
    source = tmp_path / "colors.mp4"
    media.run(
        [
            "-f",
            "lavfi",
            "-i",
            "color=red:s=160x284:r=24:d=1",
            "-f",
            "lavfi",
            "-i",
            "color=blue:s=160x284:r=24:d=1",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=2",
            "-filter_complex",
            "[0:v][1:v]concat=n=2:v=1:a=0[v]",
            "-map",
            "[v]",
            "-map",
            "2:a",
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            source,
        ]
    )
    original = source.read_bytes()
    p = setup_project(client)
    pid, sid = p["id"], p["shots"][0]["id"]
    response = client.post(
        f"/api/projects/{pid}/shots/{sid}/upload/visual",
        files={"file": ("colors.mp4", original, "video/mp4")},
    )
    assert response.status_code == 200
    p = response.json()
    cid = p["shots"][0]["candidates"][-1]["id"]
    p = client.post(
        f"/api/projects/{pid}/shots/{sid}/select", json={"candidate_id": cid}
    ).json()
    old_revision = p["workflow_status"]["edit_revision"]
    url = f"/api/projects/{pid}/shots/{sid}/candidates/{cid}/edit"
    assert client.put(url, json={"start": 1, "end": 9}).status_code == 400
    assert client.put(url, json={"start": 1.5, "end": 1}).status_code == 422
    p = client.put(url, json={"start": 1.1, "end": 1.8}).json()
    assert p["workflow_status"]["edit_revision"] != old_revision
    assert not p["shots"][0]["candidates"][-1]["stale"]
    output = tmp_path / "trim.mp4"
    duration = media.render_shot(
        source,
        output,
        {"duration": 6, "narration": ""},
        tmp_path / "trim-work",
        edit={"start": 1.1, "end": 1.8},
    )
    assert duration == pytest.approx(0.7)
    assert media.info(output)["duration"] == pytest.approx(0.7, abs=0.08)
    assert media.info(output)["audio"]
    pixel = subprocess.run(
        [
            media.ffmpeg(),
            "-v",
            "error",
            "-i",
            str(output),
            "-vf",
            "scale=1:1",
            "-frames:v",
            "1",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-",
        ],
        capture_output=True,
        check=True,
    ).stdout
    assert pixel[2] > 200 and pixel[0] < 40, "trim must start in the blue second half"
    assert source.read_bytes() == original
    assert (
        client.put(url, json={"start": 0, "end": None}).json()["workflow_status"][
            "edit_revision"
        ]
        == old_revision
    )


def mock_style_model(client, monkeypatch):
    """Exercise the real prompt/parser through a fake HTTP model; no paid calls."""
    client.put(
        "/api/settings",
        json={
            "llm_model": "test-model",
            "llm_api_key": "test-key",
            "llm_base_url": "https://example.invalid/v1",
        },
    )
    recommendation = {
        "name": "温暖都市漫画",
        "style": "现代二维动漫，柔和暖色，自然光，人物外观一致。",
        "reason": "原文以婚后情感变化为主，适合温暖而细腻的表现。",
    }
    calls = []

    def post(url, **kwargs):
        calls.append(kwargs["json"])
        prompt = kwargs["json"]["messages"][0]["content"]
        from backend.schemas import ContentBrief

        brief = ContentBrief(
            format="dialogue",
            audience="甜宠读者",
            source_notes="来自提供的梗概",
            promise="冷漠变亲近",
            opening="丈夫挽留妻子",
            payoff="丈夫主动挽留",
            cliffhanger="妻子会留下吗",
            beats=[
                {
                    "scene": "家中",
                    "action": "丈夫伸手挽留",
                    "speaker": "丈夫",
                    "line": "别走。",
                }
            ],
        ).model_dump()
        result = recommendation
        if "你是小说推文编辑" in prompt:
            result = {
                **brief,
                **(
                    {"recommended_style": recommendation}
                    if "recommended_style" in prompt
                    else {}
                ),
            }

        class Response:
            ok = True

            def json(self):
                return {"choices": [{"message": {"content": json.dumps(result)}}]}

        return Response()

    monkeypatch.setattr(providers.requests, "post", post)
    return recommendation, calls


def test_auto_style_is_recommended_with_brief_and_requires_acceptance(
    client, monkeypatch
):
    recommendation, calls = mock_style_model(client, monkeypatch)
    p = client.post(
        "/api/projects", json={"title": "甜宠", "premise": "冷淡丈夫失忆后亲近妻子"}
    ).json()
    endpoint = f"/api/projects/{p['id']}"
    assert p["style_mode"] == "auto" and p["style"] == ""
    assert not p["workflow_status"]["style_ok"]
    assert client.post(endpoint + "/plan", json={"mode": "ai"}).status_code == 400
    assert not calls
    assert client.post(endpoint + "/brief/draft").status_code == 200
    p = wait(client, p["id"])
    assert p["job"]["status"] == "done"
    assert len(calls) == 1
    assert p["style_recommendation"]["style"] == recommendation["style"]
    assert "recommended_style" not in p["workflow"]["brief"]
    assert p["style"] == ""
    p = client.post(endpoint + "/style/accept").json()
    assert p["style"] == recommendation["style"]
    assert p["workflow_status"]["style_ok"]
    assert client.post(endpoint + "/brief/draft").status_code == 200
    p = wait(client, p["id"])
    assert (
        len(calls) == 2
        and "recommended_style" not in calls[-1]["messages"][0]["content"]
    )
    assert p["style"] == recommendation["style"]


def test_personal_presets_persist_and_can_be_reused_without_a_model(client):
    created = client.post(
        "/api/style-presets", json={"name": "我的暖色", "style": " 暖色二维，柔光。 "}
    )
    assert created.status_code == 200
    preset = created.json()
    assert preset["personal"] and preset["style"] == "暖色二维，柔光。"
    path = client.app.state.studio.store.root / "style-presets.json"
    assert json.loads(path.read_text())[0]["id"] == preset["id"]
    assert preset in client.get("/api/style-presets").json()
    for title in ["第一条", "第二条"]:
        p = client.post(
            "/api/projects",
            json={
                "title": title,
                "premise": "婚后故事",
                "style_mode": "preset",
                "style_preset_id": preset["id"],
                "style": "不可信客户端覆盖",
            },
        ).json()
        assert p["style"] == preset["style"] and p["workflow_status"]["style_ok"]
    assert (
        client.post(
            "/api/style-presets", json={"name": "我的暖色", "style": "别的画风"}
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/style-presets", json={"name": "  ", "style": "画风"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/projects",
            json={
                "title": "无效",
                "premise": "故事",
                "style_mode": "custom",
                "style": "   ",
            },
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/projects",
            json={
                "title": "无效",
                "premise": "故事",
                "style_mode": "preset",
                "style_preset_id": "missing",
            },
        ).status_code
        == 400
    )


def test_recommendation_does_not_overwrite_selected_style_and_expires_with_source(
    client, monkeypatch
):
    recommendation, calls = mock_style_model(client, monkeypatch)
    p = client.post(
        "/api/projects",
        json={
            "title": "我的项目",
            "premise": "婚后故事",
            "style": "我已选定的画风",
        },
    ).json()
    assert p["style_mode"] == "custom"  # old API clients with explicit style still work
    endpoint = f"/api/projects/{p['id']}"
    client.post(endpoint + "/style/recommend")
    p = wait(client, p["id"])
    assert p["style"] == "我已选定的画风"
    assert p["style_recommendation"]["style"] == recommendation["style"]
    p = client.put(endpoint, json={**p, "premise": "改为探案故事"}).json()
    assert "style_recommendation" not in p
    assert client.post(endpoint + "/style/accept").status_code == 400
    assert len(calls) == 1


def test_style_change_invalidates_visual_review_and_existing_candidates(
    client, monkeypatch
):
    from backend.services import signature, video_prompt

    p = prepare_guided(client)
    p = approve_animatic(client, p)
    endpoint = f"/api/projects/{p['id']}"
    store = client.app.state.studio.store

    def add_candidate(current):
        shot = current["shots"][0]
        shot["candidates"].append(
            {
                "id": "style-test",
                "status": "ready",
                "provider": "seedance",
                "signature": signature(current, shot),
            }
        )
        current["workflow"]["pilot_review"] = {
            "revision": p["workflow_status"]["story_revision"],
            "artifact_id": "style-test",
        }

    store.change(p["id"], add_candidate)
    p = client.get(endpoint).json()
    assert p["workflow_status"]["pilot_ok"]
    p = client.put(
        endpoint, json={**p, "style_mode": "preset", "style_preset_id": "urban-romance"}
    ).json()
    assert p["workflow_status"]["content_ok"]
    assert (
        not p["workflow_status"]["preview_ok"] and not p["workflow_status"]["pilot_ok"]
    )
    assert not p["characters_approved"] and not any(s["approved"] for s in p["shots"])
    assert p["shots"][0]["candidates"][-1]["stale"]
    assert all(video_prompt(p, s).startswith(p["style"]) for s in p["shots"])


def test_failed_style_recommendation_keeps_project_style(client, monkeypatch):
    mock_style_model(client, monkeypatch)

    def fail(*args, **kwargs):
        raise providers.requests.ConnectionError("offline")

    monkeypatch.setattr(providers.requests, "post", fail)
    p = client.post(
        "/api/projects", json={"title": "画风", "premise": "故事", "style": "手动画风"}
    ).json()
    client.post(f"/api/projects/{p['id']}/style/recommend")
    p = wait(client, p["id"])
    assert p["job"]["status"] == "failed"
    assert p["style"] == "手动画风" and "style_recommendation" not in p
    # Presets remain usable after a model failure.
    response = client.put(
        f"/api/projects/{p['id']}",
        json={**p, "style_mode": "preset", "style_preset_id": "mystery"},
    )
    assert response.status_code == 200

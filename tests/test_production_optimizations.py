import copy

import pytest
from fastapi.testclient import TestClient
from test_studio import setup_project

from backend import economics, workflow
from backend.api import create_app
from backend.schemas import PublicationFeedback
from backend.services import signature, view
from backend.storage import uid


@pytest.fixture
def client(tmp_path):
    app = create_app(tmp_path)
    with TestClient(app, headers={"X-Drama-Client": "1"}) as client:
        yield client


def candidate(project, shot, **values):
    return {
        "id": uid(),
        "provider": "seedance",
        "status": "ready",
        "signature": signature(project, shot),
        "estimated_cost": 6,
        "task_id": "remote-task",
        "file": uid() + ".mp4",
        **values,
    }


def test_costs_include_archive_but_only_current_valid_selections(client):
    p = setup_project(client)
    first, second = p["shots"]
    chosen = candidate(p, first)
    first["candidates"] = [chosen, candidate(p, first, status="rejected")]
    first["selected"] = chosen["id"]
    second["candidates"] = [
        candidate(p, second, status="uncertain", task_id=None),
        candidate(p, second, status="failed", task_id=None, estimated_cost=9),
        candidate(p, second, provider="upload", estimated_cost=0),
    ]
    archived = candidate(p, first, estimated_cost=4)
    # A repeated archive reference is counted once, even across old versions.
    p["archived_versions"] = [{"shots": [{"candidates": [archived]}]}] * 2
    p["reserved_cost"] = 22
    before = copy.deepcopy(p)
    summary = economics.summary(p)
    assert p == before
    assert summary["estimated_video_cost"] == 22
    assert summary["selected_cost"] == 6
    assert summary["unselected_cost"] == 16
    assert summary["unsettled_tasks"] == 1
    assert summary["multiple_candidate_shots"] == 1
    assert summary["paid_attempts"] == 5
    assert summary["shots"][1]["estimated_cost"] == 6
    first["duration"] += 1
    assert economics.summary(p)["selected_cost"] == 0


def test_batch_duration_is_atomic_and_only_changes_affected_shots(client):
    p = setup_project(client)
    first, second = p["shots"]
    first["candidates"] = [candidate(p, first)]
    first["selected"] = first["candidates"][0]["id"]
    first["audio"] = "audio.wav"
    second["audio"] = "other.wav"
    client.app.state.studio.store.save(p)
    path = f"/api/projects/{p['id']}/batch-shot-duration"
    failed = client.put(path, json={"shot_ids": [first["id"], uid()], "duration": 8})
    assert failed.status_code == 400
    unchanged = client.get(f"/api/projects/{p['id']}").json()
    assert unchanged["shots"][0]["duration"] == first["duration"]
    assert unchanged["shots"][0]["approved"]
    changed = client.put(
        path, json={"shot_ids": [first["id"], first["id"]], "duration": 8}
    )
    assert changed.status_code == 200
    a, b = changed.json()["shots"]
    assert a["duration"] == 8 and not a["approved"] and a["audio"] is None
    assert a["candidates"][0]["stale"]
    assert a["selected"] == first["selected"]
    assert b["approved"] and b["audio"] == "other.wav" and b["duration"] == 2
    # Saving an unchanged value must not revoke a valid approval or audio.
    same = client.put(path, json={"shot_ids": [second["id"]], "duration": 2}).json()
    assert same["shots"][1]["approved"]
    assert same["shots"][1]["audio"] == "other.wav"
    assert (
        client.put(path, json={"shot_ids": [first["id"]], "duration": 13}).status_code
        == 422
    )
    client.app.state.studio.store.change(
        p["id"], lambda x: x.update(job={"status": "running"})
    )
    assert (
        client.put(path, json={"shot_ids": [second["id"]], "duration": 4}).status_code
        == 400
    )


def test_feedback_is_version_specific_and_preserves_editorial_revision(client):
    p = setup_project(client)
    revision = workflow.edit_revision(p)
    ids = [uid(), uid(), uid()]
    cost = economics.summary(p)
    p["exports"] = [
        {
            "id": ids[0],
            "kind": "production",
            "cost_summary": cost,
            "edit_revision": revision,
        },
        {"id": ids[1], "kind": "production", "edit_revision": revision},
        {"id": ids[2], "kind": "preview"},
    ]
    client.app.state.studio.store.save(p)
    path = f"/api/projects/{p['id']}/exports/{ids[0]}/feedback"
    response = client.put(
        path,
        json={
            "platform": "抖音",
            "views": 0,
            "revenue": 0,
            "actual_cost": 12.5,
            "notes": "开头需要更早出现冲突",
        },
    )
    assert response.status_code == 200
    updated = response.json()
    assert updated["workflow_status"]["edit_revision"] == revision
    assert updated["exports"][0]["current"]
    assert updated["exports"][0]["cost_summary"] == cost
    assert updated["exports"][0]["feedback"]["views"] == 0
    assert updated["exports"][0]["feedback"]["likes"] is None
    assert "feedback" not in updated["exports"][1]
    assert client.put(path, json={"views": -1}).status_code == 422
    assert (
        client.put(path, json={"published_url": "javascript:alert(1)"}).status_code
        == 422
    )
    assert (
        client.put(
            f"/api/projects/{p['id']}/exports/{ids[2]}/feedback", json={}
        ).status_code
        == 400
    )
    assert (
        client.put(
            f"/api/projects/{p['id']}/exports/{uid()}/feedback", json={}
        ).status_code
        == 400
    )
    # Empty values stay unknown, instead of fabricating zero views or income.
    cleared = client.put(path, json={}).json()["exports"][0]["feedback"]
    assert cleared["views"] is None and cleared["revenue"] is None
    raw = client.app.state.studio.store.read(p["id"])
    assert raw["exports"][0]["feedback"] == cleared


@pytest.mark.parametrize("field", ["actual_cost", "revenue"])
def test_feedback_rejects_nonfinite_costs(field):
    with pytest.raises(ValueError):
        PublicationFeedback.model_validate({field: float("nan")})


def test_view_does_not_persist_computed_costs(client):
    p = setup_project(client)
    assert "cost_summary" in view(p)
    raw = client.app.state.studio.store.read(p["id"])
    assert "cost_summary" not in raw

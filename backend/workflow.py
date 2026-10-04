"""Content decisions and revision-aware production gates; no model calls."""

import hashlib
import json
import re

from backend.schemas import ContentBrief


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def words(value):
    return re.sub(r"[\W_]+", "", value, flags=re.UNICODE)


def content_revision(p):
    values = [p["premise"], p.get("workflow", {}).get("brief", {})]
    if story_format(p) != "narration":
        values.append(story_format(p))
    return digest(values)


def story_format(p):
    return p.get(
        "story_format",
        p.get("workflow", {}).get("brief", {}).get("format", "narration"),
    )


def script_errors(brief, shots):
    """Check attribution and ordering as well as text, including silent beats."""
    if brief.get("format", "narration") == "narration":
        if words("".join(s["narration"] for s in shots)) != words(
            brief.get("narration", "")
        ):
            return ["分镜台词与已确认文案不一致，请统一后重新预演"]
        if any(s["narration"].strip() and s["speaker"] != "旁白" for s in shots):
            return ["旁白推文的口播说话人应为旁白"]
        return []
    beats = brief.get("beats", [])
    indices = [s.get("beat_index") for s in shots]
    if any(not isinstance(i, int) or i < 1 or i > len(beats) for i in indices):
        return ["每个分镜须关联已审核剧本的段落编号"]
    if sorted(set(indices)) != list(range(1, len(beats) + 1)) or indices != sorted(
        indices
    ):
        return ["分镜须按顺序覆盖全部剧本段落，包括无台词的反应段落"]
    errors = []
    for i, beat in enumerate(beats, 1):
        group = [s for s in shots if s["beat_index"] == i]
        if words("".join(s["narration"] for s in group)) != words(beat["line"]):
            errors.append(f"第 {i} 段台词被增删或改写，请与已审剧本保持一致")
        if any(
            s["narration"].strip() and s["speaker"] != beat["speaker"] for s in group
        ):
            errors.append(f"第 {i} 段台词说话人不符，不能将角色对白改成旁白或交给他人")
        if any(s["scene"] != beat["scene"] for s in group):
            errors.append(f"第 {i} 段场景与已审剧本不符")
    return errors


def story_revision(p):
    # Reference URL renewal alone must not invalidate an editorial decision.
    from backend.services import signature

    return digest(
        [
            content_revision(p),
            [signature(p, s) for s in p["shots"]],
            [s.get("audio") for s in p["shots"]],
        ]
    )


def edit_revision(p):
    return digest(
        [
            story_revision(p),
            [
                [s.get("selected"), c.get("edit"), c.get("subtitle_text")]
                for s in p["shots"]
                for c in s["candidates"]
                if c["id"] == s.get("selected")
            ],
        ]
    )


def brief_errors(p):
    brief = p.get("workflow", {}).get("brief", {})
    labels = {
        "audience": "目标读者",
        "source_notes": "原文依据",
        "promise": "核心反差",
        "opening": "开头",
        "payoff": "本条兑现",
        "cliffhanger": "追读问题",
    }
    errors = [
        f"请填写{label}"
        for key, label in labels.items()
        if not brief.get(key, "").strip()
    ]
    fmt = story_format(p)
    if brief.get("format", "narration") != fmt:
        errors.append("制作形式已改变，请按当前形式重新起草或填写策划")
    if fmt == "narration":
        if not brief.get("narration", "").strip():
            errors.append("请填写完整口播文案")
        if brief.get("opening") and not words(brief.get("narration", "")).startswith(
            words(brief["opening"])
        ):
            errors.append("完整口播文案须以选定开头起笔")
    else:
        beats = brief.get("beats", [])
        if not beats:
            errors.append("请填写场景、动作和角色台词组成的剧本段落")
        if not any(
            b.get("line", "").strip() and b.get("speaker") not in ("", "旁白")
            for b in beats
        ):
            errors.append("对话或混合形式至少需要一段角色对白")
        if fmt == "dialogue" and any(
            b.get("line", "").strip() and b.get("speaker") == "旁白" for b in beats
        ):
            errors.append("对话短剧通过角色台词和动作叙事；需要旁白时请选择混合形式")
    return errors


def status(p):
    w = p.get("workflow", {})
    enabled = w.get("version") == 1
    content_ok = (
        not brief_errors(p)
        and bool(w.get("content_review"))
        and w["content_review"]["revision"] == content_revision(p)
    )
    revision = story_revision(p)
    preview = next(
        (
            e
            for e in p["exports"]
            if e.get("kind") == "animatic" and e.get("story_revision") == revision
        ),
        None,
    )
    preview_ok = bool(
        preview and w.get("preview_review", {}).get("revision") == revision
    )
    pilot = w.get("pilot_review", {})
    from backend.services import candidate_matches

    pilot_ok = pilot.get("revision") == revision and any(
        c["id"] == pilot.get("artifact_id")
        and c["status"] == "ready"
        and c.get("provider") != "preview"
        and candidate_matches(p, s, c)
        for s in p["shots"]
        for c in s["candidates"]
    )
    blockers, warnings = [], []
    if not p.get("style", "").strip():
        blockers.append("请先在故事页确认统一画风")
    if enabled:
        if not content_ok:
            blockers.append("先在故事页保存并审核内容策划")
        if not p["shots"]:
            blockers.append("请先选择分镜方案")
        blockers.extend(script_errors(w.get("brief", {}), p["shots"]))
        for i, s in enumerate(p["shots"], 1):
            if any(
                not s.get(k, "").strip()
                for k in ("purpose", "start_state", "end_state")
            ):
                blockers.append(f"镜头 {i} 缺少叙事作用或起止状态")
        if not preview_ok:
            blockers.append("先在分镜页制作并观看免费预演，再记录审核结果")
    total = sum(s["duration"] for s in p["shots"])
    target = w.get("brief", {}).get("target_duration", 30)
    if enabled and total > target * 1.2:
        warnings.append(
            f"分镜共 {total} 秒，超过目标 {target} 秒的 20%，请检查是否有多余铺垫"
        )
    for i, s in enumerate(p["shots"], 1):
        if len(words(s["narration"])) / s["duration"] > 5:
            warnings.append(
                f"镜头 {i} 台词较密，建议试听后调整时长（提示值，不是质量评分）"
            )
        if i > 1 and s["scene"] == p["shots"][i - 2]["scene"]:
            previous = p["shots"][i - 2].get("end_state")
            if previous and s.get("start_state") and previous != s["start_state"]:
                warnings.append(
                    f"镜头 {i - 1} → {i} 同场景起止描述不同，请核对位置、道具和动作"
                )
    return {
        "story_format": story_format(p),
        "enabled": enabled,
        "style_ok": bool(p.get("style", "").strip()),
        "content_ok": content_ok,
        "preview_ok": preview_ok,
        "pilot_ok": bool(pilot_ok),
        "blockers": blockers,
        "warnings": warnings,
        "story_revision": revision,
        "edit_revision": edit_revision(p),
    }


def new_workflow(format="dialogue"):
    return {"version": 1, "brief": ContentBrief(format=format).model_dump()}

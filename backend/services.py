import copy
import hashlib
import json
import logging
import os
import shutil
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from backend import economics, media, providers, styles, workflow
from backend.schemas import StyleRecommendation
from backend.storage import Store, atomic_json, now, uid

log = logging.getLogger(__name__)


def get_shot(project, shot_id):
    for shot in project["shots"]:
        if shot["id"] == shot_id:
            return shot
    raise ValueError("镜头不存在")


def stable_reference_uri(value):
    """Ignore expiring HTTPS query tokens while retaining the object identity."""
    if not value:
        return value
    parsed = urlsplit(value)
    if parsed.scheme.lower() == "https" and parsed.netloc:
        return urlunsplit(("https", parsed.netloc.lower(), parsed.path, "", ""))
    return value


def signature(project, shot):
    characters = copy.deepcopy(project["characters"])
    for character in characters:
        if not character.get("voice_description"):
            character.pop("voice_description", None)
        character["reference_uri"] = stable_reference_uri(
            character.get("reference_uri", "")
        )
    data = {
        "style": project["style"],
        "characters": characters,
        "shot": {
            k: shot[k]
            for k in (
                "title",
                "scene",
                "visual",
                "narration",
                "speaker",
                "duration",
                "characters",
            )
        },
    }
    for key in ("purpose", "start_state", "end_state", "beat_index", "delivery"):
        if shot.get(key):
            data["shot"][key] = shot[key]
    return hashlib.sha256(
        json.dumps(data, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def candidate_matches(project, shot, candidate):
    """Accept legacy candidates when only a signed URL query has changed."""
    current = signature(project, shot)
    if candidate.get("signature") == current:
        return True
    snapshot = candidate.get("snapshot")
    if not snapshot:
        return False
    try:
        original = {
            "style": snapshot["style"],
            "characters": snapshot["characters"],
        }
        return signature(original, snapshot["shot"]) == current
    except (KeyError, TypeError):
        return False


def video_prompt(project, shot):
    characters = [c for c in project["characters"] if c["name"] in shot["characters"]]
    context = "；".join(f"{c['name']}：{c['appearance']}" for c in characters)
    prompt = (
        f"{project['style']}。场景：{shot['scene']}。固定角色设定：{context}。"
        f"{shot['visual']}。保持服装、面孔一致，画面中不要字幕。"
    )
    if shot.get("start_state") or shot.get("end_state"):
        prompt += (
            f"\n镜头的叙事作用：{shot.get('purpose', '')}。"
            f"开场状态：{shot.get('start_state', '')}。"
            f"结束状态：{shot.get('end_state', '')}。"
            "只完成本镜头动作，不自行添加剧情、转场、片尾或黑场。"
        )
    referenced = [
        c["name"]
        for c in characters
        if c.get("reference_uri") or c.get("reference_file")
    ]
    if referenced:
        mapping = "；".join(
            f"参考图{i + 1}对应角色{character}"
            for i, character in enumerate(referenced)
        )
        prompt += f"\n角色参考：{mapping}。严格保持参考人物的身份、五官和发型。"
    if shot["narration"]:
        speaker = next(
            (c for c in project["characters"] if c["name"] == shot["speaker"]), None
        )
        voice = (
            f"{speaker['name']}（{speaker['appearance']}）" if speaker else "画外旁白"
        )
        staging = (
            "说话人不在画面中，以画外声音表达，不要增加人物。"
            if shot["speaker"] not in shot["characters"]
            else "说话人出镜时保持中文口型同步，其他角色不要跟着说话。"
        )
        prompt += (
            f"\n原生中文配音：说话人是{voice}，准确且只说一次以下台词："
            + json.dumps(shot["narration"], ensure_ascii=False)
            + f"。在{shot['duration']}秒内自然说完，保留呼吸和停顿，不要截断。"
            "根据情境表达克制、自然的情绪，不要机械朗读或播报腔。"
            "同一角色保持相同的年龄感、音色和口音。"
            + staging
            + "对白清楚，高于背景音乐和音效。不添加其他台词、解说或人声演唱。"
        )
        if speaker and speaker.get("voice_description"):
            prompt += f"\n固定声音设定：{speaker['voice_description']}。"
        if shot.get("delivery"):
            prompt += f"\n本句表演：{shot['delivery']}。情绪说明不能作为台词念出。"
    else:
        prompt += (
            "\n原生声音：仅生成与画面同步的环境声和音效，不要对白、旁白或人声演唱。"
        )
    return prompt


def shot_reference_uris(project, shot, project_dir=None):
    """Return reference assets in character-library order for stable prompt mapping."""
    references = []
    for character in project["characters"]:
        if character["name"] not in shot["characters"]:
            continue
        if character.get("reference_uri"):
            references.append(character["reference_uri"])
        elif character.get("reference_file") and project_dir is not None:
            raise ValueError(
                f"角色“{character['name']}”只有本地参考图。Seedance API 不接受本地文件或 Base64；"
                "请先上传到对象存储，并在角色页填写公网 HTTPS 地址或 asset:// 素材 URI"
            )
    return references


def view(project):
    p = copy.deepcopy(project)
    for shot in p["shots"]:
        for c in shot["candidates"]:
            c["stale"] = not candidate_matches(p, shot, c)
    p["workflow_status"] = workflow.status(p)
    p["cost_summary"] = economics.summary(p)
    for entry in p["exports"]:
        if entry.get("edit_revision"):
            entry["current"] = (
                entry["edit_revision"] == p["workflow_status"]["edit_revision"]
            )
        elif any(
            c.get("edit")
            for s in p["shots"]
            for c in s["candidates"]
            if c["id"] == s.get("selected")
        ):
            # Pre-trimming exports contain the full clip, even with identical IDs.
            entry["current"] = False
    return p


class Studio:
    def __init__(self, root):
        self.store = Store(root)
        # Recovery must only run after obtaining exclusive ownership. Otherwise
        # opening a second server could mark the first server's live jobs failed.
        self._lease = (Path(root) / ".workbench.lock").open("a+")
        try:
            if os.name == "nt":
                import msvcrt

                self._lease.seek(0)
                self._lease.write("0")
                self._lease.flush()
                self._lease.seek(0)
                msvcrt.locking(self._lease.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._lease.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self._lease.close()
            raise RuntimeError(
                "这个作品目录已有工作台在运行，请使用已打开的服务"
            ) from exc
        self.settings_path = Path(root) / "settings.json"
        self.pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="drama")
        self.store.recover()

    def close(self):
        self.pool.shutdown(wait=True)
        self._lease.close()

    def create(self, values):
        values = self.resolve_style(values)
        p = dict(
            id=uid(),
            **values,
            created_at=now(),
            updated_at=now(),
            scripts=[],
            active_script=None,
            script_approved=False,
            characters=[],
            characters_approved=False,
            shots=[],
            exports=[],
            archived_versions=[],
            reserved_cost=0,
            job={},
            workflow=workflow.new_workflow(values.get("story_format", "dialogue")),
        )
        self.store.save(p)
        return p

    def style_presets(self):
        with self.store.lock:
            path = self.store.root / "style-presets.json"
            personal = json.loads(path.read_text("utf-8")) if path.exists() else []
            return [dict(item, personal=False) for item in styles.PRESETS] + personal

    def save_style_preset(self, values):
        with self.store.lock:
            personal = [p for p in self.style_presets() if p["personal"]]
            if any(p["name"] == values["name"] for p in self.style_presets()):
                raise ValueError("已有同名画风预设，请换一个名称")
            if len(personal) >= 100:
                raise ValueError("个人画风预设最多保存100个")
            item = dict(values, id=uid(), personal=True)
            atomic_json(self.store.root / "style-presets.json", personal + [item])
            return item

    def resolve_style(self, values):
        values = dict(values)
        if values.get("style_mode") == "preset":
            preset = next(
                (
                    p
                    for p in self.style_presets()
                    if p["id"] == values["style_preset_id"]
                ),
                None,
            )
            if not preset:
                raise ValueError("画风预设不存在，请重新选择")
            values["style"] = preset["style"]
        return values

    def update_project(self, pid, values):
        values = self.resolve_style(values)

        def update(p):
            if values["budget"] < p["reserved_cost"]:
                raise ValueError("预算不能小于已有预估消耗")
            styles.apply_style(p, values["style"])
            if values["premise"] != p["premise"]:
                p.pop("style_recommendation", None)
            if "story_format" in values and values[
                "story_format"
            ] != workflow.story_format(p):
                p["script_approved"] = False
                p["characters_approved"] = False
                for shot in p["shots"]:
                    shot["approved"] = False
            p.update(values)

        return self.store.change(pid, update, idle=True)

    def recommend_style(self, pid):
        settings = providers.load_settings(self.settings_path)
        if not settings["llm_api_key"] or not settings["llm_model"]:
            raise ValueError("请先配置文本模型，或在项目设置中直接选择画风预设")

        def work():
            p = self.store.read(pid)
            recommendation = providers.recommend_style(p["premise"], settings)
            self.store.change(
                pid,
                lambda current: self.save_style_recommendation(current, recommendation),
            )

        return self.job(pid, "正在根据原文推荐画风（文本服务）", work)

    @staticmethod
    def save_style_recommendation(p, recommendation):
        p["style_recommendation"] = {
            **StyleRecommendation.model_validate(recommendation).model_dump(),
            "source_revision": workflow.digest(p["premise"]),
        }

    def accept_style(self, pid):
        def update(p):
            recommendation = p.get("style_recommendation", {})
            if recommendation.get("source_revision") != workflow.digest(p["premise"]):
                raise ValueError("请先根据当前原文生成画风推荐")
            styles.apply_style(p, recommendation["style"])
            p.update(style_mode="auto", style_preset_id="")

        return self.store.change(pid, update, idle=True)

    def job(self, project_id, label, worker, prepare=None):
        def start(p):
            if prepare:
                prepare(p)
            p["job"] = {
                "id": uid(),
                "status": "running",
                "message": label,
                "progress": 0,
                "started_at": now(),
            }

        p = self.store.change(project_id, start, idle=True)
        try:
            self.pool.submit(self._work, project_id, worker)
        except Exception:
            self.store.change(
                project_id,
                lambda p: p["job"].update(
                    status="failed", message="任务未启动，请重试"
                ),
            )
            raise
        return p

    def _work(self, project_id, worker):
        try:
            worker()
            self.store.change(
                project_id,
                lambda p: p["job"].update(
                    status="done", progress=100, message="处理完成", finished_at=now()
                ),
            )
        except Exception as exc:  # noqa: BLE001 - background job boundary; persist failure without leaking credentials
            # Avoid leaking SDK exception strings, URLs, or credentials to the UI.
            message = (
                str(exc)
                if isinstance(exc, ValueError)
                else "处理失败，请检查服务配置、素材及磁盘空间"
            )
            log.warning("Drama job failed: %s", type(exc).__name__)
            self.store.change(
                project_id,
                lambda p: p["job"].update(
                    status="failed", message=message[:1000], finished_at=now()
                ),
            )

    def progress(self, pid, value, message):
        self.store.change(
            pid, lambda p: p["job"].update(progress=value, message=message)
        )

    def plan(self, pid, mode):
        if mode != "ai":
            raise ValueError("仅支持 AI 剧本生成，请使用导入功能添加已有剧本")
        settings = providers.load_settings(self.settings_path)
        p = self.store.read(pid)
        styles.require_style(p)
        if (
            mode == "ai"
            and p.get("workflow", {}).get("version") == 1
            and not workflow.status(p)["content_ok"]
        ):
            raise ValueError("请先完成内容策划审核，再生成分镜草案")
        if mode == "ai" and not (settings["llm_api_key"] and settings["llm_model"]):
            raise ValueError("请先配置文本模型，或导入已有剧本")

        def work():
            scripts = providers.scripts(
                p["premise"],
                p["style"],
                settings,
                brief=p.get("workflow", {}).get("brief")
                if p.get("workflow", {}).get("version") == 1
                else None,
            )

            def save(current):
                current["scripts"].extend(
                    {"id": uid(), "source": mode, "created_at": now(), "script": s}
                    for s in scripts
                )

            self.store.change(pid, save)

        return self.job(pid, "正在准备剧本方案", work)

    def draft_brief(self, pid):
        settings = providers.load_settings(self.settings_path)

        def work():
            p = self.store.read(pid)
            brief = providers.content_brief(
                p["premise"],
                settings,
                recommend_style=p.get("style_mode") == "auto" and not p["style"],
                story_format=workflow.story_format(p),
            )
            recommendation = brief.pop("recommended_style", None)

            def save(current):
                current["workflow"] = {"version": 1, "brief": brief}
                if recommendation:
                    self.save_style_recommendation(current, recommendation)

            self.store.change(pid, save)

        return self.job(pid, "正在分析原文并起草内容策划（文本服务）", work)

    def review_workflow(self, pid, request):
        def update(p):
            if p.get("workflow", {}).get("version") != 1:
                raise ValueError("请先保存内容策划，启用新流程")
            w = p["workflow"]
            revision = workflow.story_revision(p)
            if request.stage == "content":
                errors = workflow.brief_errors(p)
                if errors:
                    raise ValueError("；".join(errors))
                revision = workflow.content_revision(p)
            elif request.stage == "preview":
                entry = next(
                    (e for e in p["exports"] if e["id"] == request.artifact_id), None
                )
                if (
                    not entry
                    or entry.get("kind") != "animatic"
                    or entry.get("story_revision") != revision
                ):
                    raise ValueError(
                        "请先生成当前分镜的免费预演，旧版本不能用于本次审核"
                    )
                if not workflow.status(p)["content_ok"]:
                    raise ValueError("内容策划已变更，请先重新审核")
                errors = workflow.script_errors(w.get("brief", {}), p["shots"])
                if errors:
                    raise ValueError("；".join(errors))
            else:
                check = workflow.status(p)
                if check["blockers"]:
                    raise ValueError("；".join(check["blockers"]))
                candidate = next(
                    (
                        c
                        for s in p["shots"]
                        for c in s["candidates"]
                        if c["id"] == request.artifact_id
                        and c["status"] == "ready"
                        and candidate_matches(p, s, c)
                    ),
                    None,
                )
                if (
                    not candidate
                    or candidate["provider"] == "preview"
                    or not str(candidate.get("file", "")).endswith((".mp4", ".mov"))
                ):
                    raise ValueError(
                        "请选一个有效的视频候选作为样片，文字卡和图片不能通过样片审核"
                    )
            w[request.stage + "_review"] = {
                "revision": revision,
                "artifact_id": request.artifact_id,
                "notes": request.notes,
                "reviewed_at": now(),
            }

        return self.store.change(pid, update, idle=True)

    def select_script(self, pid, script_id):
        def change(p):
            candidate = next((s for s in p["scripts"] if s["id"] == script_id), None)
            if not candidate:
                raise ValueError("剧本方案不存在")
            if p["shots"]:
                p["archived_versions"].append(
                    {
                        "active_script": p["active_script"],
                        "characters": p["characters"],
                        "shots": p["shots"],
                        "saved_at": now(),
                    }
                )
            s = candidate["script"]
            p.update(
                active_script=script_id,
                script_approved=False,
                characters_approved=False,
                characters=copy.deepcopy(s["characters"]),
            )
            p["shots"] = [
                dict(
                    **shot,
                    id=uid(),
                    approved=False,
                    candidates=[],
                    selected=None,
                    audio=None,
                )
                for shot in s["shots"]
            ]

        return self.store.change(pid, change, idle=True)

    def approve(self, pid, stage):
        def change(p):
            styles.require_style(p)
            if not p["active_script"]:
                raise ValueError("请先选择剧本")
            if stage == "script":
                p["script_approved"] = True
            elif stage == "characters":
                if not p["script_approved"]:
                    raise ValueError("请先确认剧本")
                p["characters_approved"] = True
            elif stage == "shots":
                if not p["characters_approved"]:
                    raise ValueError("请先确认角色")
                for shot in p["shots"]:
                    shot["approved"] = True
            else:
                raise ValueError("未知审核阶段")

        return self.store.change(pid, change, idle=True)

    @staticmethod
    def ready(p, shots):
        styles.require_style(p)
        if not p["script_approved"] or not p["characters_approved"]:
            raise ValueError("请先确认剧本和角色")
        if any(not s["approved"] for s in shots):
            raise ValueError("请先确认所选分镜")

    def generate(self, pid, request):
        settings = providers.load_settings(self.settings_path)
        mode, variants = request.mode, request.variants
        video_options = (
            {"generate_audio": True} if providers.video_profile(settings) else {}
        )
        if mode == "seedance":
            if not request.confirm_paid:
                raise ValueError("请确认本次会调用付费视频服务")
            if not settings["seedance_api_key"]:
                raise ValueError("请先配置 Seedance API Key")
            if settings["estimate_per_second"] <= 0:
                raise ValueError("请先填写每秒费用预估，用于预算控制")
        ids = list(dict.fromkeys(request.shot_ids))

        def prepare(p):
            shots = [get_shot(p, sid) for sid in ids]
            self.ready(p, shots)
            if mode == "seedance" and p.get("workflow", {}).get("version") == 1:
                check = workflow.status(p)
                if check["blockers"]:
                    raise ValueError("；".join(check["blockers"]))
                if not check["pilot_ok"] and (len(ids) != 1 or variants != 1):
                    raise ValueError(
                        "样片尚未通过审核：请只选一个镜头、一个候选试做，观看后记录样片审核"
                    )
                if not check["pilot_ok"] and any(
                    c["provider"] == "seedance"
                    and c["status"] == "ready"
                    and candidate_matches(p, s, c)
                    for s in p["shots"]
                    for c in s["candidates"]
                ):
                    raise ValueError(
                        "已有待审核样片，请先观看并记录通过，或淘汰后再试做"
                    )
                used = {name for s in shots for name in s["characters"]}
                if any(
                    c["name"] in used and not c.get("reference_uri")
                    for c in p["characters"]
                ):
                    raise ValueError("请为出镜角色配置参考素材 URI，再提交付费生成")
            for shot in shots:
                if mode == "seedance":
                    providers.video_request(
                        shot["visual"],
                        shot["duration"],
                        settings,
                        reference_uris=shot_reference_uris(
                            p, shot, self.store.directory(pid)
                        ),
                    )
                if mode == "seedance" and any(
                    c["status"] in {"uncertain", "interrupted"}
                    for c in shot["candidates"]
                    if c["provider"] == "seedance"
                ):
                    raise ValueError(
                        "该镜头有结果未知的付费任务，请先继续查询或标记已核对"
                    )
            cost = (
                sum(s["duration"] for s in shots)
                * variants
                * settings["estimate_per_second"]
                if mode == "seedance"
                else 0
            )
            if p["reserved_cost"] + cost > p["budget"]:
                raise ValueError("本次预计消耗超过项目剩余预算，请减少镜头或候选数量")

        def work():
            total = len(ids) * variants
            count = 0
            for sid in ids:
                for _ in range(variants):
                    p = self.store.read(pid)
                    shot = get_shot(p, sid)
                    candidate = {
                        "id": uid(),
                        "provider": mode,
                        "status": "generating",
                        "signature": signature(p, shot),
                        "file": None,
                        "task_id": None,
                        "created_at": now(),
                        "estimated_cost": round(
                            shot["duration"] * settings["estimate_per_second"], 4
                        )
                        if mode == "seedance"
                        else 0,
                    }
                    candidate["prompt"] = video_prompt(p, shot)
                    reference_uris = (
                        shot_reference_uris(p, shot, self.store.directory(pid))
                        if mode == "seedance"
                        else []
                    )
                    # Retain the exact production inputs with each candidate.
                    candidate["snapshot"] = {
                        "shot": {
                            k: v
                            for k, v in shot.items()
                            if k not in {"candidates", "selected"}
                        },
                        "characters": copy.deepcopy(p["characters"]),
                        "style": p["style"],
                    }
                    if mode == "seedance":
                        candidate["request"] = providers.request_for_record(
                            providers.video_request(
                                candidate["prompt"],
                                shot["duration"],
                                settings,
                                reference_uris=reference_uris,
                                **video_options,
                            )
                        )
                        candidate["reference_uris"] = reference_uris
                        candidate["dialogue_requested"] = bool(
                            video_options and shot["narration"]
                        )
                        candidate["remote_base_url"] = settings["seedance_base_url"]

                    def add(current, sid=sid, candidate=candidate):
                        get_shot(current, sid)["candidates"].append(candidate)
                        current["reserved_cost"] = round(
                            current["reserved_cost"] + candidate["estimated_cost"], 4
                        )

                    self.store.change(pid, add)
                    self.progress(
                        pid,
                        int(count / total * 100),
                        f"正在制作 {count + 1}/{total}：{shot['title']}",
                    )
                    try:
                        if mode == "preview":
                            name = candidate["id"] + ".png"
                            media.storyboard(
                                shot,
                                self.store.directory(pid) / name,
                                p["shots"].index(shot) + 1,
                                len(shot["candidates"]) + 1,
                            )
                        else:
                            task_id = providers.submit_video(
                                candidate["prompt"],
                                shot["duration"],
                                settings,
                                reference_uris=reference_uris,
                                **video_options,
                            )
                            self.candidate_update(
                                pid,
                                sid,
                                candidate["id"],
                                task_id=task_id,
                                remote_base_url=settings["seedance_base_url"],
                            )
                            url = providers.wait_video(task_id, settings)
                            name = candidate["id"] + ".mp4"
                            self.progress(
                                pid,
                                int(count / total * 100),
                                f"镜头已生成，正在下载 {count + 1}/{total}：{shot['title']}",
                            )
                            providers.download(url, self.store.directory(pid) / name)
                            media.validate_media(
                                self.store.directory(pid) / name, "video"
                            )
                        self.candidate_update(
                            pid, sid, candidate["id"], status="ready", file=name
                        )
                    except Exception as exc:
                        latest = get_shot(self.store.read(pid), sid)["candidates"][-1]
                        status = (
                            "uncertain"
                            if isinstance(exc, providers.UncertainSubmission)
                            else ("interrupted" if latest.get("task_id") else "failed")
                        )

                        def fail(current, sid=sid, candidate=candidate, status=status):
                            stored = next(
                                c
                                for c in get_shot(current, sid)["candidates"]
                                if c["id"] == candidate["id"]
                            )
                            stored["status"] = status
                            # A definitive rejection before Ark returns a task ID
                            # cannot have started billable video generation.
                            if status == "failed" and not stored.get("task_id"):
                                current["reserved_cost"] = max(
                                    0,
                                    round(
                                        current["reserved_cost"]
                                        - stored["estimated_cost"],
                                        4,
                                    ),
                                )

                        self.store.change(pid, fail)
                        raise
                    count += 1

        return self.job(pid, "准备生成镜头", work, prepare)

    def candidate_update(self, pid, sid, cid, **values):
        def update(p):
            c = next(
                (c for c in get_shot(p, sid)["candidates"] if c["id"] == cid), None
            )
            if not c:
                raise ValueError("候选不存在")
            c.update(values)

        return self.store.change(pid, update)

    def resume(self, pid, sid, cid):
        settings = providers.load_settings(self.settings_path)
        p = self.store.read(pid)
        c = next((c for c in get_shot(p, sid)["candidates"] if c["id"] == cid), None)
        if not c or not c.get("task_id"):
            raise ValueError("缺少远端任务编号，请先在服务商后台核对")
        if not settings["seedance_api_key"]:
            raise ValueError("请先配置视频服务密钥")
        settings["seedance_base_url"] = c["remote_base_url"]

        def work():
            url = providers.wait_video(c["task_id"], settings)
            name = cid + ".mp4"
            self.progress(pid, 50, "已有镜头生成成功，正在下载，不会重新付费提交")
            providers.download(url, self.store.directory(pid) / name)
            media.validate_media(self.store.directory(pid) / name, "video")
            self.candidate_update(pid, sid, cid, file=name, status="ready")

        return self.job(pid, "正在查询已有远端任务，不会重新提交", work)

    def export(self, pid, request):
        def prepare(p):
            if not p["shots"]:
                raise ValueError("请先制作分镜")
            self.ready(p, p["shots"])
            if (
                request.voice
                and not shutil.which("say")
                and any(s["narration"] and not s.get("audio") for s in p["shots"])
            ):
                raise ValueError("此系统无本地配音，请逐镜头上传音轨或关闭系统配音")
            if request.kind == "animatic":
                return
            for shot in p["shots"]:
                c = next(
                    (c for c in shot["candidates"] if c["id"] == shot["selected"]), None
                )
                if not c or c["status"] != "ready" or not candidate_matches(p, shot, c):
                    raise ValueError(f"镜头「{shot['title']}」尚未选定有效候选")
                if request.kind == "production" and c["provider"] == "preview":
                    raise ValueError(
                        "正式成片不能包含文字预演卡，请替换为生成或导入的画面"
                    )

        return self.job(
            pid, "准备合成导出", lambda: self.export_work(pid, request), prepare
        )

    def export_work(self, pid, request):
        p = self.store.read(pid)
        folder = self.store.directory(pid)
        export_id = uid()
        clips, subtitles, durations, audio_sources = [], [], [], []
        animatic = request.kind == "animatic"
        selected = (
            []
            if animatic
            else [
                next(c for c in s["candidates"] if c["id"] == s["selected"])
                for s in p["shots"]
            ]
        )
        mini_only = all(
            c.get("request", {})
            .get("model", "")
            .startswith("doubao-seedance-2-0-mini-")
            for c in selected
        )
        output_size = (720, 1280) if mini_only else (1080, 1920)
        timecode = 0
        with tempfile.TemporaryDirectory(dir=folder, prefix="render-") as temp:
            for index, shot in enumerate(p["shots"]):
                self.progress(
                    pid,
                    int(index / len(p["shots"]) * 95),
                    f"正在合成镜头 {index + 1}/{len(p['shots'])}",
                )
                if animatic:
                    source = Path(temp) / f"card-{index}.png"
                    media.storyboard(shot, source, index + 1, 1)
                    c = {"provider": "preview", "file": str(source)}
                else:
                    c = next(
                        c for c in shot["candidates"] if c["id"] == shot["selected"]
                    )
                # Correct captions to the actual spoken wording without discarding
                # a usable generation or rewriting the original script.
                shot = {**shot, "narration": c.get("subtitle_text", shot["narration"])}
                if shot.get("audio"):
                    audio_source = "uploaded"
                elif request.voice and shot["narration"]:
                    audio_source = "system_speech"
                else:
                    audio_source = (
                        "native"
                        if media.info(folder / c["file"])["audio"]
                        else "silent"
                    )
                audio_sources.append(
                    {
                        "shot_id": shot["id"],
                        "source": audio_source,
                        "dialogue_requested": c.get("dialogue_requested", False),
                    }
                )
                output = Path(temp) / f"clip-{index:03d}.mp4"
                voice_name = next(
                    (
                        c["voice"]
                        for c in p["characters"]
                        if c["name"] == shot["speaker"]
                    ),
                    "Tingting",
                )
                duration = media.render_shot(
                    folder / c["file"],
                    output,
                    shot,
                    Path(temp) / str(index),
                    audio=folder / shot["audio"] if shot.get("audio") else None,
                    voice=request.voice,
                    voice_name=voice_name,
                    production=request.kind == "production",
                    output_size=output_size,
                    edit=c.get("edit"),
                )
                clips.append(output)
                durations.append(duration)
                if shot["narration"]:
                    subtitles.append(
                        f"{len(subtitles) + 1}\n{media.srt_time(timecode)} --> "
                        f"{media.srt_time(timecode + duration)}\n"
                        f"{shot['narration']}\n"
                    )
                timecode += duration
            filename = export_id + ".mp4"
            media.join(clips, folder / filename, temp)
        if not media.info(folder / filename)["video"]:
            raise ValueError("导出文件验证失败")
        (folder / (export_id + ".srt")).write_text("\n".join(subtitles), "utf-8")
        manifest = {
            "project_id": pid,
            "title": p["title"],
            "kind": request.kind,
            "created_at": now(),
            "duration": timecode,
            "resolution": "x".join(
                map(str, output_size if request.kind == "production" else (540, 960))
            ),
            "estimated_video_cost": p["reserved_cost"],
            "cost_summary": economics.summary(p),
            "characters": p["characters"],
            "shots": p["shots"],
            "shot_durations": durations,
            "export_settings": request.model_dump(),
            "audio_sources": audio_sources,
            "story_revision": workflow.story_revision(p),
            "edit_revision": workflow.edit_revision(p),
        }
        atomic_json(folder / (export_id + ".json"), manifest)
        item = {
            "id": export_id,
            "file": filename,
            "subtitle": export_id + ".srt",
            "manifest": export_id + ".json",
            "kind": request.kind,
            "duration": round(timecode, 2),
            "resolution": manifest["resolution"],
            "created_at": now(),
            "selected_candidates": []
            if animatic
            else [s["selected"] for s in p["shots"]],
            "audio_sources": audio_sources,
            "story_revision": manifest["story_revision"],
            "edit_revision": manifest["edit_revision"],
            "cost_summary": manifest["cost_summary"],
        }
        self.store.change(pid, lambda current: current["exports"].append(item))

import os
import re
import shutil
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from backend import media, providers
from backend.schemas import (
    BatchShotDuration,
    Character,
    ClipEdit,
    ContentBrief,
    ExportRequest,
    GenerateRequest,
    NewProject,
    PublicationFeedback,
    Script,
    Settings,
    Shot,
    StylePreset,
    WorkflowReview,
)
from backend.services import Studio, candidate_matches, get_shot, signature, view
from backend.storage import now, uid

ROOT = Path(__file__).resolve().parents[1]


class PlanRequest(BaseModel):
    mode: str = Field(pattern="^ai$")


class SelectRequest(BaseModel):
    candidate_id: str
    subtitle_text: str | None = Field(default=None, max_length=300)


class ReviewRequest(BaseModel):
    action: str = Field(pattern="^(reject|checked)$")


def create_app(root=None, frontend_root=None):
    studio = Studio(root or os.getenv("DRAMA_STORAGE", str(ROOT / "storage/drama")))

    @asynccontextmanager
    async def lifespan(app):
        yield
        studio.close()

    app = FastAPI(
        title="幕间 · AI漫剧工作台", docs_url=None, redoc_url=None, lifespan=lifespan
    )
    app.state.studio = studio
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["127.0.0.1", "localhost", "[::1]", "testserver"],
    )

    @app.middleware("http")
    async def local_access(request, call_next):
        origin = request.headers.get("origin")
        expected = f"{request.url.scheme}://{request.url.netloc}"
        if origin and origin != expected:
            return JSONResponse({"detail": "仅允许本机工作台访问"}, status_code=403)
        if (
            request.method not in {"GET", "HEAD", "OPTIONS"}
            and request.headers.get("x-drama-client") != "1"
        ):
            return JSONResponse({"detail": "请求缺少工作台标识"}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(ValueError)
    async def bad_input(request, exc):
        return JSONResponse({"detail": str(exc)[:1000]}, status_code=400)

    @app.exception_handler(FileNotFoundError)
    async def missing(request, exc):
        return JSONResponse({"detail": "项目或文件不存在"}, status_code=404)

    @app.exception_handler(RequestValidationError)
    async def invalid(request, exc):
        errors = [
            " / ".join(map(str, e["loc"])) + ": " + e["msg"] for e in exc.errors()
        ]
        return JSONResponse(
            {"detail": "输入无效：" + "；".join(errors)[:1000]}, status_code=422
        )

    @app.get("/api/status")
    def status():
        return {
            "settings": providers.public_settings(studio.settings_path),
            "video_models": providers.VIDEO_MODELS,
            "local_voice": bool(shutil.which("say")),
            "storage": str(studio.store.root),
            "style_presets": studio.style_presets(),
        }

    @app.get("/api/style-presets")
    def style_presets():
        return studio.style_presets()

    @app.post("/api/style-presets")
    def save_style_preset(data: StylePreset):
        return studio.save_style_preset(data.model_dump())

    @app.put("/api/settings")
    def settings(data: Settings):
        providers.save_settings(studio.settings_path, data.model_dump())
        return providers.public_settings(studio.settings_path)

    @app.get("/api/projects")
    def projects():
        return [
            {
                k: p[k]
                for k in (
                    "id",
                    "title",
                    "created_at",
                    "updated_at",
                    "budget",
                    "reserved_cost",
                )
            }
            | {"shots": len(p["shots"]), "exports": len(p["exports"])}
            for p in studio.store.list()
        ]

    @app.post("/api/projects")
    def new_project(data: NewProject):
        return view(studio.create(data.model_dump()))

    @app.get("/api/projects/{pid}")
    def project(pid: str):
        return view(studio.store.read(pid))

    @app.put("/api/projects/{pid}")
    def update_project(pid: str, data: NewProject):
        values = data.model_dump()
        if "story_format" not in data.model_fields_set:
            values.pop("story_format")
        return view(studio.update_project(pid, values))

    @app.post("/api/projects/{pid}/style/recommend")
    def recommend_style(pid: str):
        return view(studio.recommend_style(pid))

    @app.post("/api/projects/{pid}/style/accept")
    def accept_style(pid: str):
        return view(studio.accept_style(pid))

    @app.post("/api/projects/{pid}/plan")
    def plan(pid: str, data: PlanRequest):
        return view(studio.plan(pid, data.mode))

    @app.put("/api/projects/{pid}/brief")
    def save_brief(pid: str, data: ContentBrief):
        def update(p):
            p.setdefault("workflow", {})
            p["workflow"].update(version=1, brief=data.model_dump())

        return view(studio.store.change(pid, update, idle=True))

    @app.post("/api/projects/{pid}/brief/draft")
    def draft_brief(pid: str):
        return view(studio.draft_brief(pid))

    @app.post("/api/projects/{pid}/workflow/review")
    def review_workflow(pid: str, data: WorkflowReview):
        return view(studio.review_workflow(pid, data))

    @app.post("/api/projects/{pid}/scripts")
    def import_script(pid: str, data: Script):
        def update(p):
            p["scripts"].append(
                {
                    "id": uid(),
                    "source": "manual",
                    "created_at": now(),
                    "script": data.model_dump(),
                }
            )

        return view(studio.store.change(pid, update, idle=True))

    @app.post("/api/projects/{pid}/scripts/{sid}/select")
    def choose_script(pid: str, sid: str):
        return view(studio.select_script(pid, sid))

    @app.post("/api/projects/{pid}/approve/{stage}")
    def approve(pid: str, stage: str):
        return view(studio.approve(pid, stage))

    @app.put("/api/projects/{pid}/characters")
    def characters(pid: str, data: list[Character]):
        def update(p):
            if not p["active_script"]:
                raise ValueError("请先选择剧本")
            script = next(
                s["script"] for s in p["scripts"] if s["id"] == p["active_script"]
            )
            Script.model_validate(
                {
                    **script,
                    "characters": [c.model_dump() for c in data],
                    "shots": p["shots"],
                }
            )
            p["characters"] = [c.model_dump() for c in data]
            p["characters_approved"] = False
            for shot in p["shots"]:
                shot["approved"] = False

        return view(studio.store.change(pid, update, idle=True))

    @app.post("/api/projects/{pid}/characters/{index}/reference")
    def character_reference(pid: str, index: int, file: Annotated[UploadFile, File()]):
        suffix = Path(file.filename or "").suffix.lower()
        if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
            raise ValueError("角色参考图仅支持 PNG、JPG、JPEG 或 WEBP")
        with studio.store.lock:
            p = studio.store.read(pid)
            if p.get("job", {}).get("status") == "running":
                raise ValueError("请等待当前任务完成后再修改角色")
            if not 0 <= index < len(p["characters"]):
                raise ValueError("角色不存在")
            name = uid() + suffix
            path = studio.store.directory(pid) / name
            try:
                size = 0
                with path.open("wb") as dest:
                    while chunk := file.file.read(1024 * 1024):
                        size += len(chunk)
                        if size > 30 * 1024 * 1024:
                            raise ValueError("角色参考图不能超过30MB")
                        dest.write(chunk)
                with Image.open(path) as image:
                    image.verify()
                with Image.open(path) as image:
                    width, height = image.size
                ratio = width / height
                if not (300 <= width <= 6000 and 300 <= height <= 6000):
                    raise ValueError("角色参考图宽高必须在300至6000像素之间")
                if not 0.4 < ratio < 2.5:
                    raise ValueError("角色参考图宽高比必须在0.4至2.5之间")
                p["characters"][index]["reference_file"] = name
                p["characters_approved"] = False
                for shot in p["shots"]:
                    if p["characters"][index]["name"] in shot["characters"]:
                        shot["approved"] = False
                studio.store.save(p)
            except Exception:
                path.unlink(missing_ok=True)
                raise
            finally:
                file.file.close()
        return view(p)

    @app.put("/api/projects/{pid}/shots/{sid}")
    def edit_shot(pid: str, sid: str, data: Shot):
        def update(p):
            names = {c["name"] for c in p["characters"]}
            if set(data.characters) - names or (
                data.speaker not in names | {"旁白"}
                and (data.narration.strip() or data.speaker)
            ):
                raise ValueError("分镜角色或说话人未在角色库中定义")
            shot = get_shot(p, sid)
            shot.update(data.model_dump())
            shot["approved"] = False
            shot["audio"] = None

        return view(studio.store.change(pid, update, idle=True))

    @app.put("/api/projects/{pid}/batch-shot-duration")
    def batch_duration(pid: str, data: BatchShotDuration):
        def update(p):
            # Validate the entire selection before changing any shot.
            shots = [get_shot(p, sid) for sid in dict.fromkeys(data.shot_ids)]
            for shot in shots:
                if shot["duration"] != data.duration:
                    shot.update(duration=data.duration, approved=False, audio=None)

        return view(studio.store.change(pid, update, idle=True))

    @app.post("/api/projects/{pid}/shots/{sid}/select")
    def select(pid: str, sid: str, data: SelectRequest):
        def update(p):
            shot = get_shot(p, sid)
            c = next(
                (c for c in shot["candidates"] if c["id"] == data.candidate_id), None
            )
            if not c or c["status"] != "ready" or not candidate_matches(p, shot, c):
                raise ValueError("候选未完成或已经过期，请重新制作")
            if "subtitle_text" in data.model_fields_set:
                if data.subtitle_text is None:
                    c.pop("subtitle_text", None)
                else:
                    c["subtitle_text"] = data.subtitle_text
            shot["selected"] = c["id"]

        return view(studio.store.change(pid, update, idle=True))

    @app.post("/api/projects/{pid}/select-first")
    def select_first(pid: str):
        def update(p):
            for shot in p["shots"]:
                valid = [
                    c
                    for c in shot["candidates"]
                    if c["status"] == "ready" and candidate_matches(p, shot, c)
                ]
                if not any(c["id"] == shot["selected"] for c in valid) and valid:
                    shot["selected"] = valid[0]["id"]

        return view(studio.store.change(pid, update, idle=True))

    @app.post("/api/projects/{pid}/shots/{sid}/candidates/{cid}/review")
    def review(pid: str, sid: str, cid: str, data: ReviewRequest):
        def update(p):
            shot = get_shot(p, sid)
            c = next((c for c in shot["candidates"] if c["id"] == cid), None)
            if not c:
                raise ValueError("候选不存在")
            if data.action == "checked" and c["status"] not in {
                "uncertain",
                "interrupted",
            }:
                raise ValueError("仅可核对结果未知的任务")
            if data.action == "reject" and c["status"] != "ready":
                raise ValueError("请先核对未知任务的计费状态")
            c["status"] = "rejected" if data.action == "reject" else "checked"
            if shot["selected"] == cid:
                shot["selected"] = None

        return view(studio.store.change(pid, update, idle=True))

    @app.put("/api/projects/{pid}/shots/{sid}/candidates/{cid}/edit")
    def edit_clip(pid: str, sid: str, cid: str, data: ClipEdit):
        def update(p):
            shot = get_shot(p, sid)
            c = next((c for c in shot["candidates"] if c["id"] == cid), None)
            if not c or c["status"] != "ready" or not candidate_matches(p, shot, c):
                raise ValueError("请先选择有效候选")
            if not str(c.get("file", "")).endswith((".mp4", ".mov")):
                raise ValueError("入点和出点仅用于视频素材")
            duration = media.info(studio.store.directory(pid) / c["file"])["duration"]
            if data.start >= duration or (data.end is not None and data.end > duration):
                raise ValueError(f"剪辑范围超出素材时长 {duration:.2f} 秒")
            if data.start == 0 and data.end is None:
                c.pop("edit", None)
            else:
                c["edit"] = data.model_dump()

        return view(studio.store.change(pid, update, idle=True))

    @app.post("/api/projects/{pid}/generate")
    def generate(pid: str, data: GenerateRequest):
        return view(studio.generate(pid, data))

    @app.post("/api/projects/{pid}/shots/{sid}/candidates/{cid}/resume")
    def resume(pid: str, sid: str, cid: str):
        return view(studio.resume(pid, sid, cid))

    @app.delete("/api/projects/{pid}/shots/{sid}/candidates/{cid}")
    def delete_failed_candidate(pid: str, sid: str, cid: str):
        def update(p):
            shot = get_shot(p, sid)
            candidate = next(
                (item for item in shot["candidates"] if item["id"] == cid), None
            )
            if not candidate:
                raise ValueError("候选不存在")
            if (
                candidate["status"] != "failed"
                or candidate.get("task_id")
                or candidate.get("file")
                or shot.get("selected") == cid
            ):
                raise ValueError("只能删除未生成文件、没有远程任务编号的失败记录")
            shot["candidates"].remove(candidate)

        return view(studio.store.change(pid, update, idle=True))

    @app.post("/api/projects/{pid}/shots/{sid}/upload/{kind}")
    def upload(pid: str, sid: str, kind: str, file: Annotated[UploadFile, File()]):
        if kind not in {"visual", "audio"}:
            raise ValueError("未知素材类型")
        suffix = Path(file.filename or "").suffix.lower()
        allowed = (
            {".mp4", ".mov", ".png", ".jpg", ".jpeg", ".webp"}
            if kind == "visual"
            else {".mp3", ".wav", ".m4a", ".aiff"}
        )
        if suffix not in allowed:
            raise ValueError("不支持此素材格式")
        # Keep save/validation under the project lock so a simultaneous script
        # change cannot attach an upload to a different production revision.
        with studio.store.lock:
            p = studio.store.read(pid)
            if p.get("job", {}).get("status") == "running":
                raise ValueError("请等待当前任务完成后再导入素材")
            shot = get_shot(p, sid)
            name = uid() + suffix
            path = studio.store.directory(pid) / name
            try:
                size = 0
                with path.open("wb") as dest:
                    while chunk := file.file.read(1024 * 1024):
                        size += len(chunk)
                        if size > 128 * 1024 * 1024:
                            raise ValueError("单个素材不能超过128MB")
                        dest.write(chunk)
                media.validate_media(path, kind)
                if kind == "audio":
                    shot["audio"] = name
                else:
                    shot["candidates"].append(
                        {
                            "id": uid(),
                            "provider": "upload",
                            "status": "ready",
                            "signature": signature(p, shot),
                            "file": name,
                            "task_id": None,
                            "created_at": now(),
                            "estimated_cost": 0,
                            "snapshot": {
                                "shot": Shot.model_validate(shot).model_dump(),
                                "characters": p["characters"],
                                "style": p["style"],
                            },
                        }
                    )
                studio.store.save(p)
            except Exception:
                path.unlink(missing_ok=True)
                raise
            finally:
                file.file.close()
        return view(p)

    @app.post("/api/projects/{pid}/export")
    def export(pid: str, data: ExportRequest):
        return view(studio.export(pid, data))

    @app.put("/api/projects/{pid}/exports/{eid}/feedback")
    def publication_feedback(pid: str, eid: str, data: PublicationFeedback):
        def update(p):
            entry = next((e for e in p["exports"] if e["id"] == eid), None)
            if not entry or entry.get("kind") != "production":
                raise ValueError("请为正式导出版本记录发布效果")
            entry["feedback"] = {**data.model_dump(), "updated_at": now()}

        return view(studio.store.change(pid, update, idle=True))

    @app.get("/assets/{pid}/{filename}")
    def asset(pid: str, filename: str):
        if not re.fullmatch(
            r"[a-f0-9]{32}\.(mp4|mov|png|jpg|jpeg|webp|mp3|wav|m4a|aiff|srt|json)",
            filename,
        ):
            raise HTTPException(404, "文件不存在")
        path = studio.store.directory(pid) / filename
        if not path.is_file():
            raise HTTPException(404, "文件不存在")
        return FileResponse(path)

    frontend_dist = Path(frontend_root) if frontend_root else ROOT / "frontend/dist"
    if (frontend_dist / "index.html").is_file():
        app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="studio")
    else:

        @app.get("/")
        def frontend_not_built():
            return JSONResponse(
                {
                    "detail": "尚未构建 Vue 前端。请在 frontend 目录执行 npm ci 和 npm run build，然后重启工作台。"
                },
                status_code=503,
            )

    return app

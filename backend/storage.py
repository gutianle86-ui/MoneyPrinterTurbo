import json
import os
import re
import tempfile
import threading
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4


def now():
    return datetime.now(UTC).isoformat()


def uid():
    return uuid4().hex


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


class Store:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()

    def directory(self, project_id):
        if not re.fullmatch(r"[a-f0-9]{32}", project_id):
            raise ValueError("无效项目编号")
        return self.root / project_id

    def read(self, project_id):
        with self.lock:
            path = self.directory(project_id) / "project.json"
            if not path.exists():
                raise FileNotFoundError("项目不存在")
            return json.loads(path.read_text("utf-8"))

    def save(self, project):
        with self.lock:
            project["updated_at"] = now()
            atomic_json(self.directory(project["id"]) / "project.json", project)

    def change(self, project_id, fn, idle=False):
        with self.lock:
            p = self.read(project_id)
            if idle and p.get("job", {}).get("status") == "running":
                raise ValueError("当前项目正在处理，请等待完成后再修改")
            fn(p)
            self.save(p)
            return p

    def list(self):
        with self.lock:
            projects = [
                json.loads(p.read_text("utf-8"))
                for p in self.root.glob("*/project.json")
            ]
        return sorted(projects, key=lambda p: p["updated_at"], reverse=True)

    def recover(self):
        for p in self.list():
            if p.get("job", {}).get("status") == "running":
                p["job"].update(
                    status="interrupted",
                    message="服务重启，任务已中断。已完成候选仍保留；有远端编号的镜头可继续查询。",
                )
                for shot in p["shots"]:
                    for c in shot["candidates"]:
                        if c["status"] == "generating":
                            c["status"] = "interrupted"
                self.save(p)

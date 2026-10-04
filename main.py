"""Run the single-user local drama workbench: python main.py."""

import argparse

import uvicorn

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="启动本地 AI 漫剧工作台")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--reload", action="store_true", help="开发时自动重载 Python 代码")
    args = parser.parse_args()
    uvicorn.run(
        "backend.api:create_app",
        factory=True,
        host="127.0.0.1",
        port=args.port,
        workers=1,
        reload=args.reload,
    )

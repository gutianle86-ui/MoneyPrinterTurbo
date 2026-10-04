#!/bin/bash
set -e
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  echo "请先安装 Python 3.11+，然后按 README.md 创建环境。"
  read -r -p "按回车关闭…"
  exit 1
fi
echo "幕间工作台：http://127.0.0.1:8765"
echo "关闭此窗口会停止工作台。作品和候选会保留。"
exec .venv/bin/python main.py

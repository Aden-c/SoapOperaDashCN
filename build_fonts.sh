#!/bin/sh
# 重新生成全部字体并装进游戏（配置见 fonts.json）。只生成某一套：sh build_fonts.sh 按钮
cd "$(dirname "$0")"
python -X utf8 fonttool/fonttool.py build -p fonts.json "$@"

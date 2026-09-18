#!/usr/bin/env bash
# 中文口语录音转写与讲评 —— 统一入口
#
# 用法:
#   bash run.sh transcribe <音频路径> [small|medium] [输出目录]
#   bash run.sh metrics    <音频路径> [逐字稿json]
#
# 负责: Python 自动探测、Windows 原生程序路径转换(cygpath)、HF 镜像环境变量
set -euo pipefail

BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 原生 Windows 程序(curl/ffmpeg/python)不认 POSIX 路径，且部分沙箱环境禁用了
# MSYS 自动转换(MSYS2_ARG_CONV_EXCL=*) —— 统一显式转换；非 MSYS 环境原样返回。
if command -v cygpath >/dev/null 2>&1; then
  W() { cygpath -w "$1"; }
else
  W() { printf '%s' "$1"; }
fi

# Python 探测顺序: WORKBUDDY_PYTHON 环境变量 > ~/.workbuddy 托管 venv(Win/Mac) > PATH
PY="${WORKBUDDY_PYTHON:-}"
if [ -z "$PY" ]; then
  for CAND in "$HOME/.workbuddy/binaries/python/envs/default/Scripts/python.exe" \
              "$HOME/.workbuddy/binaries/python/envs/default/bin/python"; do
    if [ -f "$CAND" ]; then PY="$CAND"; break; fi
  done
fi
[ -n "$PY" ] || PY=python

# 国内网络直连 HuggingFace 的 xet 通道会 401，必须关 xet + 换镜像
export HF_ENDPOINT="${HF_ENDPOINT:-https://hf-mirror.com}"
export HF_HUB_DISABLE_XET=1
export HF_HUB_DISABLE_SYMLINKS_WARNING=1

CMD="${1:-}"
[ -n "$CMD" ] || { sed -n '2,9p' "$0" >&2; exit 1; }
shift

case "$CMD" in
  transcribe)
    [ $# -ge 1 ] || { echo "错误: transcribe 需要音频路径" >&2; exit 1; }
    AUDIO="$(W "$1")"; shift
    MODEL="${1:-medium}"
    [ $# -ge 1 ] && shift
    if [ $# -ge 1 ] && [ -n "${1:-}" ]; then
      exec "$PY" "$(W "$BASE/transcribe.py")" "$AUDIO" "$MODEL" "$(W "$1")"
    else
      exec "$PY" "$(W "$BASE/transcribe.py")" "$AUDIO" "$MODEL"
    fi
    ;;
  metrics)
    [ $# -ge 1 ] || { echo "错误: metrics 需要音频路径" >&2; exit 1; }
    AUDIO="$(W "$1")"; shift
    if [ $# -ge 1 ] && [ -n "${1:-}" ]; then
      exec "$PY" "$(W "$BASE/metrics.py")" "$AUDIO" "$(W "$1")"
    else
      exec "$PY" "$(W "$BASE/metrics.py")" "$AUDIO"
    fi
    ;;
  *)
    echo "未知子命令: $CMD（可用: transcribe | metrics）" >&2
    exit 1
    ;;
esac

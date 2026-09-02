#!/usr/bin/env bash
# B 站视频口播转写：链接/短链/BV号 → 元信息 → 音频 → Whisper 文本
# 用法: bili_transcript.sh <URL或BV号> [输出txt路径]
# 依赖: curl, ffmpeg, ffprobe, 托管 venv 中的 faster-whisper
set -euo pipefail

UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
INPUT="$1"
OUT="${2:-}"
TMP="$(dirname "${OUT:-.}")/bili_tmp_$$"   # 不用 mktemp：沙箱/安全钩子会拦系统 Temp 目录的写入与删除
mkdir -p "$TMP"
trap 'rm -rf "$TMP"' EXIT

# 原生 Windows 程序（curl/ffprobe/python）不认 POSIX 路径，且部分沙箱环境禁用了 MSYS
# 自动转换（MSYS2_ARG_CONV_EXCL=*）。统一显式转换；非 MSYS 环境原样返回。
if command -v cygpath >/dev/null 2>&1; then
  W() { cygpath -w "$1"; }
else
  W() { printf '%s' "$1"; }
fi

# 1. 提取 BV 号（支持 b23.tv 短链、完整链接、裸 BV 号）
BV=$(echo "$INPUT" | grep -oE 'BV[0-9A-Za-z]{10}' | head -1 || true)
if [ -z "$BV" ]; then
  REAL=$(curl -s -o /dev/null -w "%{url_effective}" -L -m 20 -A "$UA" "$INPUT")
  BV=$(echo "$REAL" | grep -oE 'BV[0-9A-Za-z]{10}' | head -1)
fi
[ -z "$BV" ] && { echo "错误：无法从输入中提取 BV 号" >&2; exit 1; }

# 2. 元信息（标题/UP主/时长/cid）
META=$(curl -s -m 20 -A "$UA" -H "Referer: https://www.bilibili.com/" \
  "https://api.bilibili.com/x/web-interface/view?bvid=$BV")
CID=$(echo "$META" | python -c "import json,sys; print(json.load(sys.stdin)['data']['cid'])")
echo "$META" | python -c "
import json,sys
d=json.load(sys.stdin)['data']
print('标题:',d['title']); print('UP主:',d['owner']['name']); print('时长:',d['duration'],'秒')
" >&2

# 3. 抽音频流地址并立刻下载（带 Referer，流地址有时效）
AUDIO_URL=$(curl -s -m 20 -A "$UA" -H "Referer: https://www.bilibili.com/" \
  "https://api.bilibili.com/x/player/playurl?bvid=$BV&cid=$CID&fnval=16" \
  | python -c "import json,sys; print(json.load(sys.stdin)['data']['dash']['audio'][0]['baseUrl'])")
curl -s -m 120 -A "$UA" -H "Referer: https://www.bilibili.com/" -o "$(W "$TMP/audio.m4s")" "$AUDIO_URL"
ffprobe -v error "$(W "$TMP/audio.m4s")" > /dev/null 2>&1 || { echo "错误：音频下载无效" >&2; exit 1; }

# 4. 本地 Whisper 转写（国内网络需 hf-mirror，脚本内已设）
OUT="${OUT:-bili_${BV}.txt}"
export HF_ENDPOINT=https://hf-mirror.com HF_HUB_DISABLE_XET=1
# Python 探测顺序：WORKBUDDY_PYTHON 环境变量 > ~/.workbuddy 托管 venv（Win/Mac）> PATH
PY="${WORKBUDDY_PYTHON:-}"
if [ -z "$PY" ]; then
  for CAND in "$HOME/.workbuddy/binaries/python/envs/default/Scripts/python.exe" \
              "$HOME/.workbuddy/binaries/python/envs/default/bin/python"; do
    [ -f "$CAND" ] && { PY="$CAND"; break; }
  done
fi
[ -n "$PY" ] || PY=python
"$PY" - "$(W "$TMP/audio.m4s")" "$(W "$OUT")" <<'PYEOF'
import sys
from faster_whisper import WhisperModel
model = WhisperModel("small", device="cpu", compute_type="int8")
segments, _ = model.transcribe(sys.argv[1], language="zh", vad_filter=True)
with open(sys.argv[2], "w", encoding="utf-8") as f:
    for s in segments:
        f.write(f"[{s.start:6.1f}s] {s.text.strip()}\n")
PYEOF

echo "完成: $OUT" >&2

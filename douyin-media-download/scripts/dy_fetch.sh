#!/usr/bin/env bash
# dy_fetch.sh — 抖音作品下载管线（视频 -> MP4 + 循环 GIF）
# 用法: dy_fetch.sh <抖音链接|分享口令|modal_id|作品ID> [输出根目录，默认 /d/douyinVideo]
# 产物: <输出根>/video/<作品ID>.mp4 + <输出根>/gif/<作品ID>.gif
# 依赖: curl, ffmpeg/ffprobe, Chrome (路径见下方 CHROME)
set -uo pipefail

INPUT="${1:?用法: dy_fetch.sh <链接|modal_id|作品ID> [输出根目录]}"
OUT_ROOT="${2:-${DOUYIN_OUT_ROOT:-$PWD/douyinVideo}}"

# 浏览器探测顺序：CHROME_BIN 环境变量 > Windows 常见路径 > macOS > PATH（Edge 与 Chrome 同参数兼容）
CHROME="${CHROME_BIN:-}"
if [ -z "$CHROME" ]; then
  for CAND in "/c/Program Files/Google/Chrome/Application/chrome.exe" \
              "/c/Program Files (x86)/Google/Chrome/Application/chrome.exe" \
              "$HOME/AppData/Local/Google/Chrome/Application/chrome.exe" \
              "/c/Program Files/Microsoft/Edge/Application/msedge.exe" \
              "/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe" \
              "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
              google-chrome chromium; do
    if [ -f "$CAND" ] || command -v "$CAND" >/dev/null 2>&1; then CHROME="$CAND"; break; fi
  done
fi
[ -n "$CHROME" ] || { echo "[dy] 错误：未找到 Chrome/Edge，可用 CHROME_BIN 环境变量指定路径" >&2; exit 1; }
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
# 临时目录放输出根下（不用 mktemp/%TEMP%：沙箱与安全钩子对系统 Temp 目录不可靠）
WORK="$OUT_ROOT/.tmp_$$"
mkdir -p "$WORK"
trap 'rm -rf "$WORK"' EXIT

# 原生 Windows 程序（curl/ffmpeg/ffprobe/chrome）不认 POSIX 路径，且部分沙箱环境禁用了
# MSYS 自动转换（MSYS2_ARG_CONV_EXCL=*）。统一显式转换为 Windows 路径；非 MSYS 环境原样返回。
if command -v cygpath >/dev/null 2>&1; then
  W() { cygpath -w "$1"; }
else
  W() { printf '%s' "$1"; }
fi

log() { printf '[dy] %s\n' "$*" >&2; }

# ---------- 1. 解析作品 ID ----------
ID=""
if [[ "$INPUT" =~ v\.douyin\.com/([0-9A-Za-z]+) ]]; then
  # 短链：跟随 302 拿真实 URL
  SHORT="https://v.douyin.com/${BASH_REMATCH[1]}/"
  REAL="$(curl -s -o /dev/null -w '%{redirect_url}' -m 20 -A "$UA" "$SHORT")"
  INPUT="$REAL"
  log "短链已解析 -> $REAL"
fi
if [[ "$INPUT" =~ modal_id=([0-9]+) ]]; then
  ID="${BASH_REMATCH[1]}"
elif [[ "$INPUT" =~ douyin\.com/(video|note)/([0-9]+) ]]; then
  ID="${BASH_REMATCH[2]}"
elif [[ "$INPUT" =~ ^[0-9]{15,}$ ]]; then
  ID="$INPUT"
fi
[[ -n "$ID" ]] || { log "错误：无法从输入中解析出作品 ID"; exit 1; }
log "作品 ID: $ID"

# ---------- 2. headless 渲染（curl 直抓只有空壳，此步必经）----------
log "渲染作品页..."
"$CHROME" --headless=new --disable-gpu --no-first-run \
  --user-data-dir="$(W "$WORK/cp")" --window-size=1280,1600 \
  --virtual-time-budget=15000 --timeout=30000 \
  --dump-dom "https://www.douyin.com/video/$ID" > "$WORK/dom.html" 2>/dev/null
DOM="$WORK/dom.html"
[[ -s "$DOM" ]] || { log "错误：渲染失败，DOM 为空"; exit 1; }

TITLE="$(grep -o '<title>[^<]*</title>' "$DOM" | head -1 | sed 's/<[^>]*>//g')"
log "作品: $TITLE"

# ---------- 3. 形态判别（优先级：实况图 > 图+视频 > 纯视频）----------
LIVE_N="$(grep -c 'livePhoto' "$DOM" || true)"
IMG_N="$(grep -c 'downloadUrlList\|"images"' "$DOM" || true)"
[[ "$LIVE_N" -gt 0 ]] && log "警告：检测到 livePhoto 特征（实况图），本脚本只处理视频层；图文需人工检查 $WORK/dom.html"

# ---------- 4. 按特征抽直链（不写死索引/JSON键名）----------
grep -o 'src="https://v[0-9a-z.-]*douyinvod[^"]*"' "$DOM" \
  | sed 's/^src="//; s/"$//' | sort -u > "$WORK/vurls.txt"
N_URLS="$(wc -l < "$WORK/vurls.txt")"
[[ "$N_URLS" -gt 0 ]] || { log "错误：DOM 中未找到 douyinvod 直链"; exit 1; }
log "抽到 $N_URLS 条签名直链（过期时间戳藏在 URL 中，必须立刻下载）"

# ---------- 5. 下载 + ffprobe 强制断言视频流 ----------
MP4="$(W "$WORK/$ID.mp4")"
OK=0
while IFS= read -r U; do
  curl -s -m 180 -A "$UA" -H "Referer: https://www.douyin.com/" \
    -o "$MP4" -w "code=%{http_code} size=%{size_download}\n" "$U" || continue
  if ffprobe -v error -select_streams v:0 -show_entries stream=codec_type \
       -of csv=p=0 "$MP4" 2>/dev/null | grep -q video; then
    OK=1; log "下载成功且含视频流"; break
  fi
  log "该直链无视频流（音频坑），换下一条"
done < "$WORK/vurls.txt"
[[ "$OK" -eq 1 ]] || { log "错误：全部直链均无视频流"; exit 1; }

DUR="$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$MP4")"
RES="$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=p=0 "$MP4")"
log "时长 ${DUR}s，分辨率 ${RES}"

# ---------- 6. 转 GIF（体积经验值：360px/12fps ≈ 1.4MB/秒）----------
FPS=12; W_=360
awk "BEGIN{exit !(${DUR%.*} > 8)}" && { FPS=10; W_=320; }
mkdir -p "$OUT_ROOT/video" "$OUT_ROOT/gif"
PAL="$(W "$WORK/pal.png")"
GIF="$(W "$OUT_ROOT/gif/$ID.gif")"
MP4OUT="$(W "$OUT_ROOT/video/$ID.mp4")"
ffmpeg -y -loglevel error -i "$MP4" \
  -vf "fps=$FPS,scale=$W_:-2:flags=lanczos,palettegen=stats_mode=diff" "$PAL"
ffmpeg -y -loglevel error -i "$MP4" -i "$PAL" \
  -lavfi "fps=$FPS,scale=$W_:-2:flags=lanczos [x]; [x][1:v] paletteuse=dither=bayer:bayer_scale=3" \
  -loop 0 "$GIF"

cp "$WORK/$ID.mp4" "$OUT_ROOT/video/$ID.mp4"
log "完成: $OUT_ROOT/video/$ID.mp4 + $OUT_ROOT/gif/$ID.gif"
log "$TITLE"

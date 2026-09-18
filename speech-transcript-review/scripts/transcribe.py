# -*- coding: utf-8 -*-
"""中文口语录音本地转写（faster-whisper）

用法：
    python transcribe.py <音频路径> [small|medium] [输出目录]

输出：
    <输出目录>/transcript_<model>.txt   带时间戳逐字稿
    <输出目录>/transcript_<model>.json  结构化分段（供 metrics.py 使用）

依赖：faster-whisper（已装在托管 venv），ffmpeg 在 PATH 中
"""
import os
import sys
import json

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
# Windows 无符号链接权限时会刷警告，关掉
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

from faster_whisper import WhisperModel  # noqa: E402


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    src = os.path.abspath(sys.argv[1])
    model_size = sys.argv[2] if len(sys.argv) > 2 else "medium"
    out_dir = os.path.abspath(sys.argv[3]) if len(sys.argv) > 3 else os.path.dirname(src)
    os.makedirs(out_dir, exist_ok=True)

    if not os.path.exists(src):
        raise SystemExit(f"音频不存在: {src}")

    stem = os.path.splitext(os.path.basename(src))[0]
    out_txt = os.path.join(out_dir, f"{stem}_{model_size}.txt")
    out_json = os.path.join(out_dir, f"{stem}_{model_size}.json")

    print(f"[1/3] 加载模型 {model_size} ...", flush=True)
    model = WhisperModel(model_size, device="cpu", compute_type="int8", cpu_threads=4)

    # 提示词保持精简（2~3 句即可）。过长会被当成待转写内容泄漏进输出。
    prompt = os.environ.get(
        "ASR_PROMPT",
        "以下是普通话口语录音，可能是汇报、演讲或会议发言。请用规范简体中文转写。",
    )

    print("[2/3] 转写中 ...", flush=True)
    segments, info = model.transcribe(
        src,
        language="zh",
        beam_size=5,
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=400),
        initial_prompt=prompt,
        condition_on_previous_text=False,
        word_timestamps=True,
    )

    lines, rows = [], []
    for seg in segments:
        text = seg.text.strip()
        if not text:
            continue
        m, s = divmod(int(seg.start), 60)
        stamp = f"[{m:02d}:{s:02d}]"
        lines.append(f"{stamp} {text}")
        rows.append({"start": round(seg.start, 2), "end": round(seg.end, 2), "text": text})
        print(f"{stamp} {text}", flush=True)

    with open(out_txt, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(
            {
                "source": src,
                "model": model_size,
                "duration": round(info.duration, 2),
                "language": info.language,
                "segments": rows,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    print(f"[3/3] 完成\n  {out_txt}\n  {out_json}", flush=True)


if __name__ == "__main__":
    main()

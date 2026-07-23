"""音频处理器 — DashScope fun-asr 语音识别"""
import base64
import subprocess
import tempfile
from pathlib import Path
from cleaner.state import upsert_metadata, log

BASE_DIR = Path.home() / "Documents" / "knowledge-system"
ASR_MODEL = "fun-asr-flash-2026-06-15"


def process_audio(file_hash: str, vault_path: str, conn) -> dict:
    import yaml
    from openai import OpenAI

    config = yaml.safe_load(open(Path.home() / ".hermes" / "config.yaml"))
    api_key = config["auxiliary"]["vision"]["api_key"]
    client = OpenAI(api_key=api_key, base_url="https://dashscope.aliyuncs.com/compatible-mode/v1")

    path = Path(vault_path)

    # 转为 16kHz mono WAV（DashScope 推荐格式）
    try:
        tmp = Path(tempfile.mkdtemp(prefix="audio_proc_"))
        wav_path = tmp / "audio.wav"
        subprocess.run([
            "ffmpeg", "-y", "-i", str(path),
            "-acodec", "pcm_s16le", "-ac", "1", "-ar", "16000",
            "-t", "1800",  # 最长 30 分钟
            str(wav_path),
        ], capture_output=True, timeout=120, check=True)

        with open(wav_path, "rb") as f:
            audio_b64 = base64.b64encode(f.read()).decode()
    except Exception as e:
        log(conn, file_hash, "processor", "error", f"音频转换失败: {e}")
        return None
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)

    # 调用 DashScope 语音识别
    try:
        resp = client.chat.completions.create(
            model=ASR_MODEL,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "input_audio", "input_audio": {"data": audio_b64, "format": "wav"}},
                ],
            }],
        )
        text = resp.choices[0].message.content or ""
    except Exception as e:
        log(conn, file_hash, "processor", "error", f"ASR 失败: {e}")
        return None

    if not text.strip():
        log(conn, file_hash, "processor", "skipped", "无语音内容")
        return None

    text_path = BASE_DIR / "processed" / "text" / f"{file_hash}.txt"
    text_path.write_text(text, encoding="utf-8")

    # 获取时长
    duration = 0
    try:
        result = subprocess.run([
            "ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(path),
        ], capture_output=True, text=True, timeout=10)
        import json
        duration = float(json.loads(result.stdout)["format"].get("duration", 0))
    except Exception:
        pass

    upsert_metadata(conn, file_hash, duration_sec=duration)
    log(conn, file_hash, "processor", "done", f"audio→text: {len(text)} chars")

    return {"text_path": str(text_path), "image_paths": [], "meta": {"title": path.stem, "duration_sec": duration}}

"""视频处理器 — 抽帧 + DashScope 视觉 + 阿里云 NLS 语音"""
import subprocess
import base64
import tempfile
from pathlib import Path
from cleaner.state import upsert_metadata, log

BASE_DIR = Path.home() / "Documents" / "knowledge-system"
FRAME_INTERVAL = 10  # 每 N 秒抽一帧
MAX_DURATION = 1800   # 最长处理 30 分钟


def _check_ffmpeg():
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=5)
        return True
    except Exception:
        return False


def _extract_frames(video_path: str, output_dir: Path, duration: float) -> list[Path]:
    """抽帧"""
    frames = []
    interval = max(1, int(duration / min(180, duration * 60 / FRAME_INTERVAL)))
    # 每 FRAME_INTERVAL 秒一帧
    for t in range(0, min(int(duration), MAX_DURATION), FRAME_INTERVAL):
        out = output_dir / f"frame_{t:04d}.jpg"
        subprocess.run([
            "ffmpeg", "-y", "-ss", str(t), "-i", video_path,
            "-vframes", "1", "-q:v", "2", str(out),
        ], capture_output=True, timeout=30)
        if out.exists():
            frames.append(out)
    return frames


def _extract_audio(video_path: str, output_dir: Path) -> Path:
    """提取音频"""
    audio_path = output_dir / "audio.wav"
    subprocess.run([
        "ffmpeg", "-y", "-i", video_path,
        "-vn", "-acodec", "pcm_s16le", "-ac", "1", "-ar", "16000",
        str(audio_path),
    ], capture_output=True, timeout=60)
    return audio_path if audio_path.exists() else None


def _analyze_frames(frames: list[Path]) -> str:
    """用 DashScope qwen-vl 分析帧"""
    import yaml
    from openai import OpenAI

    config = yaml.safe_load(open(Path.home() / ".hermes" / "config.yaml"))
    api_key = config["auxiliary"]["vision"]["api_key"]
    model = config.get("auxiliary", {}).get("vision", {}).get("model", "qwen-vl-max")
    client = OpenAI(api_key=api_key, base_url="https://dashscope.aliyuncs.com/compatible-mode/v1")

    descriptions = []
    for f in frames[:30]:  # 最多分析 30 帧
        with open(f, "rb") as fp:
            img_b64 = base64.b64encode(fp.read()).decode()
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}},
                {"type": "text", "text": "用一句话描述这个画面中的关键内容。"},
            ]}],
            max_tokens=100,
        )
        descriptions.append(f"  [{f.stem}] {resp.choices[0].message.content}")

    return "\n".join(descriptions)


def process_video(file_hash: str, vault_path: str, conn) -> dict:
    if not _check_ffmpeg():
        log(conn, file_hash, "processor", "error", "ffmpeg 未安装")
        return None

    # 获取时长
    result = subprocess.run([
        "ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", vault_path,
    ], capture_output=True, text=True, timeout=10)
    import json
    duration = float(json.loads(result.stdout)["format"].get("duration", 0)) if result.returncode == 0 else 0

    tmp_dir = Path(tempfile.mkdtemp(prefix="video_proc_"))

    # 抽帧 + 分析
    frames = _extract_frames(vault_path, tmp_dir, duration)
    vision_text = _analyze_frames(frames) if frames else "(未提取到帧)"

    # 提取音频
    audio_path = _extract_audio(vault_path, tmp_dir)
    speech_text = "(语音识别需配置阿里云 NLS)"  # 留待 NLS 集成

    # 合并
    text = f"""# 视频分析: {Path(vault_path).stem}
## 基本信息
- 时长: {duration:.0f}秒
- 抽帧间隔: {FRAME_INTERVAL}秒
- 分析帧数: {len(frames)}

## 视觉分析
{vision_text}

## 语音转录
{speech_text}
"""
    text_path = BASE_DIR / "processed" / "text" / f"{file_hash}.txt"
    text_path.write_text(text, encoding="utf-8")

    upsert_metadata(conn, file_hash, duration_sec=duration)
    log(conn, file_hash, "processor", "done", f"video: {len(frames)} frames, {len(text)} chars")

    # 清理
    import shutil
    shutil.rmtree(tmp_dir, ignore_errors=True)

    return {"text_path": str(text_path), "image_paths": [], "meta": {"title": Path(vault_path).stem, "duration_sec": duration}}

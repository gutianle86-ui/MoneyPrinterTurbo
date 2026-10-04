"""Deterministic storyboard cards and real FFmpeg exports; no paid calls."""

import re
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
FONT = ROOT / "resource/fonts/MicrosoftYaHeiNormal.ttc"


def ffmpeg():
    found = shutil.which("ffmpeg")
    if found:
        return found
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def run(args, timeout=180):
    result = subprocess.run(
        [ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", *map(str, args)],
        capture_output=True,
        check=False,
        timeout=timeout,
    )
    if result.returncode:
        raise ValueError("媒体处理失败，请检查素材是否可播放及磁盘空间")


def info(path):
    result = subprocess.run(
        [ffmpeg(), "-hide_banner", "-i", str(path)],
        capture_output=True,
        timeout=30,
        check=False,
    )
    report = result.stderr.decode("utf-8", errors="replace")
    match = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", report)
    duration = (
        sum(float(n) * scale for n, scale in zip(match.groups(), (3600, 60, 1)))
        if match
        else 0
    )
    dimensions = re.search(r"Video:[^\n]*?\b(\d{2,5})x(\d{2,5})\b", report)
    return {
        "video": "Video:" in report,
        "audio": "Audio:" in report,
        "duration": duration,
        "width": int(dimensions[1]) if dimensions else None,
        "height": int(dimensions[2]) if dimensions else None,
    }


def validate_media(path, kind):
    details = info(path)
    if not details["audio" if kind == "audio" else "video"]:
        raise ValueError("文件中没有可读取的音轨或画面")
    if kind == "audio":
        if not 0 < details["duration"] <= 120:
            raise ValueError("单镜头音轨必须在120秒以内")
        run(["-i", path, "-t", "0.2", "-f", "null", "-"], timeout=30)
    else:
        run(["-i", path, "-frames:v", "1", "-f", "null", "-"], timeout=30)
    return details


def font(size):
    return ImageFont.truetype(str(FONT), size)


def wrap(text, width, face):
    lines = []
    for paragraph in text.split("\n"):
        line = ""
        for character in paragraph:
            if face.getlength(line + character) > width:
                lines.append(line)
                line = character
            else:
                line += character
        lines.append(line)
    return lines


def draw_text(draw, text, xy, face, fill, width, spacing=12, max_lines=20):
    x, y = xy
    lines = wrap(text, width, face)
    for index, line in enumerate(lines[:max_lines]):
        if index == max_lines - 1 and len(lines) > max_lines:
            line = line[:-1] + "…"
        draw.text((x, y), line, font=face, fill=fill)
        y += face.size + spacing
    return y


def storyboard(shot, path, index, variant):
    palettes = [("#111b2c", "#81dec0"), ("#24192c", "#d5afff"), ("#242216", "#e3cb83")]
    bg, accent = palettes[(variant - 1) % len(palettes)]
    im = Image.new("RGB", (540, 960), bg)
    draw = ImageDraw.Draw(im)
    draw.rectangle((36, 42, 504, 46), fill=accent)
    draw.text((36, 70), f"STORYBOARD  /  {index:02d}", font=font(21), fill=accent)
    draw.text((36, 130), f"{index:02d}", font=font(100), fill=accent)
    y = draw_text(draw, shot["title"], (36, 286), font(36), "#ffffff", 468)
    y = draw_text(draw, shot["scene"], (36, y + 22), font(23), accent, 468)
    y = draw_text(draw, shot["visual"], (36, y + 40), font(25), "#c2ccda", 468, max_lines=6)
    label = f"说话人：{shot['speaker']}" if shot.get("narration") else "无台词 · 动作 / 反应"
    draw_text(draw, label, (36, min(y + 22, 720)), font(23), accent, 468, max_lines=2)
    draw.text((36, 890), "分镜预演 · 文字卡 / 非 AI 画面", font=font(20), fill=accent)
    im.save(path)


def caption(text, path):
    im = Image.new("RGBA", (540, 960), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    face = font(27)
    lines = wrap(text, 452, face)
    # Long dialogue is rendered as timed subtitle pages by render_shot.
    top = 824 - len(lines) * 40
    draw.rounded_rectangle((24, top - 14, 516, 842), radius=12, fill=(0, 0, 0, 205))
    draw_text(draw, text, (44, top), face, "#ffffff", 452, spacing=13)
    im.save(path)


def speech(text, voice, path):
    if not shutil.which("say"):
        raise ValueError("本机没有系统配音，请上传逐镜头音轨或关闭系统配音")
    try:
        result = subprocess.run(
            [
                "say",
                "-v",
                voice or "Tingting",
                "-r",
                "190",
                "-o",
                str(path),
                "--",
                text,
            ],
            capture_output=True,
            check=False,
            timeout=90,
        )
    except subprocess.TimeoutExpired as exc:
        raise ValueError("系统配音超时，请上传音轨或关闭配音") from exc
    if result.returncode:
        raise ValueError("系统音色不可用，请使用 Tingting 或上传音轨")


def render_shot(
    source,
    output,
    shot,
    work,
    audio=None,
    voice=False,
    voice_name="Tingting",
    production=False,
    output_size=None,
    edit=None,
):
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    if not audio and voice and shot["narration"]:
        audio = work / "voice.aiff"
        speech(shot["narration"], voice_name, audio)
    image_source = Path(source).suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
    source_details = (
        info(source) if not image_source else {"audio": False, "duration": 0}
    )
    # A planned shot length is a minimum, not a crop boundary. Seedance clips can
    # run longer than the storyboard estimate, and trimming them also cuts speech.
    duration = max(
        shot["duration"],
        source_details["duration"],
        info(audio)["duration"] + 0.25 if audio else 0,
    )
    if edit and not image_source:
        start = edit.get("start", 0)
        end = (
            edit.get("end")
            if edit.get("end") is not None
            else source_details["duration"]
        )
        if not 0 <= start < end <= source_details["duration"]:
            raise ValueError("剪辑范围超出素材时长")
        duration = end - start
        if audio and info(audio)["duration"] > duration:
            raise ValueError("剪辑片段短于配音，请延长出点或缩短音轨后再合成")
    native_audio = not audio and source_details["audio"]
    width, height = (output_size or (1080, 1920)) if production else (540, 960)
    args = ["-loop", "1", "-framerate", "24"] if image_source else []
    if edit and not image_source:
        args += ["-ss", str(edit.get("start", 0))]
    args += ["-i", source]
    if audio:
        args += ["-i", audio]
    elif not native_audio:
        args += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
    audio_index = 0 if native_audio else 1
    overlay_index = 1 if native_audio else 2
    filters = [
        f"[0:v]scale={width}:{height}:force_original_aspect_ratio=decrease:flags=lanczos,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=24,tpad=stop_mode=clone:stop_duration=120[base]"
    ]
    current = "base"
    lines = wrap(shot["narration"], 452, font(27)) if shot["narration"] else []
    pages = ["\n".join(lines[i : i + 2]) for i in range(0, len(lines), 2)]
    for i, page in enumerate(pages):
        overlay = work / f"caption-{i}.png"
        caption(page, overlay)
        args += ["-loop", "1", "-framerate", "24", "-i", overlay]
        start, end = i * duration / len(pages), (i + 1) * duration / len(pages)
        next_name = f"cap{i}"
        filters.append(f"[{i + overlay_index}:v]scale={width}:{height}[sub{i}]")
        filters.append(
            f"[{current}][sub{i}]overlay=0:0:enable='gte(t,{start:.3f})*lt(t,{end:.3f})'[{next_name}]"
        )
        current = next_name
    filters.append(f"[{audio_index}:a]apad,aresample=48000[a]")
    args += [
        "-filter_complex",
        ";".join(filters),
        "-map",
        f"[{current}]",
        "-map",
        "[a]",
        "-t",
        f"{duration:.3f}",
        "-c:v",
        "libx264",
        "-preset",
        "medium" if production else "ultrafast",
        "-crf",
        "17" if production else "23",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "256k" if production else "128k",
        "-ac",
        "2",
        "-ar",
        "48000",
        "-movflags",
        "+faststart",
        "-threads",
        "2",
        output,
    ]
    run(args)
    return duration


def join(clips, output, work):
    # Only internally generated filenames enter the concat manifest.
    manifest = Path(work) / "concat.txt"
    manifest.write_text("\n".join(f"file '{Path(c).name}'" for c in clips), "utf-8")
    run(
        [
            "-f",
            "concat",
            "-safe",
            "1",
            "-i",
            manifest,
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            output,
        ]
    )


def srt_time(seconds):
    millis = round(seconds * 1000)
    hours, millis = divmod(millis, 3600000)
    minutes, millis = divmod(millis, 60000)
    seconds, millis = divmod(millis, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{millis:03}"

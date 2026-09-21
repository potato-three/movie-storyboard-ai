"""Small, bounded preview payloads; original exported frames are never resized."""
import base64
import io
import json
import os
from functools import lru_cache

from PIL import Image, ImageOps


@lru_cache(maxsize=24)
def _thumbnail(path, mtime_ns, size):
    with Image.open(path) as source:
        image = ImageOps.exif_transpose(source).convert("RGB")
        image.thumbnail((960, 640), Image.Resampling.LANCZOS)
        stream = io.BytesIO()
        image.save(stream, "JPEG", quality=82)
    return "data:image/jpeg;base64," + base64.b64encode(stream.getvalue()).decode("ascii")


def preview_payload(shot, view="关键帧", automatic=False):
    path = shot.get("motion") if view == "运动图" else shot.get("keyframe")
    path = path or shot.get("keyframe")
    try:
        stat = os.stat(path)
        src = _thumbnail(path, stat.st_mtime_ns, stat.st_size)
    except (OSError, ValueError, TypeError):
        # A missing/broken preview must not abort extraction or clear the last image.
        return json.dumps({"error": "这一镜预览暂不可用，保留上一张画面。"}, ensure_ascii=False)
    caption = (
        f"当前预览：镜头 {shot['no']} · {view}　"
        f"{shot['start_tc']} → {shot['end_tc']}　时长 {shot['duration']} 秒\n"
        f"机位：{shot.get('camera') or '—'}　｜　"
        f"主体：{shot.get('subject') or '—'}（强度 {shot.get('level') or '—'}）"
    )
    return json.dumps({
        "id": f"{shot['run_id']}:{shot['no']}:{view}",
        "run": shot["run_id"], "no": shot["no"], "src": src,
        "caption": caption, "automatic": automatic,
    }, ensure_ascii=False)

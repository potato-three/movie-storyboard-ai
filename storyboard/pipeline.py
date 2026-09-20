# -*- coding: utf-8 -*-
"""
pipeline.py —— 统一编排
========================
检测镜头 -> 逐镜头提取关键帧 + 运动分析 -> 导出 CSV/MD/HTML/信息。
app.py（网页）与 main.py（命令行）都调用本模块，保证两条入口结果一致。

run_pipeline 是一个「生成器」，会依次 yield：
  ("status", 文字, 总进度0~1)
  ("shot",   当前i, 总数n, shot字典, 总进度0~1)   # 每处理完一个镜头
  ("done",   结果字典)
progress: 可选回调 progress(frac, 描述)，用于网页按钮上的进度条。
"""

import os
import re
import cv2
import datetime

from scenedetect import open_video

from storyboard import config as C
from storyboard.detector import detect_shots, safe_imwrite, close_video
from storyboard.motion import analyze_shot_motion
from storyboard.exporter import (
    export_csv, export_markdown, export_html, export_info_txt,
)

VERSION = "v0.2"


def safe_stem(path: str) -> str:
    """从路径取影片名并清洗成合法文件夹名。"""
    name = os.path.splitext(os.path.basename(path))[0]
    name = re.sub(r'[\\/:*?"<>|]+', "_", name).strip().strip(".")
    if len(name) > 60:
        name = name[:60].rstrip()
    return name or "video"


def make_out_dir(video_path: str, now=None) -> str:
    """分镜结果\\影片名_分镜结果_YYYYMMDD_HHMM\\"""
    stem = safe_stem(video_path)
    ts = (now or datetime.datetime.now()).strftime("%Y%m%d_%H%M")
    out_dir = os.path.join(C.RESULT_DIR, f"{stem}_分镜结果_{ts}")
    os.makedirs(os.path.join(out_dir, C.FRAMES_DIRNAME), exist_ok=True)
    os.makedirs(os.path.join(out_dir, C.MOTION_DIRNAME), exist_ok=True)
    return out_dir


def _cleanup_empty(d: str):
    """失败时删除本次新建的结果目录（含半成品文件）。"""
    try:
        for root, dirs, files in os.walk(d, topdown=False):
            for f in files:
                try:
                    os.remove(os.path.join(root, f))
                except Exception:
                    pass
            for dd in dirs:
                try:
                    os.rmdir(os.path.join(root, dd))
                except Exception:
                    pass
        os.rmdir(d)
    except Exception:
        pass


def run_pipeline(video_path: str, threshold: float = 27, mode: str = "平衡",
                 do_motion: bool = True, progress=None):
    def p(frac, desc):
        if progress is not None:
            try:
                progress(frac, desc)
            except Exception:
                pass

    if not video_path or not os.path.exists(video_path):
        raise FileNotFoundError(f"找不到视频文件: {video_path}")

    mp = C.MODES.get(mode, C.MODES[C.DEFAULT_MODE])
    frame_skip, mw, ms = mp["frame_skip"], mp["motion_width"], mp["motion_samples"]

    out_dir = make_out_dir(video_path)
    frames_dir = os.path.join(out_dir, C.FRAMES_DIRNAME)
    motion_dir = os.path.join(out_dir, C.MOTION_DIRNAME)
    video = None

    try:
        # ① 检测镜头（必须扫完全片才有边界，进度通过 progress 回调推送）
        yield ("status", "① 正在扫描全片、切分镜头（这一步决定镜头总数）…", 0.02)
        shots, fps, total_frames = detect_shots(
            video_path, threshold=threshold, frame_skip=frame_skip,
            progress=lambda f: p(0.02 + 0.45 * f, f"① 扫描切镜头 {int(f * 100)}%"),
        )

        n = len(shots)
        yield ("status", f"② 检测到 {n} 个镜头，开始逐镜头提取关键帧与运动分析…", 0.50)

        # ② 逐镜头：关键帧 + 运动（单句柄，按时间顺序 seek）
        video = open_video(video_path)
        cap = video.capture
        for i, shot in enumerate(shots):
            no = shot["shot_no"]
            mid = shot["mid_frame"]
            cap.set(cv2.CAP_PROP_POS_FRAMES, mid)
            ok, frame = cap.read()
            if not ok or frame is None:
                cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, mid - 1))
                ok, frame = cap.read()

            if ok and frame is not None:
                kf_path = os.path.join(frames_dir, f"shot_{no:04d}.jpg")
                safe_imwrite(kf_path, frame)
                shot["keyframe"] = kf_path
                base = frame
            else:
                shot["keyframe"] = ""
                base = None

            mo_path = os.path.join(motion_dir, f"shot_{no:04d}_motion.jpg")
            if do_motion and base is not None:
                mres = analyze_shot_motion(
                    cap, fps, shot, base, mo_path,
                    work_width=mw, n_samples=ms)
                shot.update(mres)
            else:
                shot.update({"camera_motion": "", "subject_motion": "",
                             "motion_level": "", "motion_image": ""})

            frac = 0.50 + 0.45 * (i + 1) / n
            p(frac, f"② 处理镜头 {i + 1}/{n}")
            yield ("shot", i + 1, n, shot, frac)

        # ③ 导出
        yield ("status", "③ 正在生成分镜表（CSV / Markdown / HTML）…", 0.97)
        stem = safe_stem(video_path)
        csv_p = export_csv(shots, os.path.join(out_dir, C.CSV_NAME))
        md_p = export_markdown(shots, os.path.join(out_dir, C.MD_NAME), stem)
        meta = dict(
            video_name=stem, video_path=video_path,
            created_at=datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            version=VERSION, threshold=threshold, mode=mode,
            frame_skip=frame_skip, motion_width=mw, motion_samples=ms,
            shot_count=n, fps=round(fps, 2),
            total_duration=round(sum(s["duration"] for s in shots), 2),
        )
        html_p = export_html(shots, os.path.join(out_dir, C.HTML_NAME), stem, meta)
        info_p = export_info_txt(meta, os.path.join(out_dir, C.INFO_NAME))
        p(1.0, "完成")

        yield ("done", dict(
            out_dir=out_dir, shots=shots, fps=fps, total_frames=total_frames,
            files=dict(csv=csv_p, md=md_p, html=html_p, info=info_p),
            frames_dir=frames_dir, motion_dir=motion_dir, meta=meta,
        ))

    except Exception:
        if video is not None:
            close_video(video)
            video = None
        _cleanup_empty(out_dir)
        raise
    finally:
        if video is not None:
            close_video(video)

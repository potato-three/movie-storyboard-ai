# -*- coding: utf-8 -*-
"""
detector.py —— 分镜检测核心
============================
1. 用 PySceneDetect 检测镜头切换点（支持隔帧扫描 frame_skip 与进度回调）
2. 时间码、中文路径安全写图等通用工具

关键帧与运动分析的逐镜头处理放在 pipeline.py，本模块只负责检测与基础工具。
"""

import os
import cv2
from scenedetect import open_video, FrameTimecode, SceneManager
from scenedetect.detectors import ContentDetector
from scenedetect.video_stream import VideoOpenFailure


# ---------- 通用工具 ----------

def format_timecode(seconds: float) -> str:
    """秒 -> HH:MM:SS.mmm 标准时间码。"""
    if seconds is None:
        return "00:00:00.000"
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    if millis == 1000:
        millis = 0
        secs += 1
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def safe_imwrite(path: str, frame, jpeg_quality: int = 92) -> bool:
    """中文路径安全保存图片（cv2.imwrite 不支持中文路径，用 imencode+tofile 中转）。"""
    ext = os.path.splitext(path)[1]
    params = []
    if ext.lower() in (".jpg", ".jpeg"):
        params = [int(cv2.IMWRITE_JPEG_QUALITY), int(jpeg_quality)]
    ok, buf = cv2.imencode(ext, frame, params)
    if ok:
        buf.tofile(path)
    return bool(ok)


def read_image_cn(path: str):
    """中文路径安全读取图片，返回 BGR ndarray；失败返回 None。"""
    try:
        data = np_fromfile(path)
        return cv2.imdecode(data, cv2.IMREAD_COLOR)
    except Exception:
        return None


def np_fromfile(path: str):
    import numpy as np
    return np.fromfile(path, dtype=np.uint8)


def close_video(video) -> None:
    """释放 open_video 返回对象底层的视频句柄（避免文件被占用）。"""
    cap = getattr(video, "capture", None)
    if cap is not None and hasattr(cap, "release"):
        try:
            cap.release()
        except Exception:
            pass


def _make_shot(no: int, sf: int, ef: int, fps: float) -> dict:
    ss, es = sf / fps, ef / fps
    return {
        "shot_no": no,
        "start_frame": int(sf),
        "end_frame": int(ef),
        "mid_frame": int((sf + ef) // 2),
        "start": round(ss, 3),
        "end": round(es, 3),
        "duration": round(es - ss, 3),
        "start_tc": format_timecode(ss),
        "end_tc": format_timecode(es),
    }


# ---------- 镜头检测 ----------

def detect_shots(video_path: str, threshold: float = 27.0,
                 frame_skip: int = 0, min_scene_len: int = 15,
                 progress=None):
    """
    检测视频中的所有镜头。

    参数:
        video_path: 视频文件路径（支持中文路径）
        threshold:  切换灵敏度，越小切得越多（动作/动画 20~25，长镜头 30~40）
        frame_skip: 隔帧扫描，0=逐帧（精确），1=隔1帧（平衡，约快一倍），2=更快
        min_scene_len: 最短镜头帧数，避免碎切
        progress:   可选回调 progress(frac: 0~1)

    返回: (shots, fps, total_frames)
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"找不到视频文件: {video_path}")

    # 0. 预检：能否打开、能否读到画面、取帧率/总帧数
    try:
        probe = open_video(video_path)
    except VideoOpenFailure:
        raise ValueError(
            "无法读取该视频文件。可能原因：\n"
            "1) 视频编码不受支持（可用 HandBrake / 格式工厂转成 H.264 的 MP4）；\n"
            "2) 文件已损坏，或是受 DRM 版权保护的加密影片；\n"
            "3) 扩展名与真实格式不符。"
        )
    fps = float(probe.frame_rate or 25.0)
    total_frames = probe.duration.frame_num if probe.duration else 0
    first = probe.read()
    close_video(probe)
    if first is None:
        raise ValueError("视频能打开但读不到任何画面，文件可能已损坏或编码不受支持。")

    # 1. 重新打开做场景检测（预检时读过一帧，从句柄干净开始）
    video = open_video(video_path)
    scene_manager = SceneManager()
    scene_manager.add_detector(
        ContentDetector(threshold=float(threshold), min_scene_len=min_scene_len)
    )

    def _on_frame(_frame, tc):
        if progress is not None and total_frames:
            try:
                progress(min(1.0, max(0.0, tc.frame_num / float(total_frames))))
            except Exception:
                pass

    scene_manager.detect_scenes(
        video, frame_skip=int(frame_skip), callback=_on_frame
    )
    scenes = scene_manager.get_scene_list()
    close_video(video)

    # 2. 整片无切换（长镜头）兜底
    if not scenes:
        duration = total_frames / fps if fps else 0.0
        return [_make_shot(1, 0, max(total_frames - 1, 0), fps)], fps, total_frames

    # 3. 整理镜头
    shots = []
    for i, (start_tc, end_tc) in enumerate(scenes, start=1):
        shots.append(_make_shot(i, start_tc.frame_num, end_tc.frame_num, fps))
    return shots, fps, total_frames

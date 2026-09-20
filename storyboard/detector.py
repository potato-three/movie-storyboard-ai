# -*- coding: utf-8 -*-
"""
detector.py
============
分镜提取核心模块：
1. 用 PySceneDetect 自动检测视频中的镜头切换点
2. 用 OpenCV 为每个镜头提取一张代表性关键帧（取镜头中间帧）

作者：你的名字
"""

import os
import cv2
import numpy as np
from scenedetect import open_video, SceneManager
from scenedetect.detectors import ContentDetector


# ---------- 工具函数 ----------

def format_timecode(seconds: float) -> str:
    """把秒数格式化成 HH:MM:SS.mmm 的标准时间码。"""
    if seconds is None:
        return "00:00:00.000"
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    if millis == 1000:  # 四舍五入进位保护
        millis = 0
        secs += 1
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def safe_imwrite(path: str, frame) -> bool:
    """
    安全保存图片，兼容 Windows 中文路径。
    （cv2.imwrite 直接写中文路径会失败，必须用 imencode 中转）
    """
    ext = os.path.splitext(path)[1]
    ok, buf = cv2.imencode(ext, frame)
    if ok:
        buf.tofile(path)
    return ok


# ---------- 核心：镜头检测 ----------

def detect_shots(video_path: str, threshold: float = 27.0):
    """
    检测视频中的所有镜头。

    参数:
        video_path: 视频文件路径
        threshold:  镜头切换灵敏度，范围 1~100。
                    数值越小越敏感（切出的镜头越多），默认 27。
                    动作片/快剪建议 20~25，文艺片/长镜头建议 30~40。

    返回:
        shots: 镜头信息列表，每个元素是一个字典:
               shot_no(镜号), start(秒), end(秒), duration(秒),
               start_tc / end_tc(时间码), mid_frame(中间帧帧号)
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"找不到视频文件: {video_path}")

    # 0. 预检：视频能否被 OpenCV/FFmpeg 解码（不依赖浏览器能否播放）
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        cap.release()
        raise ValueError(
            "无法读取该视频文件。可能原因：\n"
            "1) 视频编码不受支持（可用 HandBrake / 格式工厂转成 H.264 编码的 MP4 再试）；\n"
            "2) 文件已损坏，或是受 DRM 版权保护的加密影片；\n"
            "3) 文件扩展名与真实格式不符。"
        )
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    can_read, _ = cap.read()
    cap.release()
    if not can_read:
        raise ValueError("视频能打开但读不到任何画面，文件可能已损坏或编码不受支持。")

    # 1. 用 PySceneDetect 检测场景
    video = open_video(video_path)
    scene_manager = SceneManager()
    scene_manager.add_detector(ContentDetector(threshold=threshold))
    scene_manager.detect_scenes(video)
    scenes = scene_manager.get_scene_list()

    # 2. 若一个切换点都没检测到（整片长镜头），兜底把整片作为一个镜头
    if not scenes:
        duration = total_frames / fps if fps else 0.0
        return [{
            "shot_no": 1,
            "start": 0.0,
            "end": round(duration, 3),
            "duration": round(duration, 3),
            "start_tc": format_timecode(0.0),
            "end_tc": format_timecode(duration),
            "mid_frame": total_frames // 2 if total_frames else 0,
        }], fps, total_frames

    # 3. 整理成镜头列表
    shots = []
    for i, (start_tc, end_tc) in enumerate(scenes, start=1):
        start_sec = start_tc.get_seconds()
        end_sec = end_tc.get_seconds()
        start_frame = start_tc.get_frames()
        end_frame = end_tc.get_frames()
        mid_frame = int((start_frame + end_frame) / 2)

        shots.append({
            "shot_no": i,
            "start": round(start_sec, 3),
            "end": round(end_sec, 3),
            "duration": round(end_sec - start_sec, 3),
            "start_tc": format_timecode(start_sec),
            "end_tc": format_timecode(end_sec),
            "mid_frame": mid_frame,
        })

    return shots, fps, total_frames


# ---------- 关键帧提取 ----------

def extract_keyframes(video_path: str, shots, out_dir: str, prefix: str = "shot"):
    """
    为每个镜头提取中间帧作为关键帧，保存到 out_dir。

    返回: 传入的 shots 列表（原地补充了 keyframe 字段，值为图片路径）
    """
    os.makedirs(out_dir, exist_ok=True)
    cap = cv2.VideoCapture(video_path)

    for shot in shots:
        cap.set(cv2.CAP_PROP_POS_FRAMES, shot["mid_frame"])
        ret, frame = cap.read()

        if not ret or frame is None:
            # 中间帧读取失败时，退回尝试镜头起始帧
            cap.set(cv2.CAP_PROP_POS_FRAMES, shot["mid_frame"] - 1)
            ret, frame = cap.read()

        if ret and frame is not None:
            filename = f"{prefix}_{shot['shot_no']:03d}.jpg"
            out_path = os.path.join(out_dir, filename)
            safe_imwrite(out_path, frame)
            shot["keyframe"] = out_path
        else:
            shot["keyframe"] = ""

    cap.release()
    return shots

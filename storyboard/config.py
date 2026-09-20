# -*- coding: utf-8 -*-
"""
config.py —— 集中管理路径与运行模式
====================================
app.py（网页）和 main.py（命令行）共用，确保无论从哪里启动，
原始视频、分镜结果、临时缓存都固定在本项目（F 盘）内，不散落 C 盘。
"""

import os

# 项目根目录 = 本文件所在目录的上一级（storyboard/ 的父目录）
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 两个职责单一的中文数据文件夹
RAW_VIDEO_DIR = os.path.join(PROJECT_ROOT, "原始视频")   # 原始数据：放原片
RESULT_DIR = os.path.join(PROJECT_ROOT, "分镜结果")     # 成品：每次提取一个子文件夹
GRADIO_TMP_DIR = os.path.join(PROJECT_ROOT, ".gradio_tmp")  # 网页上传/运行缓存

for _d in (RAW_VIDEO_DIR, RESULT_DIR, GRADIO_TMP_DIR):
    os.makedirs(_d, exist_ok=True)

# 结果子文件夹 / 文件名（统一中文命名）
FRAMES_DIRNAME = "关键帧"
MOTION_DIRNAME = "运动图"
CSV_NAME = "分镜表.csv"
MD_NAME = "分镜表.md"
HTML_NAME = "分镜表.html"
INFO_NAME = "提取信息.txt"

# 三档运行模式：
#   frame_skip    隔帧扫描（0=逐帧；1=隔1帧，约快一倍；2=隔2帧）
#   motion_width  光流工作宽度（越小越快，只影响微观细节，不影响大方向）
#   motion_samples 每个镜头采样多少帧算运动
MODES = {
    "精确": {"frame_skip": 0, "motion_width": 640, "motion_samples": 16},
    "平衡": {"frame_skip": 1, "motion_width": 480, "motion_samples": 12},
    "快速": {"frame_skip": 2, "motion_width": 360, "motion_samples": 8},
}
DEFAULT_MODE = "平衡"

VIDEO_EXTS = (
    ".mp4", ".mkv", ".mov", ".avi", ".wmv", ".flv", ".webm",
    ".m4v", ".ts", ".mpg", ".mpeg", ".3gp",
)


def list_raw_videos():
    """列出『原始视频』文件夹里的视频文件名（供网页下拉选择）。"""
    if not os.path.isdir(RAW_VIDEO_DIR):
        return []
    return sorted(
        f for f in os.listdir(RAW_VIDEO_DIR)
        if f.lower().endswith(VIDEO_EXTS)
    )


def raw_video_path(filename):
    """把下拉选中的文件名拼成绝对路径。"""
    return os.path.join(RAW_VIDEO_DIR, filename)

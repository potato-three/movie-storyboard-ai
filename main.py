# -*- coding: utf-8 -*-
"""
main.py —— 分镜提取命令行入口
================================

最简单的用法：
    1. 把一个视频文件放进 input/ 文件夹
    2. 运行：python main.py
    3. 结果在 output/ 文件夹里（关键帧 + CSV + Markdown + HTML）

指定视频：
    python main.py "C:\路径\到\你的电影.mp4"

调整灵敏度（数值越小切出的镜头越多）：
    python main.py input/test.mp4 --threshold 22
"""

import os
import sys
import argparse
from datetime import datetime

from storyboard import (
    detect_shots,
    extract_keyframes,
    export_csv,
    export_markdown,
    export_html,
)

# 支持的视频格式
VIDEO_EXTS = (".mp4", ".mkv", ".mov", ".avi", ".flv", ".wmv", ".webm", ".m4v")


def find_default_video(input_dir: str):
    """如果用户没指定视频，自动从 input/ 里找第一个视频。"""
    if not os.path.isdir(input_dir):
        return None
    for name in sorted(os.listdir(input_dir)):
        if name.lower().endswith(VIDEO_EXTS):
            return os.path.join(input_dir, name)
    return None


def run(video_path: str, threshold: float = 27.0, output_root: str = "output"):
    """完整流水线：检测镜头 → 提取关键帧 → 导出三种分镜表。"""
    video_path = os.path.abspath(video_path)
    video_name = os.path.splitext(os.path.basename(video_path))[0]

    # 每次运行单独建一个结果文件夹，避免覆盖
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = os.path.abspath(os.path.join(output_root, f"{video_name}_{stamp}"))
    frames_dir = os.path.join(out_dir, "frames")
    os.makedirs(frames_dir, exist_ok=True)

    print("=" * 56)
    print(f"  电影分镜提取工具")
    print(f"  视频：{video_name}")
    print(f"  灵敏度阈值：{threshold}")
    print("=" * 56)

    # 第 1 步：检测镜头
    print("\n[1/3] 正在检测镜头切换，请稍候（视频越长越久）...")
    shots, fps, total_frames = detect_shots(video_path, threshold=threshold)
    print(f"      视频帧率 {fps:.2f} fps，共 {total_frames} 帧")
    print(f"      ✓ 检测到 {len(shots)} 个镜头")

    if not shots:
        print("\n⚠ 没有检测到任何镜头，请检查视频文件是否正常。")
        return None

    # 第 2 步：提取关键帧
    print("\n[2/3] 正在提取每个镜头的关键帧...")
    shots = extract_keyframes(video_path, shots, frames_dir)
    print(f"      ✓ 关键帧已保存到 frames/ 文件夹")

    # 第 3 步：导出分镜表
    print("\n[3/3] 正在导出分镜表...")
    csv_path = export_csv(shots, os.path.join(out_dir, "storyboard.csv"))
    md_path = export_markdown(shots, os.path.join(out_dir, "storyboard.md"), video_name)
    html_path = export_html(shots, os.path.join(out_dir, "storyboard.html"), video_name)
    print(f"      ✓ CSV：     {csv_path}")
    print(f"      ✓ Markdown：{md_path}")
    print(f"      ✓ HTML：    {html_path}")

    print("\n" + "=" * 56)
    print(f"  全部完成！用浏览器打开这个文件看图文版分镜表：")
    print(f"  {html_path}")
    print("=" * 56)
    return out_dir


def main():
    parser = argparse.ArgumentParser(description="电影分镜提取小工具")
    parser.add_argument("video", nargs="?", default=None,
                        help="视频文件路径（不填则自动处理 input/ 里的第一个视频）")
    parser.add_argument("--threshold", "-t", type=float, default=27.0,
                        help="镜头切换灵敏度 1~100，越小越敏感（默认 27）")
    parser.add_argument("--output", "-o", default="output",
                        help="结果输出目录（默认 output/）")
    args = parser.parse_args()

    # 确定视频路径
    base_dir = os.path.dirname(os.path.abspath(__file__))
    video_path = args.video
    if video_path is None:
        video_path = find_default_video(os.path.join(base_dir, "input"))
        if video_path is None:
            print("没有找到视频！请把视频文件放进 input/ 文件夹，")
            print("或者用命令指定：python main.py \"你的视频路径.mp4\"")
            sys.exit(1)
    elif not os.path.isabs(video_path):
        video_path = os.path.join(base_dir, video_path)

    run(video_path, threshold=args.threshold,
        output_root=os.path.join(base_dir, args.output))


if __name__ == "__main__":
    main()

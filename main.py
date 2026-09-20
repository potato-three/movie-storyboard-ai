# -*- coding: utf-8 -*-
"""
main.py —— 分镜提取命令行入口
================================
用法：
    1. 把视频放进『原始视频』文件夹
    2. python main.py                      处理文件夹里第一个视频
       python main.py "D:\\某视频.mp4"      指定视频
       python main.py -t 23 -m 平衡         指定灵敏度与模式
       python main.py --no-motion          只切镜头、不做运动分析

结果统一写入『分镜结果』文件夹，每次一个子文件夹。
"""

import os
import sys
import argparse

from storyboard import config as C
from storyboard.pipeline import run_pipeline


def main():
    ap = argparse.ArgumentParser(description="电影分镜提取工具（命令行）")
    ap.add_argument("video", nargs="?", default=None,
                    help="视频路径；不填则处理『原始视频』里的第一个视频")
    ap.add_argument("--threshold", "-t", type=float, default=27.0,
                    help="镜头切换灵敏度，越小切得越多（默认 27）")
    ap.add_argument("--mode", "-m", default=C.DEFAULT_MODE,
                    choices=list(C.MODES.keys()), help="精确 / 平衡 / 快速")
    ap.add_argument("--no-motion", action="store_true", help="跳过运动分析")
    args = ap.parse_args()

    if args.video:
        vp = args.video if os.path.isabs(args.video) else os.path.abspath(args.video)
    else:
        vids = C.list_raw_videos()
        if not vids:
            print("『原始视频』文件夹里没有视频。请先把视频放进去，")
            print("或指定路径：python main.py \"你的视频.mp4\"")
            sys.exit(1)
        vp = C.raw_video_path(vids[0])

    if not os.path.exists(vp):
        print("找不到视频：", vp)
        sys.exit(1)

    print("=" * 56)
    print(" 电影分镜提取工具")
    print(" 视频：" + os.path.basename(vp))
    print(f" 阈值：{args.threshold}    模式：{args.mode}")
    print("=" * 56)

    def prog(frac, desc):
        sys.stdout.write(f"\r {desc} … {int(frac * 100):3d}%")
        sys.stdout.flush()

    result = None
    try:
        for ev in run_pipeline(vp, threshold=args.threshold, mode=args.mode,
                               do_motion=not args.no_motion, progress=prog):
            kind = ev[0]
            if kind == "status":
                print("\n" + ev[1])
            elif kind == "shot":
                _, i, n, _shot, _f = ev
                sys.stdout.write(f"\r 处理镜头 {i}/{n}")
                sys.stdout.flush()
            elif kind == "done":
                result = ev[1]
    except Exception as e:
        print("\n[错误] " + str(e))
        sys.exit(1)

    print("\n" + "=" * 56)
    print(" 全部完成！结果文件夹：")
    print("  " + result["out_dir"])
    print(" 图文分镜本（浏览器打开）：" + result["files"]["html"])
    print("=" * 56)


if __name__ == "__main__":
    main()

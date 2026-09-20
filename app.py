# -*- coding: utf-8 -*-
"""
app.py —— 分镜提取网页界面
============================
运行方法：python app.py
启动后浏览器会自动打开 http://127.0.0.1:7860
在网页里上传视频 → 点「开始提取」→ 在线查看分镜表和关键帧，并可下载结果。
"""

import os
import tempfile
import pandas as pd
import gradio as gr

from storyboard import (
    detect_shots,
    extract_keyframes,
    export_csv,
    export_markdown,
    export_html,
)


def process_video(video_file, threshold):
    """Gradio 回调：跑完整流水线并返回结果。"""
    if video_file is None:
        raise gr.Error("请先上传一个视频文件")

    video_path = video_file if isinstance(video_file, str) else video_file.name
    video_name = os.path.splitext(os.path.basename(video_path))[0]

    # 结果放到临时目录
    out_dir = tempfile.mkdtemp(prefix="storyboard_")
    frames_dir = os.path.join(out_dir, "frames")
    os.makedirs(frames_dir, exist_ok=True)

    # 1. 检测镜头
    try:
        shots, fps, total_frames = detect_shots(video_path, threshold=threshold)
    except (ValueError, FileNotFoundError) as e:
        raise gr.Error(str(e))
    if not shots:
        raise gr.Error("没有检测到镜头，请换个视频或调低灵敏度阈值")

    # 2. 提取关键帧
    shots = extract_keyframes(video_path, shots, frames_dir)

    # 3. 导出文件
    csv_path = export_csv(shots, os.path.join(out_dir, "storyboard.csv"))
    md_path = export_markdown(shots, os.path.join(out_dir, "storyboard.md"), video_name)
    html_path = export_html(shots, os.path.join(out_dir, "storyboard.html"), video_name)

    # 4. 整理给网页展示的表格
    df = pd.DataFrame([{
        "镜号": s["shot_no"],
        "开始": s["start_tc"],
        "结束": s["end_tc"],
        "时长(秒)": s["duration"],
    } for s in shots])

    # 5. 关键帧画廊：(图片路径, 标题) 列表
    gallery = [
        (s["keyframe"], f"镜头{s['shot_no']}｜{s['start_tc']}｜{s['duration']}s")
        for s in shots if s.get("keyframe")
    ]

    summary = f"✅ 提取完成：共 **{len(shots)}** 个镜头 ｜ 帧率 {fps:.1f} fps ｜ 结果文件可在下方下载"
    download_files = [csv_path, md_path, html_path]
    return df, gallery, summary, download_files, html_path


# ---------------- 界面 ----------------

with gr.Blocks(title="电影分镜提取工具") as demo:
    gr.Markdown(
        "# 🎬 电影分镜提取工具\n"
        "上传一段视频，自动切分镜头、提取关键帧、生成结构化分镜表。\n\n"
        "**支持 MP4 / MKV / MOV / AVI / WMV / FLV / WebM / TS 等常见格式**（含 H.265），"
        "无需浏览器能播放，交给后端解码即可。电影文件体积较大时，提取需要一些时间，请耐心等待。"
    )

    with gr.Row():
        with gr.Column(scale=1):
            video_input = gr.File(
                label="① 上传视频文件",
                file_types=[
                    ".mp4", ".mkv", ".mov", ".avi", ".wmv", ".flv",
                    ".webm", ".m4v", ".ts", ".mpg", ".mpeg", ".3gp",
                ],
                type="filepath",
            )
            threshold = gr.Slider(
                10, 60, value=27, step=1,
                label="② 镜头切换灵敏度（数值越小，切出的镜头越多）",
                info="快剪/动作片试 20~25，长镜头/文艺片试 30~40",
            )
            btn = gr.Button("③ 开始提取分镜", variant="primary", size="lg")

        with gr.Column(scale=1):
            summary = gr.Markdown("结果会显示在这里。")
            html_file = gr.File(label="图文版 HTML（浏览器打开效果最好）", visible=True)
            other_files = gr.File(label="CSV / Markdown 分镜表", file_count="multiple")

    gr.Markdown("### 关键帧")
    gallery = gr.Gallery(
        label="每个镜头一张代表帧",
        columns=4, height=420, object_fit="cover", show_label=False,
    )

    gr.Markdown("### 分镜表")
    table = gr.Dataframe(
        headers=["镜号", "开始", "结束", "时长(秒)"],
        datatype=["number", "str", "str", "number"],
        wrap=True, interactive=False,
    )

    btn.click(
        fn=process_video,
        inputs=[video_input, threshold],
        outputs=[table, gallery, summary, other_files, html_file],
    )


if __name__ == "__main__":
    # 默认仅本机访问；设置环境变量 GRADIO_SHARE=1 可生成公网临时链接
    share = os.environ.get("GRADIO_SHARE", "0") == "1"
    demo.launch(
        inbrowser=True,
        server_name="0.0.0.0",   # 允许同一 WiFi/局域网内的手机、其他电脑访问
        server_port=7860,
        share=share,
        theme=gr.themes.Soft(),
    )

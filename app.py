# -*- coding: utf-8 -*-
"""
app.py —— 分镜提取网页界面（v0.2.2）
====================================
· 原始视频可从下拉直接选择（免上传、不产生副本），也可临时上传
· 精确 / 平衡 / 快速 三档
· 流式进度：独立进度区，双缓冲平滑预览已处理镜头
· 镜头浏览器：大图 + 拖动滑块 + 上一镜/下一镜 + 关键帧/运动图切换
· 所有结果保存到 F 盘『分镜结果』，可一键打开文件夹
"""

import os
import time
import uuid
from pathlib import Path

# 必须在 import gradio 之前，把网页上传/缓存目录指到项目内（F 盘），不占 C 盘
from storyboard import config as C
os.makedirs(C.GRADIO_TMP_DIR, exist_ok=True)
os.environ.setdefault("GRADIO_TEMP_DIR", C.GRADIO_TMP_DIR)

import pandas as pd
import gradio as gr

from storyboard import config
from storyboard.pipeline import run_pipeline
from storyboard.preview import preview_payload


# ---------------- 辅助 ----------------

def _to_browser(shots, run_id):
    return [{
        "run_id": run_id,
        "no": s["shot_no"],
        "keyframe": s.get("keyframe", ""),
        "motion": s.get("motion_image", ""),
        "start_tc": s["start_tc"], "end_tc": s["end_tc"],
        "duration": s["duration"],
        "camera": s.get("camera_motion", ""),
        "subject": s.get("subject_motion", ""),
        "level": s.get("motion_level", ""),
    } for s in shots]


def _show(idx, view, data, shown=None, busy=False):
    """Only user input browses completed results; an empty state never clears preview."""
    if busy or not data:
        return gr.skip(), gr.skip()
    i = max(1, min(len(data), int(idx)))
    s = data[i - 1]
    requested = [s["run_id"], i, view]
    if shown == requested:
        return gr.skip(), gr.skip()
    return preview_payload(s, view), requested


# ---------------- 主流程（生成器，流式） ----------------

OUTPUT_NAMES = (
    "status", "viewer", "shot_slider", "gallery", "table", "html_file",
    "other_files", "saved_md", "browser_state", "outdir_state", "shown_state",
    "busy_state", "view_radio", "prev_btn", "next_btn", "btn", "progress_area",
)


def _updates(**values):
    return tuple(values.get(name, gr.skip()) for name in OUTPUT_NAMES)


def _controls(busy, count=0):
    enabled = not busy and count > 0
    return dict(busy_state=busy, btn=gr.update(interactive=not busy),
                shot_slider=gr.update(interactive=enabled),
                view_radio=gr.update(interactive=enabled),
                prev_btn=gr.update(interactive=enabled),
                next_btn=gr.update(interactive=enabled))


def process_video(file_in, dd_choice, threshold, mode, progress=gr.Progress()):
    # 确定视频来源
    if file_in:
        vp = file_in
    elif dd_choice:
        vp = config.raw_video_path(dd_choice)
    else:
        yield _updates(status="❌ 请先从下拉选择『原始视频』，或上传一个视频文件。")
        return
    if not os.path.exists(vp):
        yield _updates(status=f"❌ 找不到视频：{vp}")
        return

    gallery_acc = []
    result = None
    run_id = uuid.uuid4().hex
    last_preview = last_gallery = last_status = float("-inf")
    controls = _controls(True)
    controls["view_radio"] = gr.update(value="关键帧", interactive=False)
    yield _updates(status="① 开始扫描视频；新镜头就绪后自动预览。",
                   viewer='{"reset":true}', gallery=[], table=[], html_file=None,
                   other_files=None, saved_md="", browser_state=[], outdir_state="",
                   shown_state=None, **controls)

    def ui_progress(frac, desc):
        progress(frac, desc=desc)

    try:
        for ev in run_pipeline(vp, threshold=float(threshold), mode=mode,
                               do_motion=True, progress=ui_progress):
            kind = ev[0]
            if kind == "status":
                yield _updates(status=ev[1])
            elif kind == "shot":
                _, i, n, shot, frac = ev
                if shot.get("keyframe"):
                    gallery_acc.append((
                        shot["keyframe"],
                        f"{shot['shot_no']}｜{shot['start_tc']}｜{shot.get('camera_motion','')}",
                    ))
                now = time.monotonic()
                changes = {}
                if now - last_status >= .2 or i == n:
                    changes["status"] = (
                        f"② 已处理 **{i}/{n}** 个镜头（{int(frac * 100)}%）。"
                        "预览约每秒更新，完整镜头均会保存。")
                    last_status = now
                if now - last_preview >= 1.0 or i == n:
                    changes["viewer"] = preview_payload(_to_browser([shot], run_id)[0], automatic=True)
                    changes["shot_slider"] = gr.update(maximum=max(n, 2), value=i, interactive=False)
                    last_preview = now
                if now - last_gallery >= 2.0 or i == n:
                    changes["gallery"] = list(gallery_acc)
                    last_gallery = now
                if changes:
                    yield _updates(**changes)
            elif kind == "done":
                result = ev[1]
    except Exception as e:
        yield _updates(status=f"❌ 处理失败：{e}", gallery=[], **_controls(False))
        return

    if result is None:
        yield _updates(status="❌ 未生成结果，请重试。", gallery=[], **_controls(False))
        return

    shots = result["shots"]
    n = len(shots)
    browser = _to_browser(shots, run_id)
    df = pd.DataFrame([{
        "镜号": s["shot_no"], "开始": s["start_tc"], "结束": s["end_tc"],
        "时长(秒)": s["duration"], "机位": s.get("camera_motion", ""),
        "主体运动": s.get("subject_motion", ""), "强度": s.get("motion_level", ""),
    } for s in shots])
    gallery_full = [(s.get("keyframe"),
                     f"{s['shot_no']}｜{s['start_tc']}｜{s.get('camera_motion','')}")
                    for s in shots if s.get("keyframe")]
    out_dir = result["out_dir"]
    controls = _controls(False, n)
    controls["shot_slider"] = gr.update(maximum=max(n, 2), value=max(n, 1), interactive=n > 1)
    yield _updates(
        status=f"✅ 提取完成：共 **{n}** 个镜头 ｜ {result['fps']:.1f} fps ｜ 模式 {mode}",
        viewer=preview_payload(browser[-1], automatic=True) if browser else gr.skip(),
        gallery=gallery_full, table=df, html_file=result["files"]["html"],
        other_files=[result["files"]["csv"], result["files"]["md"]],
        saved_md=f"📂 结果已保存到：\n\n`{out_dir}`", browser_state=browser,
        outdir_state=out_dir, shown_state=[run_id, n, "关键帧"], **controls)


# ---------------- 界面 ----------------

# 深色主题的第一层：使用 Gradio 官方主题变量，覆盖动态生成的上传、下载、表格、
# Radio 等组件，而不是只靠零散 CSS 追着内部 class 名修补。
_APP_THEME = gr.themes.Base(
    primary_hue="blue", secondary_hue="slate", neutral_hue="slate",
).set(
    body_background_fill="#080b12", body_background_fill_dark="#080b12",
    body_text_color="#e8eefc", body_text_color_dark="#e8eefc",
    body_text_color_subdued="#a9b6cc", body_text_color_subdued_dark="#a9b6cc",
    background_fill_primary="#0e1420", background_fill_primary_dark="#0e1420",
    background_fill_secondary="#111a29", background_fill_secondary_dark="#111a29",
    block_background_fill="#101827", block_background_fill_dark="#101827",
    block_border_color="#2a3a55", block_border_color_dark="#2a3a55",
    block_label_background_fill="#0e1420", block_label_background_fill_dark="#0e1420",
    block_label_border_color="#2a3a55", block_label_border_color_dark="#2a3a55",
    block_label_text_color="#dce7fb", block_label_text_color_dark="#dce7fb",
    input_background_fill="#0b1220", input_background_fill_dark="#0b1220",
    input_background_fill_focus="#101c31", input_background_fill_focus_dark="#101c31",
    input_background_fill_hover="#111d31", input_background_fill_hover_dark="#111d31",
    input_border_color="#385071", input_border_color_dark="#385071",
    input_border_color_focus="#4e8cff", input_border_color_focus_dark="#4e8cff",
    input_placeholder_color="#7f8da6", input_placeholder_color_dark="#7f8da6",
    checkbox_label_background_fill="#0b1220", checkbox_label_background_fill_dark="#0b1220",
    checkbox_label_background_fill_selected="#1d4ed8", checkbox_label_background_fill_selected_dark="#1d4ed8",
    checkbox_label_text_color="#e8eefc", checkbox_label_text_color_dark="#e8eefc",
    checkbox_label_text_color_selected="#ffffff", checkbox_label_text_color_selected_dark="#ffffff",
    checkbox_label_border_color="#385071", checkbox_label_border_color_dark="#385071",
    checkbox_label_border_color_selected="#60a5fa", checkbox_label_border_color_selected_dark="#60a5fa",
    button_primary_background_fill="#2563eb", button_primary_background_fill_dark="#2563eb",
    button_primary_background_fill_hover="#3b82f6", button_primary_background_fill_hover_dark="#3b82f6",
    button_primary_border_color="#60a5fa", button_primary_border_color_dark="#60a5fa",
    button_primary_text_color="#ffffff", button_primary_text_color_dark="#ffffff",
    button_secondary_background_fill="#1d4ed8", button_secondary_background_fill_dark="#1d4ed8",
    button_secondary_background_fill_hover="#2563eb", button_secondary_background_fill_hover_dark="#2563eb",
    button_secondary_border_color="#60a5fa", button_secondary_border_color_dark="#60a5fa",
    button_secondary_text_color="#ffffff", button_secondary_text_color_dark="#ffffff",
    table_text_color="#e8eefc", table_text_color_dark="#e8eefc",
    table_even_background_fill="#0e1625", table_even_background_fill_dark="#0e1625",
    table_odd_background_fill="#111c2d", table_odd_background_fill_dark="#111c2d",
    table_border_color="#2a3a55", table_border_color_dark="#2a3a55",
)

# 深色主题的第二层：只针对本工具的稳定容器补充布局、蓝色按钮和预览效果。
# 刻意不再使用 `span { color: ... }` 之类的全局文字规则，避免白字落到白底上。
_APP_CSS = """
:root { color-scheme: dark; }
body, .gradio-container { background: #080b12 !important; }
.gradio-container { max-width: 1440px !important; }
#storyboard_app { color: #e8eefc; }
#storyboard_app h1, #storyboard_app h2, #storyboard_app h3,
#storyboard_app .prose, #storyboard_app .prose p { color: #e8eefc !important; }
#input_panel, #result_panel {
  background: #101827 !important;
  border: 1px solid #2a3a55 !important;
  border-radius: 14px !important;
  padding: 14px !important;
}
#video_upload, #html_export, #table_exports {
  background: #0b1220 !important;
  border-color: #385071 !important;
}
#storyboard_app [data-testid="file-upload"],
#storyboard_app [data-testid="file-preview"],
#storyboard_app .file-preview, #storyboard_app .upload-container,
#storyboard_app .drop-zone {
  background: #0b1220 !important;
  color: #e8eefc !important;
  border-color: #385071 !important;
}
#storyboard_app button {
  background: #1d4ed8 !important;
  border-color: #60a5fa !important;
  color: #ffffff !important;
  transition: background .18s ease, transform .18s ease !important;
}
#storyboard_app button:hover {
  background: #3b82f6 !important;
  transform: translateY(-1px);
}
#storyboard_app button.primary, #storyboard_app button[data-variant="primary"] {
  background: #2563eb !important;
  border-color: #93c5fd !important;
  color: #ffffff !important;
}
#storyboard_app table, #storyboard_app thead, #storyboard_app tbody,
#storyboard_app tr, #storyboard_app td, #storyboard_app th {
  background: #0e1625 !important;
  color: #e8eefc !important;
  border-color: #2a3a55 !important;
}
#storyboard_app footer { background: #080b12 !important; }

/* Loading is confined to this fixed slot, never placed over images. */
#progress_area { min-height: 76px; }
"""

_WEB_DIR = Path(__file__).resolve().parent / "web"
_VIEWER_JS = (_WEB_DIR / "preview.js").read_text(encoding="utf-8")
_VIEWER_CSS = (_WEB_DIR / "preview.css").read_text(encoding="utf-8")

with gr.Blocks(title="电影分镜提取工具", elem_id="storyboard_app") as demo:
    gr.Markdown(
        "# 🎬 电影分镜提取工具 v0.2.2\n"
        "上传或选择视频 → 自动切镜头 → 提取关键帧 → 分析运动（机位/主体方向/强度）→ 生成图文分镜本。\n\n"
        "支持 MP4 / MKV / MOV / AVI / WMV / FLV / WebM / TS 等常见格式（含 H.265），"
        "无需浏览器能播放，交给后端解码即可。**所有结果只保存在 F 盘『分镜结果』文件夹。**"
    )

    with gr.Row():
        with gr.Column(scale=1, elem_id="input_panel"):
            video_dd = gr.Dropdown(
                choices=config.list_raw_videos(),
                label="① 从『原始视频』文件夹选择", interactive=True)
            refresh_btn = gr.Button("🔄 刷新文件列表", size="sm", variant="secondary")
            video_input = gr.File(
                label="…或上传临时视频（任意格式，缓存也在 F 盘）",
                file_types=list(config.VIDEO_EXTS), type="filepath",
                elem_id="video_upload")
            threshold = gr.Slider(
                10, 60, value=27, step=1,
                label="② 镜头切换灵敏度（数值越小切得越多）",
                info="快剪/动作/动画试 20~25，长镜头/文艺片试 30~40")
            mode = gr.Radio(
                ["精确", "平衡", "快速"], value=config.DEFAULT_MODE,
                label="③ 运行模式",
                info="精确=逐帧最慢；平衡=隔1帧约快一倍（推荐）；快速=隔2帧。运动分析在缩小画面上采样，不影响大方向。")
            btn = gr.Button("④ 开始提取分镜", variant="primary", size="lg")

        with gr.Column(scale=1, elem_id="result_panel"):
            progress_area = gr.HTML("", min_height=76, elem_id="progress_area")
            status = gr.Markdown("结果会显示在这里。")
            saved_md = gr.Markdown("")
            open_btn = gr.Button("📂 打开本次结果文件夹", size="sm", variant="secondary")
            html_file = gr.File(label="图文分镜本 HTML（浏览器打开）", elem_id="html_export")
            other_files = gr.File(label="CSV / Markdown 分镜表", file_count="multiple",
                                  elem_id="table_exports")

    gr.Markdown("### 🎞️ 镜头浏览器")
    viewer = gr.HTML("{}", elem_id="shot_viewer", apply_default_css=False,
                     html_template='<div class="sb-preview-mount"></div>',
                     css_template=_VIEWER_CSS, js_on_load=_VIEWER_JS)
    view_radio = gr.Radio(
        ["关键帧", "运动图"], value="关键帧", label="查看内容", interactive=False)
    with gr.Row():
        prev_btn = gr.Button("◀ 上一镜", scale=1, variant="secondary", interactive=False)
        shot_slider = gr.Slider(1, 2, value=1, step=1,
                                label="定位镜头（提取期间自动预览，完成后可手动浏览）", scale=4,
                                interactive=False, elem_id="shot_position")
        next_btn = gr.Button("下一镜 ▶", scale=1, variant="secondary", interactive=False)

    gr.Markdown("### 全部关键帧总览（点击任意一张，上方自动跳转）")
    gallery = gr.Gallery(columns=6, height=320, object_fit="cover",
                         show_label=False, allow_preview=False, elem_id="shot_gallery")

    gr.Markdown("### 分镜表")
    table = gr.Dataframe(
        headers=["镜号", "开始", "结束", "时长(秒)", "机位", "主体运动", "强度"],
        datatype=["number", "str", "str", "number", "str", "str", "str"],
        wrap=True, interactive=False)

    # 跨回调状态
    browser_state = gr.State([])
    outdir_state = gr.State("")
    shown_state = gr.State(None)  # 最近请求 [任务ID, 镜头号, 视图]；真正显示状态由前端解码后提交
    busy_state = gr.State(False)

    main_outputs = [
        status, viewer, shot_slider, gallery, table, html_file,
        other_files, saved_md, browser_state, outdir_state, shown_state,
        busy_state, view_radio, prev_btn, next_btn, btn, progress_area,
    ]

    btn.click(fn=process_video,
              inputs=[video_input, video_dd, threshold, mode],
              outputs=main_outputs, show_progress="full", show_progress_on=[progress_area],
              concurrency_id="storyboard-ui", trigger_mode="once")

    refresh_btn.click(fn=lambda: gr.update(choices=config.list_raw_videos()),
                      outputs=[video_dd])

    # input only fires for user input; programmatic progress updates never browse.
    b_inputs = [shot_slider, view_radio, browser_state, shown_state, busy_state]
    b_outputs = [viewer, shown_state]
    browse_options = dict(show_progress="hidden", trigger_mode="always_last",
                          concurrency_id="storyboard-ui")
    shot_slider.input(fn=_show, inputs=b_inputs, outputs=b_outputs, **browse_options)
    view_radio.input(fn=_show, inputs=b_inputs, outputs=b_outputs, **browse_options)

    def _step(offset, idx, view, data, shown, busy):
        if busy or not data:
            return gr.skip(), gr.skip(), gr.skip()
        new_idx = max(1, min(len(data), int(idx) + offset)) if data else int(idx)
        payload, shown2 = _show(new_idx, view, data, shown, busy)
        return payload, gr.update(value=new_idx), shown2

    prev_btn.click(fn=lambda i, v, d, s, b: _step(-1, i, v, d, s, b),
                   inputs=b_inputs,
                   outputs=[viewer, shot_slider, shown_state], **browse_options)
    next_btn.click(fn=lambda i, v, d, s, b: _step(1, i, v, d, s, b),
                   inputs=b_inputs,
                   outputs=[viewer, shot_slider, shown_state], **browse_options)

    def _on_gallery(evt: gr.SelectData, view, data, shown, busy):
        if busy or not data:
            return gr.skip(), gr.skip(), gr.skip()
        idx = evt.index
        if isinstance(idx, (list, tuple)):
            idx = idx[0] if idx else 0
        available = [i for i, shot in enumerate(data, 1) if shot.get("keyframe")]
        if not 0 <= int(idx) < len(available):
            return gr.skip(), gr.skip(), gr.skip()
        i = available[int(idx)]
        payload, shown2 = _show(i, view, data, shown)
        return payload, gr.update(value=i), shown2

    gallery.select(fn=_on_gallery, inputs=[view_radio, browser_state, shown_state, busy_state],
                   outputs=[viewer, shot_slider, shown_state], **browse_options)

    def _open_folder(d):
        if not d:
            return "⚠️ 还没有可打开的结果，请先提取一次。"
        try:
            os.startfile(d)
            return f"📂 已打开：`{d}`"
        except Exception as e:
            return f"打开失败：{e}"

    open_btn.click(fn=_open_folder, inputs=[outdir_state], outputs=[saved_md])


if __name__ == "__main__":
    share = os.environ.get("GRADIO_SHARE", "0") == "1"
    demo.queue()
    demo.launch(
        inbrowser=True,
        server_name="0.0.0.0",
        server_port=7860,
        share=share,
        allowed_paths=[config.RAW_VIDEO_DIR, config.RESULT_DIR, config.GRADIO_TMP_DIR],
        css=_APP_CSS,
        theme=_APP_THEME,
    )

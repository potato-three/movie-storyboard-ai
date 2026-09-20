# -*- coding: utf-8 -*-
"""
app.py —— 分镜提取网页界面（v0.2）
====================================
· 原始视频可从下拉直接选择（免上传、不产生副本），也可临时上传
· 精确 / 平衡 / 快速 三档
· 流式进度：扫描显示百分比，逐镜头出一张亮一张
· 镜头浏览器：大图 + 拖动滑块 + 上一镜/下一镜 + 关键帧/运动图切换
· 所有结果保存到 F 盘『分镜结果』，可一键打开文件夹
"""

import os

# 必须在 import gradio 之前，把网页上传/缓存目录指到项目内（F 盘），不占 C 盘
from storyboard import config as C
os.makedirs(C.GRADIO_TMP_DIR, exist_ok=True)
os.environ.setdefault("GRADIO_TEMP_DIR", C.GRADIO_TMP_DIR)

import pandas as pd
import gradio as gr

from storyboard import config
from storyboard.pipeline import run_pipeline


# ---------------- 辅助 ----------------

def _shot_info(s):
    return (
        f"**镜头 {s['shot_no']}**　{s['start_tc']} → {s['end_tc']}"
        f"　时长 {s['duration']} 秒\n\n"
        f"机位运动：**{s.get('camera_motion') or '—'}**　｜　"
        f"画面主体：**{s.get('subject_motion') or '—'}**"
        f"（强度 {s.get('motion_level') or '—'}）"
    )


def _to_browser(shots):
    return [{
        "no": s["shot_no"],
        "keyframe": s.get("keyframe", ""),
        "motion": s.get("motion_image", ""),
        "start_tc": s["start_tc"], "end_tc": s["end_tc"],
        "duration": s["duration"],
        "camera": s.get("camera_motion", ""),
        "subject": s.get("subject_motion", ""),
        "level": s.get("motion_level", ""),
    } for s in shots]


def _show(idx, view, data, shown=None):
    """返回 (大图, 信息, 已显示状态)。相同镜头+视图直接 skip，避免重复渲染/闪烁。"""
    if not data:
        return None, "", shown
    i = max(1, min(len(data), int(idx)))
    # 与当前已显示的完全一致：三个输出全部跳过，前端不重载图片、不触发淡入
    if shown == [i, view]:
        return gr.skip(), gr.skip(), gr.skip()
    s = data[i - 1]
    if view == "运动图" and s.get("motion"):
        img = s["motion"]
    else:
        img = s.get("keyframe")
    info = _shot_info({
        "shot_no": s["no"], "start_tc": s["start_tc"], "end_tc": s["end_tc"],
        "duration": s["duration"], "camera_motion": s["camera"],
        "subject_motion": s["subject"], "motion_level": s["level"],
    })
    return img, info, [i, view]


# ---------------- 主流程（生成器，流式） ----------------

def process_video(file_in, dd_choice, threshold, mode, progress=gr.Progress()):
    skip = gr.skip()
    # 确定视频来源
    if file_in:
        vp = file_in
    elif dd_choice:
        vp = config.raw_video_path(dd_choice)
    else:
        yield ("❌ 请先从下拉选择『原始视频』，或上传一个视频文件。",) + (skip,) * 10
        return
    if not os.path.exists(vp):
        yield (f"❌ 找不到视频：{vp}",) + (skip,) * 10
        return

    gallery_acc = []
    result = None

    def ui_progress(frac, desc):
        progress(frac, desc=desc)

    try:
        for ev in run_pipeline(vp, threshold=float(threshold), mode=mode,
                               do_motion=True, progress=ui_progress):
            kind = ev[0]
            if kind == "status":
                yield (ev[1],) + (skip,) * 10
            elif kind == "shot":
                _, i, n, shot, frac = ev
                img = shot.get("keyframe") or None
                gallery_acc.append((
                    shot.get("keyframe"),
                    f"{shot['shot_no']}｜{shot['start_tc']}｜{shot.get('camera_motion','')}",
                ))
                K = max(1, n // 80)
                gal = gallery_acc if (i % K == 0 or i == n) else skip
                info = _shot_info(shot)
                yield (
                    f"② 正在处理镜头 **{i}/{n}**（{int(frac * 100)}%），出一张亮一张…",
                    img, gr.update(maximum=n, value=i), info, gal,
                    skip, skip, skip, skip, skip, skip,
                )
            elif kind == "done":
                result = ev[1]
    except Exception as e:
        yield (f"❌ 处理失败：{e}",) + (skip,) * 10
        return

    if result is None:
        yield ("❌ 未生成结果，请重试。",) + (skip,) * 10
        return

    shots = result["shots"]
    n = len(shots)
    browser = _to_browser(shots)
    df = pd.DataFrame([{
        "镜号": s["shot_no"], "开始": s["start_tc"], "结束": s["end_tc"],
        "时长(秒)": s["duration"], "机位": s.get("camera_motion", ""),
        "主体运动": s.get("subject_motion", ""), "强度": s.get("motion_level", ""),
    } for s in shots])
    gallery_full = [(s.get("keyframe"),
                     f"{s['shot_no']}｜{s['start_tc']}｜{s.get('camera_motion','')}")
                    for s in shots if s.get("keyframe")]
    out_dir = result["out_dir"]
    first_img, first_info, _ = _show(1, "关键帧", browser)

    yield (
        f"✅ 提取完成：共 **{n}** 个镜头 ｜ {result['fps']:.1f} fps ｜ 模式 {mode}",
        first_img, gr.update(maximum=max(n, 1), value=1), first_info,
        gallery_full, df,
        result["files"]["html"], [result["files"]["csv"], result["files"]["md"]],
        f"📂 结果已保存到（F盘）：\n\n`{out_dir}`",
        browser, out_dir,
    )


# ---------------- 界面 ----------------

# 镜头浏览器大图的「平滑预览」美化：深色播放器底 + 切换淡入，避免白屏闪眼。
# Gradio 6 不执行 gr.HTML 里的 <script>，故 CSS 走 head、JS 走 js_on_load。
_VIEWER_CSS = """
#shot_viewer { background:#0d0e11 !important; border-radius:10px; overflow:hidden; }
#shot_viewer img { background:transparent !important; }
#shot_viewer button { background-color:rgba(255,255,255,0.10) !important; }
"""

_VIEWER_JS = """
(function () {
  // 禁用滑块的鼠标滚轮改值：滚轮在滑块上只会让镜头号飞速跳动、大图狂闪
  if (!window.__sbWheel) {
    window.__sbWheel = true;
    document.addEventListener('wheel', function (e) {
      var t = e.target;
      if (t && t.tagName === 'INPUT' && t.type === 'range') { e.preventDefault(); }
    }, { passive: false, capture: true });
  }
  function fadeIn(img) {
    img.style.transition = 'opacity .28s ease';
    img.style.opacity = '1';
  }
  function bindImg(img) {
    if (img.__sbFade) return; img.__sbFade = true;
    // 新插入、尚未加载完的 img：先隐藏，加载好再柔和淡入（间隙是深色底，不白屏）
    if (!(img.complete && img.naturalWidth > 0)) {
      img.style.opacity = '0';
      img.addEventListener('load', function () { fadeIn(img); }, { once: true });
      setTimeout(function () { if (img.complete && img.naturalWidth > 0) fadeIn(img); }, 700);
    }
    // 同一 img 的 src 变化：瞬间压暗到深色底（不做淡出动画，避免呼吸感），新图就绪再淡入
    var mo = new MutationObserver(function () {
      img.style.transition = 'none';
      img.style.opacity = '0';
      // 强制回流后再挂过渡，确保淡入生效
      void img.offsetWidth;
      if (img.complete && img.naturalWidth > 0) { setTimeout(function () { fadeIn(img); }, 30); }
      else { img.addEventListener('load', function () { fadeIn(img); }, { once: true }); }
    });
    mo.observe(img, { attributes: true, attributeFilter: ['src'] });
  }
  function attach(root) {
    root.querySelectorAll('img').forEach(bindImg);
    var o = new MutationObserver(function () { root.querySelectorAll('img').forEach(bindImg); });
    o.observe(root, { childList: true, subtree: true });
  }
  var timer = setInterval(function () {
    var r = document.getElementById('shot_viewer');
    if (r) { attach(r); clearInterval(timer); }
  }, 250);
})();
"""

with gr.Blocks(title="电影分镜提取工具") as demo:
    gr.Markdown(
        "# 🎬 电影分镜提取工具 v0.2\n"
        "上传或选择视频 → 自动切镜头 → 提取关键帧 → 分析运动（机位/主体方向/强度）→ 生成图文分镜本。\n\n"
        "支持 MP4 / MKV / MOV / AVI / WMV / FLV / WebM / TS 等常见格式（含 H.265），"
        "无需浏览器能播放，交给后端解码即可。**所有结果只保存在 F 盘『分镜结果』文件夹。**"
    )

    with gr.Row():
        with gr.Column(scale=1):
            video_dd = gr.Dropdown(
                choices=config.list_raw_videos(),
                label="① 从『原始视频』文件夹选择", interactive=True)
            refresh_btn = gr.Button("🔄 刷新文件列表", size="sm")
            video_input = gr.File(
                label="…或上传临时视频（任意格式，缓存也在 F 盘）",
                file_types=list(config.VIDEO_EXTS), type="filepath")
            threshold = gr.Slider(
                10, 60, value=27, step=1,
                label="② 镜头切换灵敏度（数值越小切得越多）",
                info="快剪/动作/动画试 20~25，长镜头/文艺片试 30~40")
            mode = gr.Radio(
                ["精确", "平衡", "快速"], value=config.DEFAULT_MODE,
                label="③ 运行模式",
                info="精确=逐帧最慢；平衡=隔1帧约快一倍（推荐）；快速=隔2帧。运动分析在缩小画面上采样，不影响大方向。")
            btn = gr.Button("④ 开始提取分镜", variant="primary", size="lg")

        with gr.Column(scale=1):
            status = gr.Markdown("结果会显示在这里。")
            saved_md = gr.Markdown("")
            open_btn = gr.Button("📂 打开本次结果文件夹", size="sm")
            html_file = gr.File(label="图文分镜本 HTML（浏览器打开）")
            other_files = gr.File(label="CSV / Markdown 分镜表", file_count="multiple")

    gr.Markdown("### 🎞️ 镜头浏览器")
    viewer = gr.Image(height=440, show_label=False, elem_id="shot_viewer")
    gr.HTML(head="<style>" + _VIEWER_CSS + "</style>", js_on_load=_VIEWER_JS)
    view_radio = gr.Radio(
        ["关键帧", "运动图"], value="关键帧", label="查看内容", interactive=True)
    with gr.Row():
        prev_btn = gr.Button("◀ 上一镜", scale=1)
        shot_slider = gr.Slider(1, 2, value=1, step=1,
                                label="拖动滑块快速定位镜头", scale=4)
        next_btn = gr.Button("下一镜 ▶", scale=1)
    shot_info = gr.Markdown("")

    gr.Markdown("### 全部关键帧总览（点击任意一张，上方自动跳转）")
    gallery = gr.Gallery(columns=6, height=320, object_fit="cover",
                         show_label=False, allow_preview=False)

    gr.Markdown("### 分镜表")
    table = gr.Dataframe(
        headers=["镜号", "开始", "结束", "时长(秒)", "机位", "主体运动", "强度"],
        datatype=["number", "str", "str", "number", "str", "str", "str"],
        wrap=True, interactive=False)

    # 跨回调状态
    browser_state = gr.State([])
    outdir_state = gr.State("")
    shown_state = gr.State(None)  # 当前大图已显示的 [镜头号, 视图]，用于去重防闪烁

    main_outputs = [
        status, viewer, shot_slider, shot_info, gallery, table,
        html_file, other_files, saved_md, browser_state, outdir_state,
    ]

    btn.click(fn=process_video,
              inputs=[video_input, video_dd, threshold, mode],
              outputs=main_outputs)

    refresh_btn.click(fn=lambda: gr.update(choices=config.list_raw_videos()),
                      outputs=[video_dd])

    # 镜头浏览器交互
    # · change：数字框输入回车 / 键盘方向键 / 兜底，trigger_mode=always_last 会自动合并连续拖动
    # · release：鼠标或按键松手才触发（拖动过程不请求）
    # · 两者都走 _show，靠 shown_state 对“相同镜头+视图”去重，重复事件直接 skip、不重载图片
    b_inputs = [shot_slider, view_radio, browser_state, shown_state]
    b_outputs = [viewer, shot_info, shown_state]
    shot_slider.change(fn=_show, inputs=b_inputs, outputs=b_outputs)
    shot_slider.release(fn=_show, inputs=b_inputs, outputs=b_outputs)
    view_radio.change(fn=_show, inputs=b_inputs, outputs=b_outputs)

    def _step(offset, idx, view, data, shown):
        new_idx = max(1, min(len(data), int(idx) + offset)) if data else int(idx)
        img, info, shown2 = _show(new_idx, view, data, shown)
        return img, info, gr.update(value=new_idx), shown2

    prev_btn.click(fn=lambda i, v, d, s: _step(-1, i, v, d, s),
                   inputs=b_inputs,
                   outputs=[viewer, shot_info, shot_slider, shown_state])
    next_btn.click(fn=lambda i, v, d, s: _step(1, i, v, d, s),
                   inputs=b_inputs,
                   outputs=[viewer, shot_info, shot_slider, shown_state])

    def _on_gallery(evt: gr.SelectData, view, data, shown):
        idx = evt.index
        if isinstance(idx, (list, tuple)):
            idx = idx[0] if idx else 0
        i = int(idx) + 1
        img, info, shown2 = _show(i, view, data, shown)
        return img, info, gr.update(value=i), shown2

    gallery.select(fn=_on_gallery, inputs=[view_radio, browser_state, shown_state],
                   outputs=[viewer, shot_info, shot_slider, shown_state])

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
        theme=gr.themes.Soft(),
    )

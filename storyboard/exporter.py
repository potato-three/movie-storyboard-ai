# -*- coding: utf-8 -*-
"""
exporter.py —— 把结果导出为 CSV / Markdown / HTML / 提取信息.txt
=================================================================
· CSV / Markdown：结构化表格，含机位、主体运动、强度
· HTML：图文分镜本。为避免长片文件巨大、浏览器卡死，
        HTML 内嵌的是「压缩缩略图」（约 400px），高清原图仍在 关键帧/、运动图/
"""

import os
import csv
import base64
import html as html_lib

import cv2

from storyboard.detector import read_image_cn


# ---------- 缩略图（HTML 瘦身关键） ----------

def _thumb_b64(path: str, width: int = 400, quality: int = 58) -> str:
    """读图 -> 缩放 -> JPEG -> base64；失败返回空串。"""
    img = read_image_cn(path)
    if img is None:
        return ""
    h, w = img.shape[:2]
    if w > width:
        nh = max(1, int(round(h * width / float(w))))
        img = cv2.resize(img, (width, nh), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        return ""
    return base64.b64encode(buf.tobytes()).decode("ascii")


def _bn(path: str) -> str:
    return os.path.basename(path) if path else ""


# ---------- CSV ----------

def export_csv(shots, out_path: str):
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        wr = csv.writer(f)
        wr.writerow(["镜号", "开始时间码", "结束时间码", "时长(秒)",
                     "机位运动", "主体运动", "运动强度",
                     "关键帧文件", "运动图文件"])
        for s in shots:
            wr.writerow([
                s["shot_no"], s["start_tc"], s["end_tc"], s["duration"],
                s.get("camera_motion", ""), s.get("subject_motion", ""),
                s.get("motion_level", ""),
                _bn(s.get("keyframe", "")), _bn(s.get("motion_image", "")),
            ])
    return out_path


# ---------- Markdown ----------

def export_markdown(shots, out_path: str, video_name: str = ""):
    L = [f"# 分镜表：{video_name}\n", f"共 **{len(shots)}** 个镜头。\n"]
    L.append("| 镜号 | 开始 | 结束 | 时长(s) | 机位 | 主体运动 | 强度 | 关键帧 | 运动图 |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for s in shots:
        kf_name, mf_name = _bn(s.get("keyframe", "")), _bn(s.get("motion_image", ""))
        kf = f"[图](关键帧/{kf_name})" if kf_name else "-"
        mf = f"[图](运动图/{mf_name})" if mf_name else "-"
        L.append(
            f"| {s['shot_no']} | {s['start_tc']} | {s['end_tc']} | {s['duration']} "
            f"| {s.get('camera_motion','')} | {s.get('subject_motion','')} "
            f"| {s.get('motion_level','')} | {kf} | {mf} |"
        )
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    return out_path


# ---------- HTML（瘦身版） ----------

def export_html(shots, out_path: str, video_name: str = "", meta: dict = None):
    meta = meta or {}
    rows = []
    for s in shots:
        kf_tag = ""
        if s.get("keyframe") and os.path.exists(s["keyframe"]):
            b = _thumb_b64(s["keyframe"])
            if b:
                kf_tag = f'<img loading="lazy" src="data:image/jpeg;base64,{b}">'
        mo_tag = ""
        if s.get("motion_image") and os.path.exists(s["motion_image"]):
            b = _thumb_b64(s["motion_image"])
            if b:
                mo_tag = f'<img loading="lazy" src="data:image/jpeg;base64,{b}">'
        rows.append(f"""
        <tr>
          <td class="no">{s['shot_no']}</td>
          <td class="frame">{kf_tag}</td>
          <td class="frame">{mo_tag}</td>
          <td class="tc">{s['start_tc']}<br><span class="to">→ {s['end_tc']}</span></td>
          <td class="dur">{s['duration']}</td>
          <td>{html_lib.escape(str(s.get('camera_motion', '')))}</td>
          <td>{html_lib.escape(str(s.get('subject_motion', '')))}</td>
          <td class="lvl">{html_lib.escape(str(s.get('motion_level', '')))}</td>
          <td class="desc" contenteditable="true"></td>
        </tr>""")

    total_duration = round(sum(s["duration"] for s in shots), 2)
    meta_line = (
        f"镜头 {len(shots)} 个 ｜ 总时长 {total_duration} 秒 ｜ "
        f"灵敏度 {meta.get('threshold', '-')} ｜ 模式 {meta.get('mode', '-')} ｜ "
        f"生成 {meta.get('created_at', '-')}"
    )
    page = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>分镜表 - {html_lib.escape(video_name)}</title>
<style>
  body {{ font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;
         margin:20px;color:#1a1b1c;background:#faf9f6; }}
  h1 {{ font-size:19px;margin-bottom:4px; }}
  .meta {{ color:#6b7280;font-size:12.5px;margin-bottom:14px; }}
  table {{ border-collapse:collapse;width:100%;background:#fff;
          box-shadow:0 1px 3px rgba(0,0,0,.08); }}
  th,td {{ border:1px solid #e4e3dd;padding:7px;font-size:12.5px;
           vertical-align:top;text-align:left; }}
  th {{ background:#f0eee7;position:sticky;top:0;z-index:2; }}
  .no {{ text-align:center;font-weight:600;width:38px; }}
  .frame img {{ width:190px;border-radius:6px;display:block;background:#eee; }}
  .tc {{ white-space:nowrap; }} .to {{ color:#9ca3af;font-size:11.5px; }}
  .dur {{ text-align:right;white-space:nowrap; }}
  .lvl {{ text-align:center; }}
  .desc {{ min-width:200px; }} .desc:focus {{ outline:2px solid #5bafc7; }}
  .tip {{ font-size:12px;color:#9ca3af;margin-top:10px;line-height:1.6; }}
</style>
</head>
<body>
  <h1>分镜表：{html_lib.escape(video_name)}</h1>
  <div class="meta">{html_lib.escape(meta_line)}　｜　高清原图见同目录「关键帧」「运动图」文件夹</div>
  <table>
    <thead><tr>
      <th>镜号</th><th>关键帧</th><th>运动图</th><th>时间码</th><th>时长(s)</th>
      <th>机位</th><th>主体运动</th><th>强度</th><th>画面描述（可编辑）</th>
    </tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
  <div class="tip">
    描述列可直接点击填写（内容只保存在你本地浏览器）。<br>
    绿色箭头＝画面内物体运动，橙色大箭头＝摄影机运动，红色粗箭头＝主体整体方向。
  </div>
</body>
</html>"""
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(page)
    return out_path


# ---------- 提取信息.txt ----------

def export_info_txt(meta: dict, out_path: str):
    lines = [
        "=" * 50,
        " 分镜结果 · 提取信息",
        "=" * 50,
        "",
        f"影片：{meta.get('video_name', '')}",
        f"原始视频：{meta.get('video_path', '')}",
        f"提取时间：{meta.get('created_at', '')}",
        f"工具版本：{meta.get('version', '')}",
        "",
        "参数与结果：",
        f"  · 镜头切换灵敏度阈值 = {meta.get('threshold', '')}",
        f"  · 运行模式 = {meta.get('mode', '')}（隔帧 {meta.get('frame_skip', '')}，"
        f"光流宽 {meta.get('motion_width', '')}，每镜采样 {meta.get('motion_samples', '')} 帧）",
        f"  · 镜头数 = {meta.get('shot_count', '')}",
        f"  · 帧率 = {meta.get('fps', '')} fps",
        f"  · 总时长 ≈ {meta.get('total_duration', '')} 秒",
        "",
        "文件夹 / 文件说明：",
        "  · 关键帧\\   每个镜头一张高清代表帧（shot_0001.jpg …）",
        "  · 运动图\\   每个镜头一张运动箭头图（shot_0001_motion.jpg …）",
        "  · 分镜表.html   图文分镜本（内嵌缩略图，浏览器打开；高清原图在上面两个文件夹）",
        "  · 分镜表.csv    可用 Excel 打开的结构化总表",
        "  · 分镜表.md     Markdown 表格",
        "",
        "机位运动：固定机位 / 左摇·右摇 / 上仰·下俯 / 推近·拉远",
        "运动强度：无 / 弱 / 中 / 强（光流为参考结果，复杂画面可能有误差）",
        "",
        "提醒：电影画面与结果仅保留在本地，请勿上传到公开 GitHub（版权）。",
        "",
    ]
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return out_path

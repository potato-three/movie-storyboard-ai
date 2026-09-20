# -*- coding: utf-8 -*-
"""
exporter.py
===========
把镜头检测结果导出成三种格式：
1. CSV 表格      —— 方便用 Excel 打开、二次编辑
2. Markdown 表   —— 直接贴进 GitHub / 笔记
3. HTML 预览页   —— 浏览器打开能看到「关键帧 + 分镜表」的图文版
"""

import os
import csv
import base64
import html as html_lib


def export_csv(shots, out_path: str):
    """导出 CSV 分镜表。"""
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["镜号", "开始时间码", "结束时间码", "时长(秒)", "关键帧文件"])
        for s in shots:
            keyframe = os.path.basename(s["keyframe"]) if s.get("keyframe") else ""
            writer.writerow([
                s["shot_no"], s["start_tc"], s["end_tc"],
                s["duration"], keyframe
            ])
    return out_path


def export_markdown(shots, out_path: str, video_name: str = ""):
    """导出 Markdown 分镜表（关键帧用相对路径引用）。"""
    lines = []
    lines.append(f"# 分镜表：{video_name}\n")
    lines.append(f"共 **{len(shots)}** 个镜头。\n")
    lines.append("| 镜号 | 开始 | 结束 | 时长(s) | 关键帧 |")
    lines.append("|---|---|---|---|---|")
    for s in shots:
        if s.get("keyframe"):
            frame_dir = os.path.basename(os.path.dirname(s["keyframe"]))
            frame_file = os.path.basename(s["keyframe"])
            img = f"[查看]({frame_dir}/{frame_file})"
        else:
            img = "-"
        lines.append(
            f"| {s['shot_no']} | {s['start_tc']} | {s['end_tc']} "
            f"| {s['duration']} | {img} |"
        )
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return out_path


def export_html(shots, out_path: str, video_name: str = ""):
    """
    导出图文版 HTML 预览页（关键帧直接内嵌，单文件即可打开，方便分享）。
    """
    rows = []
    for s in shots:
        img_tag = ""
        if s.get("keyframe") and os.path.exists(s["keyframe"]):
            with open(s["keyframe"], "rb") as img_f:
                b64 = base64.b64encode(img_f.read()).decode("ascii")
            img_tag = f'<img src="data:image/jpeg;base64,{b64}" loading="lazy">'
        rows.append(f"""
        <tr>
          <td class="no">{s['shot_no']}</td>
          <td class="frame">{img_tag}</td>
          <td>{s['start_tc']}<br>→ {s['end_tc']}</td>
          <td>{s['duration']}</td>
          <td class="desc" contenteditable="true"></td>
        </tr>""")

    total_duration = round(sum(s["duration"] for s in shots), 2)
    page = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>分镜表 - {html_lib.escape(video_name)}</title>
<style>
  body {{ font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
         margin: 24px; color: #1a1b1c; background: #faf9f6; }}
  h1 {{ font-size: 20px; }}
  .meta {{ color: #6b7280; font-size: 13px; margin-bottom: 16px; }}
  table {{ border-collapse: collapse; width: 100%; background: #fff;
          box-shadow: 0 1px 3px rgba(0,0,0,.08); }}
  th, td {{ border: 1px solid #e4e3dd; padding: 8px; font-size: 13px;
           vertical-align: top; text-align: left; }}
  th {{ background: #f0eeE7; position: sticky; top: 0; }}
  .no {{ text-align: center; font-weight: 600; width: 40px; }}
  .frame img {{ width: 220px; border-radius: 6px; display: block; }}
  .desc {{ min-width: 240px; }}
  .desc:focus {{ outline: 2px solid #5bafc7; }}
  .tip {{ font-size: 12px; color: #9ca3af; margin-top: 8px; }}
</style>
</head>
<body>
  <h1>分镜表：{html_lib.escape(video_name)}</h1>
  <div class="meta">共 {len(shots)} 个镜头 ｜ 总时长 {total_duration} 秒
      ｜ 最后一列可直接点击填写画面描述（内容只保存在你本地浏览器）</div>
  <table>
    <thead><tr>
      <th>镜号</th><th>关键帧</th><th>时间码</th><th>时长(s)</th><th>画面描述（可编辑）</th>
    </tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
  <div class="tip">提示：这是自动切分结果，描述列留给你手动补充或后续接入 AI 自动生成。</div>
</body>
</html>"""

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(page)
    return out_path

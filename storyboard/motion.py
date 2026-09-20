# -*- coding: utf-8 -*-
"""
motion.py —— 镜头运动分析（OpenCV 光流，纯本地、免费）
=========================================================
对每个镜头：
  1. 镜头内均匀采样若干帧，缩放到较小尺寸（提速），转灰度
  2. 稀疏角点 + Lucas-Kanade 光流，RANSAC 估「全局仿射」= 摄影机运动
     · 全局内点在画面中分布足够广、且各帧对方向一致，才判为摄影机运动，
       否则视为「画面内物体在动」（避免纯色背景里一个小球横移被误判成摇镜）
  3. 主体运动方向优先用稀疏角点位移（对纯色/无纹理物体比稠密光流可靠）：
     判为摄影机运动时取「外点」（运动物体），否则取全部角点
  4. 稠密 Farneback 光流减摄影机运动，用于运动强度分级与箭头可视化
  5. 输出机位运动、主体方向、强度，并生成带箭头的运动示意图

注：光流是像素级估算，结果为「参考」，复杂特效/遮挡可能有误差。
"""

import os
import numpy as np
import cv2

from storyboard.detector import safe_imwrite

# 经验阈值（可按实测调整）
PAN_THR = 0.06     # 整镜平移占画面宽/高比例，超过才判摇/俯仰
ZOOM_THR = 0.04    # 整镜累计缩放比例
COVER_MIN = 0.35   # 全局内点包围盒占画面面积比例，超过才信任摄影机运动
CONS_MIN = 0.60    # 各帧对方向一致率，低于则不判该分量
DISP_W = 960       # 运动示意图输出宽
GRID_STEP = 34     # 残差箭头网格间距


def _resize_to_width(frame, width):
    h, w = frame.shape[:2]
    if w == width:
        return frame
    nh = max(1, int(round(h * width / float(w))))
    return cv2.resize(frame, (width, nh), interpolation=cv2.INTER_AREA)


def _compass(dx, dy):
    """把向量翻译成八方位中文（返回不含"向"的词，如 向右/右上/向左）。"""
    if abs(dx) < 1e-6 and abs(dy) < 1e-6:
        return ""
    ang = np.degrees(np.arctan2(-dy, dx))  # 屏幕 y 向下，取负让上为 +90
    dirs = ["向右", "右上", "向上", "左上", "向左", "左下", "向下", "右下"]
    return dirs[int(np.round((ang % 360) / 45.0)) % 8]


def _put_cn(img, text, org, scale=1.0, color=(255, 255, 255), thickness=2):
    """用 PIL 写中文（OpenCV 原生不支持）；无 PIL 时退回 ASCII。"""
    try:
        from PIL import Image, ImageDraw, ImageFont
        font = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", int(22 * scale))
        pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        ImageDraw.Draw(pil).text(org, text, font=font,
                                 fill=(color[2], color[1], color[0]))
        return cv2.cvtColor(np.asarray(pil), cv2.COLOR_RGB2BGR)
    except Exception:
        cv2.putText(img, text.encode("ascii", "ignore").decode(),
                    org, cv2.FONT_HERSHEY_SIMPLEX, 0.7 * scale, color, thickness)
        return img


def analyze_shot_motion(cap, fps, shot: dict, base_frame, out_path: str,
                        work_width: int = 480, n_samples: int = 12) -> dict:
    result = {
        "camera_motion": "固定机位", "camera_code": "static",
        "subject_motion": "几乎静止", "motion_level": "无", "motion_image": "",
    }
    sf, ef = shot["start_frame"], shot["end_frame"]
    if ef - sf < 2:
        _draw_and_save(base_frame, None, (0, 0), result, out_path, 0, 0, 0)
        result["motion_image"] = out_path if os.path.exists(out_path) else ""
        return result

    idxs = np.linspace(sf, max(ef - 1, sf + 1), n_samples).astype(int)
    grays, frames = [], []
    for fi in idxs:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(fi))
        ok, fr = cap.read()
        if not ok or fr is None:
            continue
        fr = _resize_to_width(fr, work_width)
        frames.append(fr)
        grays.append(cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY))
    if len(frames) < 2:
        _draw_and_save(base_frame, None, (0, 0), result, out_path, 0, 0, 0)
        result["motion_image"] = out_path if os.path.exists(out_path) else ""
        return result

    h, w = grays[0].shape
    npair = len(grays) - 1

    # ---- 1) 稀疏光流 ----
    feat = dict(maxCorners=300, qualityLevel=0.2, minDistance=12, blockSize=9)
    lk = dict(winSize=(17, 17), maxLevel=3,
              criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 20, 0.03))
    p0 = cv2.goodFeaturesToTrack(grays[0], mask=None, **feat)

    # 暗场（黑屏/淡入淡出）或纹理极少（纯色/平坦画面）：没有可靠运动可测，判静止
    mean_lum = float(np.mean(grays[len(grays) // 2]))
    n_corner = 0 if p0 is None else len(p0)
    if mean_lum < 22 or n_corner < 12:
        _draw_and_save(frames[0], None, (0, 0), result, out_path, 0, 0, 0)
        result["motion_image"] = out_path if os.path.exists(out_path) else ""
        return result

    pairs = []          # 全局（相机）仿射统计
    all_motion = []     # 每对全部角点的位移中位（相邻采样帧，像素）
    if p0 is not None and len(p0) >= 6:
        prev_g, prev_p = grays[0], p0
        for g in grays[1:]:
            nxt, st, _ = cv2.calcOpticalFlowPyrLK(prev_g, g, prev_p, None, **lk)
            back, st2, _ = cv2.calcOpticalFlowPyrLK(g, prev_g, nxt, None, **lk)
            if nxt is None or back is None:
                prev_g = g
                continue
            okm = (st.ravel() == 1) & (st2.ravel() == 1)
            a0, b0, bb = prev_p[okm], nxt[okm], back[okm]
            err = np.abs(a0 - bb).reshape(-1, 2).max(axis=1)
            good = err < 1.5
            a, b = a0[good], b0[good]
            if len(a) >= 6:
                d = (b - a).reshape(-1, 2)
                all_motion.append((float(np.median(d[:, 0])),
                                   float(np.median(d[:, 1])), len(d)))
                M, inliers = cv2.estimateAffinePartial2D(
                    a, b, method=cv2.RANSAC, ransacReprojThreshold=2.5)
                if M is not None and inliers is not None and len(inliers) >= 6:
                    inl = inliers.ravel().astype(bool)
                    sc = (np.hypot(M[0, 0], M[0, 1]) +
                          np.hypot(M[1, 0], M[1, 1])) / 2.0
                    pa = a[inl].reshape(-1, 2)
                    out_d = d[~inl]
                    odx = float(np.median(out_d[:, 0])) if len(out_d) >= 3 else np.nan
                    ody = float(np.median(out_d[:, 1])) if len(out_d) >= 3 else np.nan
                    pairs.append(dict(
                        tx=float(M[0, 2]) / w, ty=float(M[1, 2]) / h,
                        ls=float(np.log(max(sc, 1e-6))),
                        xs=pa[:, 0], ys=pa[:, 1],
                        odx=odx, ody=ody, nout=int(len(out_d))))
            # 用本帧检测的角点作为下一轮起点，避免点逐渐丢失
            prev_p = cv2.goodFeaturesToTrack(g, mask=None, **feat)
            if prev_p is None or len(prev_p) < 6:
                prev_p = nxt
            prev_g = g

    # ---- 2) 摄影机运动判定 ----
    cam_dx = cam_dy = 0.0
    cam_zoom = 0
    bg_scale, bg_txpx, bg_typx = 1.0, 0.0, 0.0
    trust_cam = False
    if pairs:
        covers = []
        for p in pairs:
            x0, x1 = np.percentile(p["xs"], [5, 95])
            y0, y1 = np.percentile(p["ys"], [5, 95])
            covers.append((x1 - x0) * (y1 - y0) / float(w * h))
        if float(np.median(covers)) >= COVER_MIN:
            trust_cam = True
            txs = np.array([p["tx"] for p in pairs])
            tys = np.array([p["ty"] for p in pairs])
            lss = np.array([p["ls"] for p in pairs])
            mtx, mty, mls = np.median(txs), np.median(tys), np.median(lss)
            tot_tx, tot_ty = mtx * npair, mty * npair
            zoom_total = float(np.exp(mls * npair))

            def _consist(vals, med):
                if med == 0:
                    return 0.0
                return float(np.mean((np.sign(vals) == np.sign(med)) &
                                     (np.abs(vals) >= 0.5 * abs(med))))

            if abs(tot_tx) > PAN_THR and _consist(txs, mtx) >= CONS_MIN:
                cam_dx = tot_tx
            if abs(tot_ty) > PAN_THR and _consist(tys, mty) >= CONS_MIN:
                cam_dy = tot_ty
            if abs(zoom_total - 1) > ZOOM_THR and _consist(lss, mls) >= CONS_MIN:
                cam_zoom = 1 if zoom_total > 1 else -1
            bg_scale = zoom_total
            bg_txpx = tot_tx * w
            bg_typx = tot_ty * h

    parts, code = [], "static"
    if cam_dx < 0:
        parts.append("右摇"); code = "pan_right"
    elif cam_dx > 0:
        parts.append("左摇"); code = "pan_left"
    if cam_dy < 0:
        parts.append("下俯"); code = code if code != "static" else "tilt_down"
    elif cam_dy > 0:
        parts.append("上仰"); code = code if code != "static" else "tilt_up"
    if cam_zoom == 1:
        parts.append("推近"); code = "zoom_in" if code == "static" else code + "+zoom_in"
    elif cam_zoom == -1:
        parts.append("拉远"); code = "zoom_out" if code == "static" else code + "+zoom_out"
    if parts:
        result["camera_motion"] = "＋".join(parts)
        result["camera_code"] = code

    # ---- 3) 主体方向：优先稀疏角点 ----
    sdx = sdy = 0.0
    sparse_ok = False
    if trust_cam:
        ox = [p["odx"] for p in pairs if not np.isnan(p["odx"])]
        oy = [p["ody"] for p in pairs if not np.isnan(p["ody"])]
        if len(ox) >= 2:
            sdx, sdy = float(np.median(ox)), float(np.median(oy))
            sparse_ok = True
    elif all_motion:
        sdx = float(np.median([m[0] for m in all_motion]))
        sdy = float(np.median([m[1] for m in all_motion]))
        sparse_ok = True

    # ---- 4) 稠密残差：运动强度 + 箭头可视化 ----
    flow = cv2.calcOpticalFlowFarneback(
        grays[0], grays[-1], None, 0.5, 3, 21, 3, 5, 1.1, 0)
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    bg = np.stack([(bg_scale - 1.0) * xs + bg_txpx,
                   (bg_scale - 1.0) * ys + bg_typx], axis=-1)
    residual = flow - bg
    mg = int(0.1 * w)
    inner = np.zeros((h, w), bool)
    inner[mg:h - mg, mg:w - mg] = True
    mag = np.hypot(residual[..., 0], residual[..., 1])
    mmask = inner & (mag > max(0.5, 0.004 * w))

    level = "无"
    if mmask.sum() > 30:
        med_v = float(np.median(mag[mmask])) / w
        level = ("无" if med_v < 0.0015 else "弱" if med_v < 0.006
                 else "中" if med_v < 0.015 else "强")

    # 最终方向向量
    vx = vy = 0.0
    if sparse_ok and np.hypot(sdx, sdy) > 0.3:
        vx, vy = sdx, sdy
        if level == "无":  # 稠密没测到（常见于纯色物体），用稀疏位移兜底分级
            span = np.hypot(sdx, sdy) * npair / w
            level = ("弱" if span < 0.12 else "中" if span < 0.30 else "强")
    elif level != "无":
        vx = float(np.median(residual[..., 0][mmask]))
        vy = float(np.median(residual[..., 1][mmask]))

    d = _compass(vx, vy)
    if d and level != "无":
        result["subject_motion"] = ("主体" + d) if d.startswith("向") else ("主体向" + d)
        result["motion_level"] = level
    else:
        result["subject_motion"] = "几乎静止"
        result["motion_level"] = "无"

    _draw_and_save(frames[0], residual, (vx, vy), result, out_path,
                   cam_dx, cam_dy, cam_zoom)
    result["motion_image"] = out_path if os.path.exists(out_path) else ""
    return result


# ---------------- 运动示意图绘制 ----------------

def _draw_zoom_marks(img, cam_zoom):
    """推近=四角箭头指向画面中心；拉远=指向四角。"""
    if cam_zoom == 0:
        return
    H, W = img.shape[:2]
    m, L = 42, 30
    cx, cy = W / 2.0, H / 2.0
    orange = (60, 165, 230)
    for (x, y) in [(m, m), (W - m, m), (m, H - m), (W - m, H - m)]:
        dx, dy = cx - x, cy - y
        n = np.hypot(dx, dy) or 1.0
        sign = 1.0 if cam_zoom == 1 else -1.0
        cv2.arrowedLine(img, (int(x), int(y)),
                        (int(x + sign * dx / n * L), int(y + sign * dy / n * L)),
                        orange, 3, tipLength=0.4)


def _draw_and_save(base_small, residual, subj_vec, result, out_path,
                   cam_dx=0.0, cam_dy=0.0, cam_zoom=0):
    disp = _resize_to_width(base_small, DISP_W)
    dh, dw = disp.shape[:2]
    sh, sw = base_small.shape[:2]
    sx, sy = dw / float(sw), dh / float(sh)

    if residual is not None:
        rh, rw = residual.shape[:2]
        for y in range(GRID_STEP, rh - GRID_STEP, GRID_STEP):
            for x in range(GRID_STEP, rw - GRID_STEP, GRID_STEP):
                dx, dy = residual[y, x]
                if np.hypot(dx, dy) > max(0.6, 0.005 * rw):
                    cv2.arrowedLine(disp, (int(x * sx), int(y * sy)),
                                    (int((x + dx) * sx), int((y + dy) * sy)),
                                    (90, 200, 90), 1, tipLength=0.3)

    if abs(cam_dx) > 0 or abs(cam_dy) > 0:
        ax = int(np.clip(cam_dx, -1, 1) * dw * 0.22)
        ay = int(np.clip(cam_dy, -1, 1) * dh * 0.22)
        cv2.arrowedLine(disp, (dw // 2 - ax // 2, dh // 2 - ay // 2),
                        (dw // 2 + ax // 2, dh // 2 + ay // 2),
                        (60, 165, 230), 6, tipLength=0.25)
    if cam_zoom != 0:
        _draw_zoom_marks(disp, cam_zoom)

    if subj_vec is not None and (abs(subj_vec[0]) > 0 or abs(subj_vec[1]) > 0):
        vx, vy = subj_vec
        n = np.hypot(vx, vy) or 1.0
        L = min(dw, dh) * 0.16
        cv2.arrowedLine(disp, (int(dw * 0.5), int(dh * 0.62)),
                        (int(dw * 0.5 + vx / n * L), int(dh * 0.62 + vy / n * L)),
                        (70, 70, 235), 5, tipLength=0.3)

    bar = np.zeros((46, dw, 3), dtype=np.uint8)
    bar[:] = (35, 40, 55)
    disp = np.vstack([bar, disp])
    txt = (f"机位：{result['camera_motion']}　|　{result['subject_motion']}"
           f"（强度：{result['motion_level']}）")
    disp = _put_cn(disp, txt, (12, 9), scale=1.05)
    safe_imwrite(out_path, disp, jpeg_quality=90)

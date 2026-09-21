# AGENTS.md — 给接手本项目的 AI 助手 / 未来的自己

> 本文件是项目的**跨会话记忆**。开始任何工作前，请先完整读完本文件和 `README.md`。
> `README.md` 面向普通使用者 / GitHub 访客；本文件记录环境、进度、踩过的坑和下一步。
> 本项目在 GitHub 公开，**不要**写入任何 API 密钥、密码或个人隐私。

## 项目是什么（一句话）
电影分镜拆解 AI 工具：视频 → 自动切镜头(PySceneDetect) → 每镜头关键帧(OpenCV) → **光流运动分析（机位 pan/tilt/zoom、画面主体方向、运动强度，并画运动箭头图）** → 导出 CSV / Markdown / 图文 HTML 分镜本；Gradio 网页（流式进度＋镜头浏览器）和命令行双入口。是用户「AI 视频创作工作流」第一阶段：分镜 → 角色资产 → 图生视频 → 后期。

## 使用者背景（决定交付方式）
- 编程 / Git **零基础**，即将赴香港城市大学就读 MScAIB（商业人工智能）硕士。
- 需要**手把手、步骤化、双击即用**的成品；全程中文；对瞎编 / 不准确零容忍；坚持先听方案、自己拍板后再动手；外部网站（如 GitHub）坚持自己操作，不要代点。
- 机器：Windows + RTX 4060 笔记本。项目放在 **F 盘**（剩余空间最大，约 338GB）。

## 关键环境（极易踩坑，务必照用）
- **运行和双击一律使用系统 Python：`D:\python\python.exe`（Python 3.14.7）。**
  本机另有一个 Doubao 工具沙箱 Python，在 PATH 中排更前；装进沙箱 Python **对双击运行无效**。装依赖必须显式：
  `D:\python\python.exe -m pip install -r requirements.txt -i https://mirrors.huaweicloud.com/repository/pypi/simple`
- 已装：gradio 6.28.0、scenedetect 0.7.1、opencv-python 5.0.0.93、pandas 3.0.1、numpy 2.4.3、pillow 12.3.0（PIL 用于运动图写中文，requirements 里是 pillow）。
- Git 2.55 在 `C:\Program Files\Git\cmd\git.exe`，credential.helper=manager。
- 两个启动 `.bat`（**GBK 编码**）写死 `"D:\python\python.exe" app.py` 并 `cd /d` 到项目；编辑必须保持 GBK，否则中文乱码。

## 数据目录（v0.2 起文件全部收口，不再有 input/output）
全部基于 `PROJECT_ROOT`（`config.py` 用脚本自身位置推导，**不写死盘符**；项目在 F 盘所以数据天然在 F 盘，别人 clone 到任意目录也能用）：
- `原始视频/`：原片放这里，网页下拉自动列出（`.gitignore` 忽略，不上传）。
- `分镜结果/`：每次提取一个子文件夹 `影片名_分镜结果_YYYYMMDD_HHMM/`（`.gitignore` 忽略）。内含：
  - `关键帧/shot_0001.jpg …`（每镜头中间帧，原图分辨率）
  - `运动图/shot_0001_motion.jpg …`（宽 960，叠运动箭头）
  - `分镜表.html`（内嵌压缩缩略图，瘦身后约 0.1MB 级；旧版内嵌原图曾达 484MB）
  - `分镜表.csv`（utf-8-sig，Excel 直接打开不乱码）、`分镜表.md`、`提取信息.txt`
- `.gradio_tmp/`：Gradio 网页运行缓存（上传文件、输出文件的服务端副本）。**已在 `import gradio` 之前用环境变量 `GRADIO_TEMP_DIR` 指到这里**，否则默认落 C 盘用户 Temp（`.gitignore` 忽略；可随时清空，服务运行中被占用的文件除外）。
- 桌面有 4 个快捷方式：电影分镜提取工具 / 分镜素材-把视频放这里 / 分镜结果-在这里查询 / 分镜工具-公网分享给朋友。

## 常用命令（PowerShell，不支持 `&&`，用 `;`）
- 网页：双击桌面快捷方式，或 `cd F:\AIProjects\movie-storyboard-ai ; D:\python\python.exe app.py` → http://127.0.0.1:7860 （绑定 0.0.0.0，局域网 IP 192.168.1.110）。
- 命令行：`D:\python\python.exe main.py`（无参数处理 `原始视频/` 里第一个视频）
  - `-t/--threshold 25` 切镜阈值；`-m/--mode 精确|平衡|快速`（默认平衡）；`--no-motion` 跳过运动分析；可直接传视频路径。
- 刷新 git PATH：`$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")`

## 架构（v0.2）
- `main.py` 命令行入口（argparse，对接 pipeline，`\r` 打印百分比）。
- `app.py` Gradio 网页：下拉选片（`config.list_raw_videos`）＋刷新＋临时上传；阈值滑块；三档 radio；**生成器流式**（逐镜头 yield，状态行＋ `gr.Progress`）；镜头浏览器（大图 viewer＋关键帧/运动图 radio＋定位滑块＋上一/下一镜＋gallery 总览 select 联动）；Dataframe 7 列；打开结果文件夹按钮（`os.startfile`）；HTML 用**单个** `gr.File`（曾误放两个导致下载区重复显示）。
- `storyboard/config.py`：路径常量、结果文件/目录名、`MODES` 三档参数、`VIDEO_EXTS`、`list_raw_videos/raw_video_path`；import 即 makedirs。
- `storyboard/detector.py`：`detect_shots(video_path,threshold,frame_skip,min_scene_len=15,progress)`（先 open 预检取 fps/总帧数/读一帧→close→再 open 检测；callback 推进度；整片无切换兜底为 1 镜头）、`format_timecode`、`safe_imwrite`(imencode+tofile)、`read_image_cn`、`close_video`。
- `storyboard/motion.py`：`analyze_shot_motion(cap,fps,shot,base_frame,out_path,work_width,n_samples)` → 返回 `camera_motion/camera_code/subject_motion/motion_level/motion_image`。
- `storyboard/pipeline.py`：`run_pipeline(...)` **生成器**，依次 yield status/shot/done；单 cap 句柄逐镜头 seek 中帧出关键帧＋运动分析；失败 `_cleanup_empty` 删半成品目录；meta 写入提取信息。`safe_stem` 限 60 字符。
- `storyboard/exporter.py`：`_thumb_b64(width=400,quality=58)`（HTML 瘦身关键）、`export_csv`(9 列 utf-8-sig)、`export_markdown`(正斜杠相对链接)、`export_html`(内嵌缩略图、9 列、sticky 表头、可编辑描述列)、`export_info_txt`。
- `storyboard/__init__.py`：统一导出。

## 运动算法（motion.py v3，已用合成片＋真实动画正片目视验证）
镜头内均匀采样 n 帧 → 缩到 work_width 转灰：
1. `goodFeaturesToTrack`(300 角点,quality 0.2,minDist 12) ＋ Lucas-Kanade(win17,level3) 双向回查(误差<1.5px)，每轮重新检测角点防丢失。
2. `estimateAffinePartial2D`(RANSAC 2.5) 估全局仿射；**仅当内点包围盒面积占比中位数 ≥0.35 且各帧对方向一致率 ≥0.60 才信任为摄影机运动**（pan：整镜归一化位移 >0.06；zoom：|zoom-1|>0.04），否则按物体运动处理。
3. **主体方向优先用稀疏角点 LK 位移的中位数**（信任相机时取 RANSAC 外点中位，不信任时取全部角点中位）；稠密 Farneback 光流只用于强度分级和画绿色残差箭头；相机变换只在信任时按整段累计扣除。
4. 强度（残差中位速度/画面宽）：无 <0.0015 / 弱 <0.006 / 中 <0.015 / 强；稀疏兜底（整镜位移占宽）：无 <0.12 / 中 <0.30 / 强。
5. 运动图宽 960：绿=残差网格箭头，橙=相机大箭头＋**四角 zoom 标记（推近四角向内、拉远向外）**，红=主体粗箭头；PIL 用 `C:\Windows\Fonts\msyh.ttc` 画中文顶条（找不到字体会回退 ASCII）。
- 顶部常量均为**经验初值**（PAN_THR/ZOOM_THR/COVER_MIN/CONS_MIN/强度阈值），要微调先看 motion.py 顶部。
- 暗场保护：采样中帧平均亮度 <22 或角点 <12，直接判固定机位/几乎静止/无（解决片头黑屏、SONY/Netflix LOGO 被编码噪声误判运动）。

## 已踩过的坑（不要重走）
- **PySceneDetect 0.7.1**：`probe.frame_rate` 是 `Fraction`，`int/Fraction`、`round(Fraction,3)` 仍返回 Fraction（时长列会显示成 219/125 这种分数）→ 必须 `fps=float(probe.frame_rate or 25.0)`。关闭视频用 `video.capture.release()`（没有 close()，不 release 会锁住文件）。`SceneManager.detect_scenes(video, frame_skip=, callback=fn)`；ContentDetector 默认 `filter_mode=MERGE` 会合并闪光灯。
- **LK 特征点 shape 是 (N,1,2)**，取坐标前必须 `.reshape(-1,2)`，否则报 *index 1 is out of bounds for axis 1 with size 1*。
- **纯色/无纹理物体（如白球）稠密光流方向会判反**：物体新露出/刚离开的边界产生反向杂流，位移大时反向像素占多数。结论：主体方向信稀疏角点（集中在物体边缘、可靠），稠密光流只算强度/画残差。
- 拼接方向词出现「主体向**向**左」：`_compass` 返回值已含「向」，拼接时按 startswith("向") 区分。
- **Gradio 6.x**：`launch()` 不接受 `show_api`；`theme=` 放 `launch()`；`gr.Slider(1,1)` 初始化报 *minimum must be less than maximum* → 初始给 (1,2)，处理后再 `update(maximum=N)`；生成器多次 yield 即流式，未变输出用 `gr.skip()`；State 不出现在 view_api。
- **`GRADIO_TEMP_DIR` 必须在 `import gradio` 之前设置**才生效。Gradio 6 即使 `launch(allowed_paths=...)`，仍会把 gr.Image/gr.File 输出复制一份到 temp 目录再给 URL（allowed_paths 主要管能否访问）；把 temp 指到 F 盘即可，gallery 是压缩缩略图、体积很小（5 镜头仅约 0.44MB）。
- 用 `gradio_client` 做接口测试时，**客户端**会把返回文件下载到系统 Temp（C:\Users\...\AppData\Local\Temp\gradio），这是测试工具行为，真实浏览器不这样（浏览器走 /file URL，下载走浏览器下载目录）；测完清掉该缓存。
- 上传组件用 `gr.File(type="filepath")`，不能用 `gr.Video`（后者浏览器端校验可播放性，MKV/H.265/mp4v 会被拦）。
- OpenCV 在 Windows **中文路径** imwrite/imread 失败：imencode+tofile / np.fromfile+imdecode（detector 已封装）。
- PowerShell 里 `curl` 是 Invoke-WebRequest 别名，要用 `curl.exe`。
- Gradio `share=True` 公网隧道在本机网络创建失败；公网部署走 **Hugging Face Spaces**。
- 改完代码要确认 7860 跑的是新进程（先 kill 命令行含 app.py 的 python.exe 再启动）；排查组件看 /config 或 gradio_client 的 view_api。
- **Gradio Slider 事件（v0.2.2 修正）**：`.change` 也会被后端 `gr.update(value=...)` 触发。旧版 change+release 在提取中读到尚未写入的 browser_state=[]，会把新大图清空。现在只绑定 `.input`，主流程更新滑块不触发浏览；空数据/busy 返回 skip。所有手动浏览事件 `show_progress='hidden'`，主提取的加载指示只放 `progress_area`。不要恢复 change+release 双绑。
- **Gradio 6 的 `gr.HTML` 经 innerHTML 插入，里面的 `<script>` 不执行**。要注入 CSS/JS：`gr.HTML(head="<style>…</style>", js_on_load="<JS字符串>")`；js_on_load 里注册的全局监听用 `window.__xxx` 标志防重复。
- **滑块滚轮会让镜头号飞速跳变、大图狂闪**：js_on_load 中在 document 的 capture 阶段监听 wheel，`target` 是 `input[type=range]` 时 `preventDefault()`（passive:false）。
- **`gr.Gallery` 点缩略图默认弹 lightbox 放大层**；要“点一张就在上方跳转”，设 `allow_preview=False`。
- browser-use 自动化的合成指针事件对原生 range 的拖手柄/点轨道**不稳定（常点不动）**；验证滑块优先用数字框输入、键盘方向键、缩略图、上一/下一镜按钮，不要依赖 `bu.drag`。
- **Seedance 是「文/图→视频」生成模型，不能做「视频→文字」理解**。视频理解用多模态视觉模型：智谱 GLM-4.6V-Flash / GLM-4.1V-Thinking-Flash（bigmodel.cn，有免费额度），备用阿里 Qwen3-VL-Flash（约输入 0.367/输出 2.936 元每百万 token，2026-09 查）。
- ContentDetector 对 dissolve（淡入淡出）较弱：横跨 LOGO→正片的长 dissolve 可能漏切成一个长镜头；正片硬切为主，影响小。

## 版本路线 / 进度
- [x] **v0.1** 镜头切分＋关键帧＋CSV/MD/HTML＋Gradio＋桌面快捷方式（已上线 GitHub）。
- [x] **v0.2（2026-09-20）**：文件全部收口到 `原始视频/`、`分镜结果/`（F 盘）；光流运动分析（机位/主体方向/强度＋运动箭头图）；三档速度（精确/平衡/快速）；网页流式提取＋进度条；镜头浏览器（滑块/上一镜下一镜/gallery 联动/关键帧-运动图切换）；HTML 瘦身（内嵌 400px q58 缩略图，484MB→约 0.1MB）；新增 config.py/motion.py/pipeline.py，重写 detector/exporter/main/app/__init__。命令行、gradio_client、真实浏览器均已端到端实测。
- [x] **v0.2.1（2026-09-21）镜头浏览器平滑预览**：大图改深色播放器底＋新图柔和淡入（消除换 src 瞬间白屏“闪眼”）；滑块 change+release 双绑＋`shown_state` 去重（拖动松手才加载、数字框/键盘跳转取值正确、相同镜头不重复渲染）；禁用滑块滚轮改值；gallery 关闭放大层、点击即跳转。数字框跳转、缩略图、关键帧/运动图、上一/下一镜、滚轮锁定、深色底淡入均已浏览器实测。
- [ ] **M2 线稿简图**：关键帧自动转分镜简笔画（本地 XDoG/Canny 免费打底，可选 AI 重绘）。
- [ ] **M3 AI 描述＋提示词**：接 GLM-4.6V/4.1V（用户需自己注册 bigmodel.cn 免费 Key；Key 放本地 `.env` 并确保 .gitignore，绝不入库）。把关键帧＋客观运动数据一起喂，输出每镜头中文描述和图生视频提示词。
- [ ] 之后：角色资产（AI 三视图/锚点图为主线，Tripo3D/Meshy＋Blender 3D 为支线）→ 图生视频（可灵/Seedance/Veo）→ 动态一致性、色调、纹理真实度 → 后期。
- [ ] 部署 Hugging Face Spaces 永久公网 demo。

## Git / 发布状态
- 远程：https://github.com/potato-three/movie-storyboard-ai （Public，账号 `potato-three`，main，目前只有 v0.1 一个提交，短 hash 45475ff，网页拖拽上传；`.gitignore` 当时漏传）。
- 本地 F 盘 `git init`+`git add` 过但**从未 commit**、user.name/email 未配，本地与远程是两套历史。首次命令行同步前：配身份 → 关联远程 → `git pull --rebase origin main`（或重新 clone）。
- v0.2 待同步：新增 `storyboard/config.py`、`storyboard/motion.py`、`storyboard/pipeline.py`；更新 `storyboard/detector.py`、`storyboard/exporter.py`、`storyboard/__init__.py`、`main.py`、`app.py`、`.gitignore`、`README.md`、`AGENTS.md`。
- 用户偏好自己用 GitHub **网页拖拽**上传（电影文件、`原始视频/`、`分镜结果/` 被 .gitignore 忽略，不会也不应上传——版权＋体积）。
- `.gitignore` 忽略：原始视频/、分镜结果/、.gradio_tmp/、.gradio/、__pycache__/、.env、临时脚本。

## 给接手 AI 的工作约定

### v0.2.2 防闪烁修复（2026-09-21）

- 旧版动画还有一个实质问题：Python 普通三引号转义破坏了 JS 正则，`node --check` 报语法错误。动画已移到 `web/preview.js`，样式在 `web/preview.css`，**两者必须随 app.py 一起分发**。
- 大图改用 Gradio 6.28 `HTML` 的常量模板＋`watch('value')`。固定双 img，隐藏层 decode 成功才叠化平移；加载失败保留旧图；字幕与完成解码的图同步提交。支持减少动态效果设置。
- `storyboard/preview.py` 用 Pillow 生成最大 960×640 的网页预览、24 项 LRU 缓存；通过 JSON/data URI 发送，不修改导出原图。提取每秒最多发一次大图，缩略图每两秒发送快照，最后一镜强制补齐；前端只保留最新待显示请求，自动预览每次显示后至少停留一秒。
- 处理期间禁用手动浏览，完成后开放；主流程、滑块、切图、上下镜和 Gallery 共享串行事件组，避免相互覆盖。每次任务有独立 run_id；新任务等待首张图期间保留旧图并明确提示。完成后不跳回第一镜。
- 单元测试：`D:\python\python.exe -m unittest discover -s tests -v`。覆盖空状态/忙碌/去重、不存在预览、事件绑定及独立进度、100 镜快流限速与全量结果、异常后解锁。
- 验收：系统 Python 命令行 demo_test.mp4 5 镜导出成功；浏览器真实 pipeline 跑 48 镜合成片并保存全量结果，逐帧 DOM 监测未见大图清空或容器/已有缩略图重建。数字框、上下镜、关键帧/运动图、Gallery 定位、快速输入最后落点均通过。未以此声称完整长片逐帧验收。
- 补充验收：测试专用入口每 50ms 推入一张、合计 40 张，前端合并到最后一张；注入无法解码的 JPEG 后旧图和字幕保留，重新提取 48 镜成功恢复。该浏览器会话逐帧 DOM 监测 27,540 次，空白帧/容器重建/已有首张缩略图重建均为 0（含静止时段，并非 27,540 张镜头）。测试专用入口与监测器不进入正式程序。新增缺失关键帧时 Gallery 序号映射测试，共 6 项单元测试通过。
- 桌面快捷方式指向本项目的 `启动分镜工具.bat`，BAT 再启动本目录 app.py；无须另建快捷方式或修改 GBK BAT。源码变动需退出旧服务后重新双击启动，单纯刷新网页不会重新加载 Python 源码。
- 改动后必须用**系统 Python** 实测：命令行跑 demo_test.mp4，必要时起服务用 gradio_client 调 `/process_video`，并用浏览器实际点一遍（滑块、关键帧/运动图切换、gallery 联动、打开文件夹），不要只看代码。
- 交付优先「双击即用」；新增依赖同步 `requirements.txt` 并装进 `D:\python\python.exe`。
- 每次重要进展更新本文件；外部事实（API/价格/接口）现查现引，不凭记忆。
- 跨会话开场白建议：「请先读取 F:\AIProjects\movie-storyboard-ai\AGENTS.md 和 README.md，我们继续做电影分镜项目。我编程零基础，请全程中文、步骤化指导。」

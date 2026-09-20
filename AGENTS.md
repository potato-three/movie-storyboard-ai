# AGENTS.md — 给接手本项目的 AI 助手 / 未来的自己

> 本文件是项目的**跨会话记忆**。开始任何工作前，请先完整读完本文件和 `README.md`。
> `README.md` 面向普通使用者；本文件记录环境、进度、踩过的坑和下一步。
> 本项目计划在 GitHub 公开，**不要**在此写入任何 API 密钥、密码或个人隐私。

## 项目是什么（一句话）
电影分镜拆解 AI 工具：上传视频 → 自动切镜头(PySceneDetect) → 每镜头提取关键帧(OpenCV) → 导出 CSV / Markdown / 图文 HTML 分镜本；提供 Gradio 网页和命令行双入口。是用户「AI 视频创作工作流」的第一阶段：分镜 → 角色资产 → 图生视频 → 后期。

## 使用者背景（决定交付方式）
- 编程 / Git **零基础**，即将赴香港城市大学就读 MScAIB（商业人工智能）硕士。
- 需要**手把手、步骤化、双击即用**的成品；全程中文；对瞎编 / 不准确零容忍。
- 机器：Windows + RTX 4060 笔记本。项目刻意放在 **F 盘**（剩余空间最大）。

## 关键环境（极易踩坑，务必照用）
- **运行和双击一律使用系统 Python：`D:\python\python.exe`（Python 3.14）。**
  本机另有一个 Doubao 工具沙箱 Python，在 PATH 中排在更前面；把依赖装进沙箱 Python **对双击运行无效**。装依赖必须显式：
  `D:\python\python.exe -m pip install -r requirements.txt`
- pip 镜像已配华为云：`https://mirrors.huaweicloud.com/repository/pypi/simple/`
- 已装入系统 Python：gradio 6.28、scenedetect 0.7.1、opencv-python 5.0、pandas、numpy。
- Git 2.55 已用 winget 安装。新开 PowerShell 若提示找不到 git，先刷新 PATH（命令见下）。
- 两个启动 `.bat`（**GBK 编码**）已写死 `D:\python\python.exe`；编辑 .bat 必须保持 GBK，否则中文乱码。

## 常用命令（PowerShell，注意不支持 `&&`，用 `;`）
- 启动网页：双击桌面「电影分镜提取工具」，或
  `cd F:\AIProjects\movie-storyboard-ai ; D:\python\python.exe app.py`
  → http://127.0.0.1:7860 ；已绑定 0.0.0.0，同一 WiFi 下可用 `http://局域网IP:7860`。
- 命令行批处理：`D:\python\python.exe main.py`（无参数自动处理 input/ 首个视频；`-t` 阈值，`-o` 输出）。
- 刷新 git 的 PATH：
  `$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")`

## 已踩过的坑（不要重走）
- **Gradio 6.x**：`launch()` 不接受 `show_api`；`theme=` 要放在 `launch()`，不能放 `Blocks()`。
- **上传组件必须用 `gr.File(type="filepath")`，不能用 `gr.Video`**：gr.Video 会在浏览器端校验「能否播放」，MKV / H.265 / OpenCV 写出的 mp4v 都会被拦截（报 *Video not playable*）。gr.File 不做播放校验，交给后端 OpenCV（自带 FFmpeg）解码即可。
- OpenCV 在 Windows **中文路径**下 `imwrite/imread` 会失败：用 `cv2.imencode` + `ndarray.tofile`（`detector.safe_imwrite` 已封装）。
- PowerShell 里 `curl` 是 `Invoke-WebRequest` 别名，要用 `curl.exe`。
- Gradio 官方 `share=True` 公网隧道在本机网络创建失败（*Could not create share link*）。要公网访问请部署 **Hugging Face Spaces**，不要依赖 gradio.live。
- 改完代码要确认 7860 端口跑的是**新进程**（旧 `python app.py` 会占着端口加载旧代码）；排查实际组件类型可访问 `/config`。
- **Seedance 是「文/图→视频」的生成模型，不能做「视频→文字」理解**。视频理解要用多模态视觉模型：智谱 GLM-4.6V-Flash（免费）/ 阿里 Qwen3-VL-Flash。

## 架构（精简）
- `main.py` 命令行入口；`app.py` Gradio 网页。
- `storyboard/detector.py`：`detect_shots(threshold=27)`（含解码预检、整片无切换时兜底为 1 个镜头）、`extract_keyframes`（取每镜头中间帧）、`format_timecode`、`safe_imwrite`。
- `storyboard/exporter.py`：`export_csv`(utf-8-sig) / `export_markdown` / `export_html`（HTML 内嵌 base64 图 + 可编辑描述列）。
- `input/` 放视频、`output/` 放结果（均已 gitignore）；`app.ico` 图标；两个 `.bat` 启动脚本。

## 版本路线 / 进度
- [x] **v0.1** 镜头切分 + 关键帧 + CSV/MD/HTML 导出 + Gradio 界面 + 桌面快捷方式。已用合成 `input/demo_test.mp4` 验证：5 镜头、时间码零误差。
- [~] **v0.25 运动分析**：概念已验证（见下），尚未集成进主程序。
- [ ] **v0.2** 接多模态视觉 API，自动生成每镜头中文描述（用户尚未注册智谱 / 阿里百炼；密钥不得写入仓库）。
- [ ] **v0.3** 关键帧转分镜线稿简图（Canny 边缘或 ControlNet lineart），画面保留运动箭头。
- [ ] 之后：角色资产（AI 三视图/锚点图为主线，Tripo3D/Meshy + Blender 的 3D 为可选支线）→ 图生视频（可灵 / Seedance / Veo）→ 后期。
- [ ] 部署 Hugging Face Spaces 获取永久公网链接。

### 运动分析验证（2026-09-20）
- 问题：单张中间帧无法表达镜头内运动（如 demo 镜头 3：蓝底白色小球水平向右移动）。
- 已验证可行：背景中值建模 + 帧差定位运动物体 → 多帧位置叠加拖影 + 红色方向箭头 + 起(绿)/止(红)点。样例图在 `output/motion_demo/`。
- 真实电影（机位会动）需改用 OpenCV 稠密光流(Farneback) 或特征点(LK)，并**分离全局运动（摄影机 pan/tilt/zoom）与局部运动（画面内物体）**。
- 计划：每镜头额外输出轨迹/光流箭头图 + 运动方向 / 机位字段，作为 v0.25；再把客观运动数据连同关键帧喂给 v0.2 的视觉模型，描述更准更省 token。

## Git / 发布状态
- 本地已 `git init` 且文件已 `git add`；**尚未首次 commit**（等用户提供 GitHub 用户名 + 注册邮箱后配置仓库级身份）。
- 远程仓库未建。计划仓库名 `movie-storyboard-ai`、Public；建库时**不要**勾选 README / .gitignore / LICENSE（本地都已有）。
- `.gitignore` 已排除 input/、output/、__pycache__/、.gradio/、flagged/、venv 等。

## 给接手 AI 的工作约定
- 改动后必须用**系统 Python** 实测：启动服务并访问 127.0.0.1:7860；必要时用 gradio_client 调 `/process_video` 做端到端验证，不要只看代码。
- 交付优先「双击即用」；新增依赖要同步更新 `requirements.txt` 并装进 `D:\python\python.exe`。
- 每次重要进展，更新本文件「版本路线 / 进度」。

# 🎬 Movie Storyboard AI · 电影分镜提取工具

把一段电影/视频丢进去，自动完成 **镜头切分 → 关键帧提取 → 结构化分镜表导出**，
为 AI 视频创作（分镜复用、角色一致性、图生视频）提供第一块拼图。

> 面向创作者的 AI 视频工作流第一阶段：先把「分镜」这一步自动化。

---

## ✨ 功能特性

- **自动镜头切分**：基于 PySceneDetect 的内容检测算法，自动找到每个镜头的切换点
- **关键帧提取**：每个镜头自动取中间帧作为代表画面
- **灵敏度可调**：动作片快剪、文艺片长镜头都能适配
- **三种导出格式**：
  - `CSV` —— Excel 打开，方便二次编辑
  - `Markdown` —— 直接贴进 GitHub / 笔记
  - `HTML` —— 图文版分镜表，浏览器打开即可逐镜查看（含可编辑的描述列）
- **两种使用方式**：命令行（批量处理）+ Gradio 网页（上传即用）

---

## 📦 安装

需要 Python 3.10+。

```bash
# 1. 克隆（或下载）本项目
git clone https://github.com/<你的用户名>/movie-storyboard-ai.git
cd movie-storyboard-ai

# 2. 安装依赖
pip install -r requirements.txt
```

---

## 🚀 使用方法

### 方式零：桌面快捷方式（Windows，最省事）

项目根目录下提供了启动脚本，可直接双击：

- **`启动分镜工具.bat`** —— 双击后自动启动并在浏览器打开工具
- **`生成公网分享链接.bat`** —— 生成临时公网链接，发给别人在线使用

> 建议把这两个 bat 右键「发送到 → 桌面快捷方式」，并可指定 `app.ico` 作为图标。

### 方式一：网页界面（推荐新手）

```bash
python app.py
```

运行后浏览器会自动打开 `http://127.0.0.1:7860`：
上传视频 → 调整灵敏度 → 点「开始提取分镜」→ 在线查看并下载结果。

- **本机使用**：双击启动脚本即可
- **局域网分享**（同一 WiFi 下的手机/同学电脑）：服务已绑定 `0.0.0.0`，
  别人用浏览器访问 `http://你的局域网IP:7860`（例如 `http://192.168.1.110:7860`）
- **公网临时分享**：双击 `生成公网分享链接.bat`，终端会给出一个 `https://*.gradio.live`
  临时链接，任何人都能打开；关闭窗口即失效

### 方式二：命令行

```bash
# 把视频放进 input/ 文件夹，然后直接运行（自动处理 input 里的第一个视频）
python main.py

# 或指定视频路径
python main.py "C:\Videos\your_movie.mp4"

# 调整灵敏度（数值越小，切出的镜头越多）
python main.py input/test.mp4 --threshold 22
```

结果会输出到 `output/视频名_时间戳/` 目录：

```
output/
└── demo_20260920_110000/
    ├── frames/              # 每个镜头一张关键帧
    │   ├── shot_001.jpg
    │   └── ...
    ├── storyboard.csv       # CSV 分镜表
    ├── storyboard.md        # Markdown 分镜表
    └── storyboard.html      # 图文版预览（推荐打开这个）
```

---

## 🗂️ 项目结构

```
movie-storyboard-ai/
├── 启动分镜工具.bat      # Windows 双击启动（本机）
├── 生成公网分享链接.bat   # Windows 双击生成临时公网链接
├── app.ico              # 应用图标
├── main.py              # 命令行入口
├── app.py               # Gradio 网页界面
├── requirements.txt
├── storyboard/
│   ├── detector.py      # 镜头检测 + 关键帧提取
│   └── exporter.py      # CSV / Markdown / HTML 导出
├── input/               # 放输入视频（已 gitignore）
└── output/              # 放输出结果（已 gitignore）
```

---

## 🧭 灵敏度阈值怎么调

| 阈值 | 适用场景 |
|---|---|
| 18 ~ 25 | 动作片、MV、快剪短视频 |
| 27（默认） | 大多数电影、剧集 |
| 30 ~ 40 | 文艺片、纪录片、长镜头多的内容 |

> 阈值越小越敏感，切出的镜头越多；如果一个完整镜头被错误切碎，就调大一点。

---

## 🛣️ Roadmap

- [x] **v0.1** 镜头自动切分 + 关键帧提取 + 分镜表导出
- [ ] **v0.2** 接入多模态大模型（GLM-4.6V / Qwen-VL），自动生成每个镜头的
      景别、运镜、画面描述
- [ ] **v0.3** 关键帧自动转线稿简图（边缘检测 / ControlNet lineart）
- [ ] **v0.4** 角色锚点图（三视图）生成与角色参考库
- [ ] **v0.5** 对接图生视频管线（分镜表 → 关键帧 → 视频片段）

---

## 🧰 技术栈

| 环节 | 技术 |
|---|---|
| 镜头切分 | [PySceneDetect](https://github.com/Breakthrough/PySceneDetect) |
| 视频/图像处理 | OpenCV |
| 网页界面 | Gradio |
| AI 镜头分析（规划中） | GLM-4.6V / Qwen-VL |

---

## 📄 License

[MIT](LICENSE)

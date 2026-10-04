# 幕间 · AI 视频工作台

一个本地运行的 AI 短片制作工具。前端使用 **Vue 3 + TypeScript + Vite**，后端使用 **FastAPI**。开发时分开运行，日常使用时由 FastAPI 同时提供 Vue 构建产物、API 和素材，一个 Python 服务即可启动整个工作台。

## 首次安装与构建

需要 Python 3.11+、Node.js 22.12+（22.x）或 24+。在项目根目录执行：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
npm --prefix frontend ci
npm --prefix frontend run build
.venv/bin/python main.py
```

浏览器打开 http://127.0.0.1:8765/ 。不要直接双击 HTML 文件。端口可用 `--port 8766` 修改。Windows 将 `.venv/bin/python` 换成 `.venv\Scripts\python.exe`。

前端已经构建好后，日常只运行 `.venv/bin/python main.py`，Mac 也可以双击 `drama.command`。运行构建产物无需 Node.js 或 Vite 服务。前端代码修改后需重新构建；构建完成后刷新页面即可。更新 Python 后需重启服务。

`frontend/dist/` 是生成目录，不提交到 Git。新克隆或部署到另一台机器时需先构建，或将已构建的整个 `dist/` 一并复制。如果缺少构建产物，首页会返回明确的构建提示，API 仍可使用。

## 前端开发与热更新

在两个终端分别运行：

```bash
# 终端一：项目根目录，启动 Python 后端
.venv/bin/python main.py --reload

# 终端二：项目根目录，启动 Vue 开发服务器
npm --prefix frontend run dev
```

开发页面打开 http://127.0.0.1:5173/ 。Vite 将 `/api`、`/assets` 和 `/openapi.json` 代理到 FastAPI，Vue 修改会热更新，无需每次构建。开发代理会将请求的 Host/Origin 对齐后端地址，FastAPI 原有的本机访问与写请求标识检查仍保留。

后端使用其他端口时，通过 `DRAMA_API_URL` 指定代理目标，例如：

```bash
DRAMA_API_URL=http://127.0.0.1:8766 npm --prefix frontend run dev
```

## 目录：从哪里开始二开

```text
frontend/
  package.json             Vue、Vite、TypeScript、测试及构建命令
  package-lock.json        锁定依赖，使用 npm ci 安装
  vite.config.ts           本地开发代理及构建配置
  index.html               Vue 挂载入口
  src/
    main.ts                Vue 启动入口
    App.vue                工作台布局、项目切换和模型选择
    api.ts                 类型化请求封装和业务 API
    types.ts               项目、角色、镜头、候选与导出数据类型
    domain.ts              候选选择、导出版本等纯业务选择器
    composables/useStudio.ts  响应式状态、操作互斥、轮询与通知
    views/                 五个制作步骤的 Vue 页面
    components/            状态条、工作流、素材及成本等组件
    dialogs/               项目、分镜、候选对比、服务设置等表单
    style.css              工作台样式
  tests/                   请求、轮询并发及 Vue 表单回归测试
  dist/                    构建产物，由 FastAPI 提供（Git 忽略）
backend/
  api.py                   FastAPI 路由及 Vue 构建产物挂载
  services.py              项目管理、后台任务、审核、候选和导出
  workflow.py              策划、制作前检查及预演与样片审核
  economics.py             生成预估、选用素材与归档成本统计
  styles.py                画风预设与画风变更规则
  providers.py             模型服务适配
  media.py                 FFmpeg 合成、字幕、音轨与媒体检查
  schemas.py               Pydantic 请求校验
  storage.py               JSON 持久化、原子保存与中断恢复
main.py                    启动入口
requirements.txt           Python 运行依赖
requirements-dev.txt       Python 检查与测试依赖
pyproject.toml             pytest 和 Ruff 配置
drama.command              Mac 日常启动脚本
storage/drama/             既有配置、作品、候选与成片，原路径保留
tests/                     后端回归测试
.github/workflows/ci.yml    Vue 构建、前端测试和 Python 检查
```

从前端开始阅读：`frontend/src/App.vue → views/ → composables/useStudio.ts → api.ts → backend/api.py`。所有 HTTP 方法和路径集中在 `api.ts`；页面使用 Vue 模板、表单绑定和组件事件，不再拼接 HTML 或委托整页点击事件。共享状态使用 Composition API，不额外引入状态库。

| 想修改什么 | 主要文件 |
|---|---|
| 页面布局和交互 | `frontend/src/views/`、`components/`、`dialogs/` |
| 页面共享状态和轮询 | `frontend/src/composables/useStudio.ts` |
| 前端 API 和数据类型 | `frontend/src/api.ts`、`types.ts` |
| 模型服务、请求参数和下载方式 | `backend/providers.py` |
| 审核、候选筛选、任务调度 | `backend/services.py` |
| 分辨率、音轨、字幕和编码参数 | `backend/media.py` |
| 后端输入校验 | `backend/schemas.py` |
| 数据持久化 | `backend/storage.py` |

后端接口结构可查看 http://127.0.0.1:8765/openapi.json 。

## 制作视频

先在页面“服务设置”配置文本模型与 Seedance 的服务地址、模型、API Key，以及每秒视频费用估算。配置统一保存在 `storage/drama/settings.json`；视频密钥为空时兼容读取 `VOLCENGINE_ARK_API_KEY` 环境变量。已移除旧 MoneyPrinterTurbo 的 `config.toml` 兼容读取。

文本服务默认继承进程的 `HTTP_PROXY` / `HTTPS_PROXY` 等环境代理。若代理不可用，可在“文本连接方式”选择“直连”，保存后立即对后续文本请求生效；该设置不影响 Seedance。文本请求不会自动重试，超时也不自动换路线重发，避免重复计费。

页面顶部可直接切换 **Seedance 2.5 / Seedance 2.0 mini**，选择后自动保存；服务设置也提供相同的模型预设。两者共用方舟地址和密钥，DeepSeek 配置保持不变。模型 ID 已通过配置的方舟 `/models` 只读接口核对：`doubao-seedance-2-5-260628`、`doubao-seedance-2-0-mini-260615`；是否能实际调用仍取决于账号开通情况与余额。

逐镜头生成使用720p并请求原生声音。全部选用mini候选的正式成片导出720p；其余正式合成使用1080p，导出清单记录实际输出分辨率。切换模型只影响后续生成，已有候选不会被重新提交。

`seedance_estimates` 分别记住每个模型的每秒费用预估，`estimate_per_second` 表示当前选中模型的值。既有2.5预算设置保留；mini首次选择使用0.6元/秒作为可编辑的保守预算参考值（按保存的官方刊例价估算并留余量，不使用限时折扣）。这是预算参考，不是实时价格或实际账单。参考来源：https://docs.volcengine.com/docs/82379/1544106 。模型预设及规格集中放在 `backend/providers.py` 的 `VIDEO_MODELS`。

### 制作形式

新项目默认“对话短剧”。项目设置还可选“旁白推文”或“混合形式”；旧项目保留原形式。对话与混合策划按场景、动作、说话人、台词、情绪保存，分镜按来源段落核对台词、说话人和顺序，支持无声反应镜头。切换形式使相关审核失效，不会自动改写已有草稿。角色声音设定与台词表演要求会进入视频提示词，但不保证跨镜头音色锁定。

### 统一画风

新项目默认选择“自动推荐”，无需手写画风。点击“AI 起草策划”时，文本模型会在同一次请求中返回策划、画风和推荐理由；在故事页点击“采用推荐画风”后再生成分镜。创建项目本身不调用模型。手动填写策划的项目也可以单独推荐画风（文本计费）。

也可在创建项目或项目设置中直接选择都市甜宠、古风言情、悬疑惊悚、玄幻热血、都市情感预设，或选择自定义。预设不调用模型；个人预设可命名保存，保存在 `storage/drama/style-presets.json`，以后创建项目可直接选用。

确认后的画风由项目内所有分镜和视频提示词继承；重新起草策划不会自动替换已确认的画风。采用新画风后，角色与分镜需重审，旧画风的候选和预演按版本失效，原文件保留。已有项目保持原画风。

### 分步骤制作

新项目：内容策划与文案审核 → 生成或导入分镜 → 固定角色 → 免费整条预演 → 单镜样片审核 → 批量制作 → 剪辑导出。

详细操作和 AI 分工见 [小说推文制作流程](docs/小说推文制作流程.md)。先读这份操作说明，再调用付费生成。

- 故事页先填写原文片段或准确梗概，再填写内容策划。也可调用文本服务起草策划（文本服务可能计费，不生成视频）。审核后的连续文案才进入 AI 分镜，导演提示词要求逐句拆分，不自行改写剧情。
- 分镜新增叙事作用、开场状态、结束状态；这些状态随镜头提示词提交。工作台检查分镜台词与文案是否一致，并给出时长、台词密度、同场景衔接提示。这些是规则检查，不是自动审美评分。
- 在“分镜与免费预演”中可直接生成完整文字卡 MP4，不用先制作候选，不覆盖选用结果。本机朗读只适合试听；无本机朗读或上传音轨时预演为静音。
- 新流程付费生成前必须审核策划和当前预演，并为出镜角色配置参考素材。样片未审核前，每次只允许一个镜头、一个候选；已有有效 AI 样片时须先审核通过或淘汰，才能继续生成。导入的有效视频也可以作为样片审核。
- 在候选窗口设置视频入点和出点，画面和原声一起裁剪；不设置时保留完整素材。外部配音长于指定区间会报错，需调整区间或音轨。候选窗口可校对字幕，但不会修改音频或自动对齐到逐字时间。
- 文案、角色、分镜发生变化后，相关预演或样片审核失效；修改剪辑、字幕或选用素材后需重新合成。原素材及历史导出仍保留。

旧项目继续沿用原流程；保存内容策划后启用上述付费检查，不会自动修改旧作品。新流程不保证模型输出无瑕疵或视频获得播放、转化；人物一致性、表演、音色和内容吸引力仍需要观看验收。当前没有整条统一配音上传与精确对齐、多轨混音或发布数据自动回收功能。

角色页支持保存本地参考图，用于预览和项目归档。Seedance API 不接受本地文件或 Base64 图片；正式生成前还需填写方舟可信素材库返回的 `asset://asset-...`，或可公开访问的 HTTPS 图片地址。工作台只附加该镜头出场角色的参考素材，并在缺少远端 URI 时于付费提交前拦截。

普通生成保持原来的 720p 文生视频请求；支持导入自己的图片、视频和音轨。免费预演生成的是文字分镜卡，用来验证故事节奏和流程，不是 AI 人物画面。Mac 可使用系统配音，其他系统可上传音轨。

正式导出默认 **1080×1920、24fps、H.264 CRF 17、AAC 256k**（全部选用 mini 候选时为 720×1280），预演保持 540×960。素材按比例留边；未指定剪辑区间时，短视频不足则定格尾帧，配音过长则延长镜头。指定入点 / 出点后以该区间为准，过长外部配音会提示调整。音轨顺序是上传音轨 → 可选系统配音 → 素材原生音轨 → 静音。正式导出不允许夹带文字预演卡。

## 制作效率与效果复盘

- **分镜页批量改时长**：勾选镜头后统一设置 2–12 秒；保存前显示受影响的候选数。只有时长实际变化的镜头需要重审，其旧候选保留并过期，上传音轨解除关联。
- **镜头制作页候选对比**：同镜头有两个及以上有效候选时，可并排查看、从头一起播放、切换左右原声试听，再选用一个候选。对比播放完整素材；剪辑区间在详情中编辑。
- **付费制作清单**：提交前展示模型、镜头、候选数量、本次预估和剩余预算；已有有效候选的镜头会提示避免重复制作。
- **导出页成本复盘**：查看累计视频预估、当前选用素材预估、其余生成预估及逐镜头明细。累计包含归档剧本；未知任务继续保留预估，明确提交失败的预估已释放。其余候选可能是备用素材，不等于浪费。
- **正式版本发布效果**：每个正式导出版本可手动记录平台、发布链接、播放、点赞、转化、收入、实际总成本和复盘笔记。未知数据留空，0 表示已确认没有；只有填写实际成本和收入后才计算利润和成本回报率。共用素材的多个版本需自行分摊实际成本。

新导出会将当时的成本快照写入制作清单，之后新增候选不会改写历史快照；旧导出没有历史快照时会明确提示。发布复盘保存在 `project.json` 对应的导出记录中，不修改原制作清单或视频。当前不自动同步服务商账单或平台数据。

## 已制作的视频在哪里

所有作品仍在 `storage/drama/`，无需迁移。

- 《龙醒》观看版：`storage/drama/showcase/龙醒-1080p.mp4`。
- 《龙醒》母版：`storage/drama/showcase/龙醒-原始母版.mp4`。
- 其他项目：`storage/drama/<项目ID>/`，其中 `project.json` 保存剧本、角色、候选和导出文件引用。
- 同目录的 MP4 是视频素材或成片，SRT 是字幕，JSON 还可能是制作清单或模型调用记录。按项目引用判断用途。
- `showcase/` 及旁边的样片脚本、策划和价格资料是历史存档；历史脚本保留原模块引用，不再作为当前可执行入口。

备份作品请复制整个 `storage/drama/`。`DRAMA_STORAGE` 环境变量可指定其他作品目录。同一个作品目录只能由一个服务进程使用。

修改人物、画风或镜头会让相关旧候选失效，需重新审核；切换剧本时旧镜头会归档。后台任务逐步保存结果，服务重启后可手动继续；有云端任务编号的继续查询原任务，没有编号的未知提交会停止，避免重复付费。预算是视频费用估算，不包含文本费用，也不等于服务商实际账单。

服务绑定本机地址，保留 Host/Origin 检查和写请求标识。设置接口隐藏密钥。当前没有公网账号系统。

## 开发检查

```bash
npm --prefix frontend ci
npm --prefix frontend run build
npm --prefix frontend test
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m ruff check backend main.py tests
.venv/bin/python -m pytest -q
```

`npm run build` 先执行 `vue-tsc` 类型检查，再生成部署产物。后端测试包含构建产物的真实访问检查，需要先完成前端构建。前端测试使用模拟请求，不调用模型服务。

测试使用模拟云端接口和真实 FFmpeg，不产生视频生成费用。FFmpeg 优先使用系统版本，否则使用 `imageio-ffmpeg` 自带版本。

`.venv/` 是 Python 环境，类似 `node_modules`；`__pycache__/`、`.pytest_cache/` 和 `.ruff_cache/` 是自动生成的缓存。业务开发时无需逐个阅读。

前端源码已迁移到 `frontend/src/`，统一部署只提供 `frontend/dist/`。模型提示词、生成参数、视频合成规则和已有作品沿用原逻辑。

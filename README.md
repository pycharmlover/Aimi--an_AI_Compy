# Aimi

一个 AI 虚拟好友平台，用户可以创建自定义 AI 角色，并与其进行实时语音 / 文字聊天。后端基于 Django + LangChain，前端基于 Vue 3 + Vite。

---

## 目录结构总览

```
AIFriends/
├── backend/                              # Django 后端
│   ├── backend/                          # Django 项目配置包
│   │   ├── settings.py                   # 全局配置（数据库、JWT、CORS、静态文件等）
│   │   ├── urls.py                       # 根路由（挂载 admin 与 web 应用路由）
│   │   ├── asgi.py                       # ASGI 入口
│   │   └── wsgi.py                       # WSGI 入口
│   ├── web/                              # 核心业务应用
│   │   ├── models/                       # 数据模型
│   │   │   ├── user.py                   # UserProfile —— 用户扩展信息（头像、简介）
│   │   │   ├── character.py              # Character —— AI 角色；Voice —— TTS 音色
│   │   │   └── friend.py                 # Friend —— 用户与角色的绑定关系
│   │   │                                 # Message —— 对话记录（含 token 用量）
│   │   │                                 # SystemPrompt —— 系统提示词配置
│   │   ├── views/                        # 视图（API 处理层）
│   │   │   ├── index.py                  # SPA 入口渲染（所有非 API 路由返回前端 HTML）
│   │   │   ├── user/                     # 用户相关接口
│   │   │   │   ├── account/
│   │   │   │   │   ├── login.py          # 登录（颁发 JWT access/refresh token）
│   │   │   │   │   ├── logout.py         # 登出（清除 refresh token cookie）
│   │   │   │   │   ├── register.py       # 注册新用户
│   │   │   │   │   ├── refresh_token.py  # 使用 refresh token 换取新 access token
│   │   │   │   │   └── get_user_info.py  # 获取当前登录用户信息
│   │   │   │   └── profile/
│   │   │   │       └── update.py         # 更新用户头像 / 简介
│   │   │   ├── create/                   # 角色创建与管理接口
│   │   │   │   └── character/
│   │   │   │       ├── create.py         # 创建 AI 角色
│   │   │   │       ├── update.py         # 更新角色信息
│   │   │   │       ├── remove.py         # 删除角色
│   │   │   │       ├── get_single.py     # 获取单个角色详情
│   │   │   │       ├── get_list.py       # 获取角色列表
│   │   │   │       └── voice/
│   │   │   │           ├── get_list.py   # 获取可用 TTS 音色列表（公开 + 当前用户私有）
│   │   │   │           └── custom/       # 自定义音色管理
│   │   │   │               ├── create_custom.py  # 上传 mp3 -> 调用复刻 API -> 存库
│   │   │   │               ├── create_voice.py   # 调用阿里云语音复刻 API
│   │   │   │               ├── list_voice.py     # 获取自定义音色列表
│   │   │   │               └── remove_voice.py   # 删除自定义音色
│   │   │   ├── friend/                   # 好友（用户-角色关系）接口
│   │   │   │   ├── get_or_create.py      # 获取或创建好友关系
│   │   │   │   ├── get_list.py           # 获取好友列表
│   │   │   │   ├── remove.py             # 删除好友
│   │   │   │   └── message/              # 消息相关
│   │   │   │       ├── chat/
│   │   │   │       │   ├── chat.py       # SSE 流式对话（LLM 推理与 TTS 合成并发输出）
│   │   │   │       │   └── graph.py      # LangGraph 对话图定义
│   │   │   │       ├── vision/
│   │   │   │       │   └── stream_vision.py  # 视觉推理接口（接收图像 + 文本提示，返回推理结果 + 音频）
│   │   │   │       ├── memory/           # 长期记忆管理
│   │   │   │       │   ├── graph.py      # 记忆提取 LangGraph 图
│   │   │   │       │   └── update.py     # 触发记忆更新（每轮对话后异步执行）
│   │   │   │       ├── asr/
│   │   │   │       │   └── asr.py        # 接收 PCM 音频，通过 WebSocket 调用 ASR 服务返回文字
│   │   │   │       ├── tts/
│   │   │   │       │   └── tts.py        # 接收文字，通过 WebSocket 调用 TTS 服务，SSE 流式返回 Base64 mp3
│   │   │   │       └── get_history.py    # 获取历史消息记录
│   │   │   ├── homepage/
│   │   │   │   └── index.py              # 返回首页所需角色 / 好友数据
│   │   │   └── utils/
│   │   │       └── photo.py              # 图片处理工具函数
│   │   ├── migrations/                   # 数据库迁移文件（按时间顺序）
│   │   │   ├── 0001_initial.py           # 初始表结构（UserProfile）
│   │   │   ├── 0002_character.py         # 添加 Character 模型
│   │   │   ├── 0003_friend.py            # 添加 Friend 模型
│   │   │   ├── 0004_message.py           # 添加 Message 模型
│   │   │   ├── 0005_alter_message_input.py  # 扩展 Message.input 字段长度
│   │   │   ├── 0006_systemprompt.py      # 添加 SystemPrompt 模型
│   │   │   └── 0007_voice_character_voice.py  # 添加 Voice 模型及 Character.voice 外键
│   │   ├── documents/                    # RAG / 向量检索模块
│   │   │   ├── utils/                    # 文档处理工具
│   │   │   └── lancedb_storage/          # LanceDB 本地向量数据库存储（已 gitignore）
│   │   ├── templates/
│   │   │   └── index.html                # Django 模板（Vue SPA 壳页面）
│   │   ├── admin.py                      # Django Admin 模型注册
│   │   ├── apps.py                       # Django 应用配置
│   │   └── urls.py                       # web 应用路由（所有 /api/* 及 SPA fallback）
│   ├── media/                            # 用户上传媒体文件（运行时生成，已 gitignore）
│   │   ├── character/
│   │   │   ├── photo/                    # 角色头像
│   │   │   └── background_images/        # 角色背景图
│   │   └── user/
│   │       └── photos/                   # 用户头像
│   ├── static/                           # 静态文件目录（前端构建产物部署至此）
│   │   └── frontend/                     # Vue 前端 dist 输出（assets/、vad/、index.html）
│   ├── manage.py                         # Django 管理命令入口
│   ├── package.json                      # 后端 Node 依赖（构建脚本用）
│   └── db.sqlite3                        # SQLite 数据库（已 gitignore）
│
└── frontend/                             # Vue 3 前端
    ├── src/
    │   ├── main.js                       # 应用入口（创建并挂载 Vue 实例，注册 Pinia、Router）
    │   ├── App.vue                       # 根组件（全局布局与路由出口 <RouterView>）
    │   ├── assets/
    │   │   └── main.css                  # 全局样式
    │   ├── router/
    │   │   └── index.js                  # 路由表定义与导航守卫（未登录重定向至登录页）
    │   │                                 #   /                          首页
    │   │                                 #   /friend/                   好友聊天页
    │   │                                 #   /create/                   角色创建页
    │   │                                 #   /create/character/update/:id  角色编辑页
    │   │                                 #   /user/account/login/       登录页
    │   │                                 #   /user/account/register/    注册页
    │   │                                 #   /user/space/:user_id/      用户空间页
    │   │                                 #   /user/profile/             个人资料编辑页
    │   │                                 #   /404/                      404 页
    │   ├── stores/
    │   │   └── user.js                   # Pinia 用户状态（id、用户名、头像、access token 等）
    │   ├── js/
    │   │   ├── config/
    │   │   │   └── config.js             # 环境配置（vue 开发 / django 开发 / cloud 生产 三套 URL）
    │   │   ├── http/
    │   │   │   ├── api.js                # Axios 封装（自动附加 Bearer token；401 时静默刷新 token 并重试原请求）
    │   │   │   ├── streamApi.js          # SSE 流式请求封装（接收 AI 文字回复 + Base64 音频流）
    │   │   │   └── visionApi.js          # 视觉推理 SSE 流式请求封装（接收推理结果 + 音频）
    │   │   └── utils/
    │   │       └── base64_to_file.js     # Base64 字符串转 File 对象工具函数
    │   ├── components/
    │   │   ├── navbar/
    │   │   │   ├── NavBar.vue            # 顶部导航栏（首页 / 好友 / 创建 / 用户菜单）
    │   │   │   └── icons/               # 导航栏 SVG 图标组件
    │   │   │       ├── HomePageIcon.vue
    │   │   │       ├── FriendIcon.vue
    │   │   │       ├── CreateIcon.vue
    │   │   │       ├── SearchIcon.vue
    │   │   │       ├── MenuIcon.vue
    │   │   │       ├── UserProfileIcon.vue
    │   │   │       ├── UserSpaceIndex.vue
    │   │   │       └── UserLogoutIcon.vue
    │   │   ├── character/
    │   │   │   ├── Character.vue         # 角色卡片展示组件
    │   │   │   ├── icons/               # 角色操作 SVG 图标组件
    │   │   │   │   ├── UpdateIcon.vue
    │   │   │   │   ├── RemoveIcon.vue
    │   │   │   │   ├── SendIcon.vue
    │   │   │   │   ├── MicIcon.vue
    │   │   │   │   ├── KeyboardIcon.vue
    │   │   │   │   └── Horn.vue             # 小喇叭图标（用于 TTS 重放按钮）
    │   │   │   └── chat_field/          # 聊天区域组件树
    │   │   │       ├── ChatField.vue     # 聊天区域容器（整合下方各子组件，支持拖动右下角缩放）
    │   │   │       ├── character_photo_field/
    │   │   │       │   └── CharacterPhotoField.vue  # 角色头像与背景展示
    │   │   │       ├── chat_history/
    │   │   │       │   ├── ChatHistory.vue          # 历史消息滚动列表
    │   │   │       │   └── message/                 # 单条消息气泡组件
    │   │   │       │       ├── Message.vue          # 消息气泡（AI 气泡下方挂载小喇叭按鈕）
    │   │   │       │       └── tts/
    │   │   │       │           └── PlayTts.vue      # 小喇叭播放组件（点击后重新合成并播放当前消息语音）
    │   │   │       └── input_field/
    │   │   │           ├── InputField.vue           # 文字输入框、发送按钮、摄像头浮窗（支持拖动）
    │   │   │           └── Microphone.vue           # 麦克风录音（集成 Silero VAD 语音端点检测）
    │   │   └── UserMenu.vue              # 用户菜单下拉（个人空间 / 资料 / 登出）
    │   └── views/
    │       ├── homepage/
    │       │   └── HomepageIndex.vue     # 首页（展示平台公开角色列表）
    │       ├── friend/
    │       │   └── FriendIndex.vue       # 好友页（左侧好友列表 + 右侧聊天窗口）
    │       ├── create/
    │       │   ├── CreateIndex.vue       # 角色管理页（我创建的角色列表 + 新建入口）
    │       │   ├── character/
    │       │   │   └── UpdateCharacter.vue  # 角色信息编辑页（名称、头像、音色、人设等）
    │       │   └── components/           # 角色创建 / 编辑表单组件
    │       │       ├── Photo.vue         # 头像上传
    │       │       ├── Name.vue          # 角色名称
    │       │       ├── Profile.vue       # 角色人设
    │       │       ├── BackgroundImage.vue  # 背景图上传
    │       │       ├── Voice.vue         # 音色选择（含自定义音色选项）
    │       │       ├── UploadVoice.vue   # 自定义音色上传组件
    │       │       └── icons/
    │       │           └── UploadIcon.vue    # 上传图标
    │       ├── user/
    │       │   ├── account/
    │       │   │   ├── LoginIndex.vue    # 登录页
    │       │   │   └── RegisterIndex.vue # 注册页
    │       │   ├── space/
    │       │   │   └── SpaceIndex.vue    # 用户空间页（查看任意用户的公开角色）
    │       │   └── profile/
    │       │       └── ProfileIndex.vue  # 个人资料编辑页（头像、昵称、简介）
    │       └── error/
    │           └── NotFoundIndex.vue     # 404 页面
    ├── public/
    │   ├── favicon.ico                   # 网站图标
    │   └── vad/                          # VAD WebAssembly 运行时文件（已 gitignore）
    │       ├── silero_vad_legacy.onnx    # Silero VAD ONNX 模型权重
    │       ├── ort-wasm-simd-threaded.*  # ONNX Runtime WebAssembly 运行时（多线程 SIMD）
    │       └── vad.worklet.bundle.min.js # VAD AudioWorklet 处理器脚本
    ├── index.html                        # HTML 入口模板
    ├── vite.config.ts                    # Vite 构建配置
    ├── tsconfig.json                     # TypeScript 根配置
    ├── tsconfig.app.json                 # 应用源码 TS 配置
    ├── tsconfig.node.json                # Node 环境 TS 配置（vite.config.ts 用）
    ├── env.d.ts                          # 环境变量与 .vue 文件类型声明
    └── package.json                      # 前端依赖声明
```

---

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端框架 | Vue 3 + Vite |
| 前端状态管理 | Pinia |
| 前端路由 | Vue Router 4 |
| HTTP 客户端 | Axios（含 JWT 自动刷新拦截器） |
| 语音活动检测 | Silero VAD（WebAssembly + ONNX Runtime） |
| 后端框架 | Django 6 + Django REST Framework |
| 身份认证 | JWT（SimpleJWT，access/refresh token 双 token 机制） |
| AI 对话 | LangChain / LangGraph |
| 语音合成（TTS） | CosyVoice v3（通过 WebSocket 与 LLM 并发流式合成） |
| 语音识别（ASR） | Gummy Realtime（通过 WebSocket 实时转写 PCM 音频） |
| 多模态视觉推理 | Qwen3.5-Flash（通过 LangChain 接收实时视频流 + 文本，返回推理结果） |
| 向量数据库 | LanceDB（本地存储，用于 RAG 长期记忆） |
| 数据库 | SQLite（开发） |
| 跨域 | django-cors-headers |

---

## 主要功能

- **角色创建**：用户可自定义 AI 角色的名称、头像、背景图、人设描述、TTS 音色
- **自定义音色**：在创建 / 编辑角色时，可上传一份**时长8s左右**的 mp3 文件进行语音复刻，生成私有音色供当前用户使用
- **好友系统**：将角色添加为好友，维护独立的对话上下文与长期记忆
- **流式对话**：LLM 推理与 TTS 合成并发执行，通过 SSE 同步向前端推送文字与音频
- **语音输入**：前端集成 Silero VAD 自动检测语音端点，录音完成后调用后端 ASR 接口转写为文字
- **长期记忆**：每轮对话结束后异步提取关键信息，更新至好友的 memory 字段，下次对话时注入 System Prompt
- **JWT 认证**：access token 存于内存，refresh token 存于 HttpOnly Cookie，Axios 拦截器自动无感刷新
- **语音重放**：每条 AI 回复气泡下方附有小喇叭按钮，点击后调用独立 TTS 接口重新合成语音，全量接收音频块后合并解码播放
- **视觉推理**：打开摄像头后，输入提示词并点击发送，AI 可分析摄像头画面内容并生成语音回复。摄像头浮窗可自由拖动位置
- **聊天框缩放**：拖动聊天框右下角三角形手柄可自由缩放聊天窗口（0.5x ~ 2x），内部布局相对位置保持不变 

---

## 使用说明

### 1. 创建虚拟环境

推荐使用 conda 或 venv，Python 版本需 **3.12+**（当前开发环境为 Python 3.14）：

```bash
conda create -n aifriends python=3.14
conda activate aifriends
```

### 2. 安装依赖

在项目根目录下执行（推荐使用清华源加速）：

```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 3. 初始化后端数据库

进入 `backend/` 目录，依次执行：

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

启动后访问 `http://127.0.0.1:8000/admin/` 可进入 Django 后台管理界面。

> **注意：** 如需在前端开发模式下调试，打开 `frontend/src/js/config/config.js`，将第一行 `platform` 改为：
> - `'vue'` — 使用 Vite 开发服务器（`npm run dev`）
> - `'django'` — 使用 Django 本地静态文件
> - `'cloud'` — 生产环境部署

### 4. 配置环境变量

在 `backend/` 目录下新建 `.env` 文件，填入以下内容（`API_KEY_EMB` 需替换为**你自己的阿里云百炼 API Key**，其余可直接复制）：

```env
API_KEY_EMB=<你的阿里云百炼 API Key>
API_BASE_EMB=https://dashscope.aliyuncs.com/compatible-mode/v1
WSS_URL=wss://dashscope.aliyuncs.com/api-ws/v1/inference
VOICE_URL=https://dashscope.aliyuncs.com/api/v1/services/audio/tts/customization
```

### 5. 注意事项

> **⚠️ 前端构建同步**
>
> 每次修改 `frontend/` 下的代码后，需在 `frontend/` 目录执行：
> ```bash
> npm run build
> ```
> 并将生成的 `assets/` 中的 JS / CSS 文件路径**手动更新**到 `backend/web/templates/index.html` 中对应的两处引用。

> **⚠️ 数据库迁移同步**
>
> 每次在 `backend/web/models/` 或 `backend/web/admin.py` 中新增 / 修改模型后，需在 `backend/` 目录执行：
> ```bash
> python manage.py makemigrations
> python manage.py migrate
> ```
> 以确保数据库结构与代码保持同步。

### 6. 生产环境部署

**前置条件：** 已有配置好 Python 环境的服务器（当前使用的是阿里云 ECS），前端已构建并集成到后端

**部署步骤：**

1. **切换环境配置**

修改 `frontend/src/js/config/config.js`，将 `platform` 改为 `'cloud'`：

```javascript
const platform = 'cloud'
```

2. **禁用调试模式**

修改 `backend/backend/settings.py`：

```python
DEBUG = False
```

3. **上传后端代码至服务器**

```bash
scp -r backend/ user@server_ip:/path/to/backend
```

4. **收集静态文件**

在服务器的 `backend/` 目录执行：

```bash
python3.14 manage.py collectstatic --noinput
```

5. **启动应用服务**

使用 `tmux` 后台运行 Gunicorn（即使关闭终端也保持运行）：

```bash
tmux 
gunicorn --workers 3 --graceful-timeout 3 --bind unix:/home/acs/backend/gunicorn.sock backend.wsgi:application
```

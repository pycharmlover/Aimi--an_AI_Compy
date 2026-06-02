# Aimi 一期联网搜索增强：文件级修改清单与 Cursor Patch Plan

## 文档目的

这份文档面向 **Cursor 实施**，目标是把 Aimi 的 **第一期联网搜索增强** 方案落成一个可直接执行的文件级 patch 计划。

本期只做最小可用版本：

- 用户在文本聊天输入框中手动开启“联网搜索”
- 后端在主模型生成前调用 browser use 搜索网页
- 只提取 browser use 返回中的“最终答案”部分
- 将其作为 `web_context` 注入主模型上下文
- 主模型仍然负责最终流式输出
- 继续沿用现有 **chunk -> TTS -> SSE -> 前端播放** 链路
- browser use 失败时自动降级为普通聊天

---

# 1. 本期真实改动边界

## 1.1 本期必须修改的现有文件

1. `requirements.txt`
2. `frontend/src/components/character/chat_field/input_field/InputField.vue`
3. `backend/web/views/friend/message/chat/chat.py`

## 1.2 本期必须新增的文件

1. `backend/web/services/__init__.py`
2. `backend/web/services/web_search/__init__.py`
3. `backend/web/services/web_search/browser_executor.py`
4. `backend/web/services/web_search/service.py`

## 1.3 本期不需要修改的现有文件

这些文件已确认**当前一期方案中不需要改**，避免 Cursor 误改：

1. `frontend/src/js/http/streamApi.js`
   - 现有流式请求工具已经支持任意 `body` 字段透传，不需要为了 `enable_web_search` 单独修改。
2. `frontend/src/js/http/visionApi.js`
   - 一期不改视觉聊天链路。
3. `backend/web/views/friend/message/chat/graph.py`
   - 一期不把 browser use 做成 LangGraph tool。
4. `backend/web/urls.py`
   - 仍然使用原有 `/api/friend/message/chat/` 接口，不新增路由。
5. `backend/web/views/friend/message/vision/stream_vision.py`
   - 一期不接视觉模式联网搜索。

## 1.4 参考文件

1. `/Users/liuchang/Desktop/browser use/main.py`
   - 这是 browser use 搜索原型参考实现。
   - 用于复用搜索任务模板、环境变量命名和 Agent 调用方式。
   - **不要直接把这个文件移动进 repo 里**，而是按下文拆分成服务层文件。

---

# 2. 目标架构（一期）

```text
InputField.vue
  -> POST /api/friend/message/chat/
     body: { friend_id, message, enable_web_search }

MessageChatView.post()
  -> if enable_web_search:
       web_context = build_web_context_for_query(message)
     else:
       web_context = ""

  -> inputs = add_system_prompt(...)
  -> inputs = add_web_context(...)
  -> inputs = add_recent_messages(...)
  -> ChatGraph.create_app()
  -> app.astream(...)
  -> 每个 chunk 继续送入 TTS websocket
  -> SSE 返回 content/audio
```

一期的关键原则：

- browser use 只做“检索与整理”
- 主模型仍是唯一最终输出源
- TTS 只消费主模型 chunk
- 搜索失败必须优雅降级

---

# 3. 文件级修改清单

下面按“文件路径 -> 当前职责 -> 本期修改目标 -> 具体 patch 点 -> 验收标准”展开。

---

## 3.2 `frontend/src/components/character/chat_field/input_field/InputField.vue`

### 当前职责

文本输入、麦克风输入、摄像头模式切换、流式聊天请求发送、音频 chunk 播放。

### 本期修改目标

给文本聊天入口新增“联网搜索”开关，并在文本聊天请求中附带 `enable_web_search`。

### 本期具体修改点

#### A. 新增前端状态

在 `<script setup>` 中新增：

- `const enableWebSearch = ref(false)`

说明：

- 默认关闭
- 一期不需要持久化到 store
- 一期只影响**文本聊天**模式

#### B. 修改文本发送请求体

当前文本模式调用：

- `streamApi('/api/friend/message/chat/', { body: { friend_id, message } })`

需要改成：

- `body: { friend_id, message, enable_web_search: enableWebSearch.value }`

#### C. UI 层增加一个联网搜索开关

在输入栏区域增加一个开关按钮。

建议要求：

- 不新增复杂组件
- 可以先用纯文字按钮 / badge 样式实现
- 开启时视觉上明显区分
- 不影响现有发送按钮、麦克风按钮、摄像头按钮布局

#### D. 摄像头模式不接入联网搜索

保持当前逻辑：

- 如果 `cameraActive` 为真，继续走 `visionApi`
- 此时 `enableWebSearch` 不参与请求

#### E. 本轮请求发送后不重置联网搜索状态

一期建议：

- 开关状态保留，便于用户连续多轮联网搜索
- 不需要在每轮发送后自动关闭

### Cursor patch 要点

1. 在脚本顶部新增 `enableWebSearch` 状态
2. 在文本聊天请求 `body` 里新增 `enable_web_search`
3. 在 template 的输入栏按钮区域增加一个联网搜索开关
4. 不要改音频 MSE 播放逻辑
5. 不要改摄像头推理逻辑
6. 不要改麦克风逻辑

### 验收标准

- 输入框可切换联网搜索开关
- 文本聊天请求会带上 `enable_web_search`
- 视觉模式不受影响
- 原有文本流式和音频播放不被破坏

---

## 3.3 `backend/web/views/friend/message/chat/chat.py`

### 当前职责

文本聊天主入口，负责：

- 接收 `friend_id` 和 `message`
- 查找好友关系
- 注入 system prompt 和 recent messages
- 创建 `ChatGraph`
- 流式消费主模型输出
- 同步送 TTS websocket
- SSE 返回文本和音频
- 写入 `Message` 历史并更新 memory

### 本期修改目标

在**主模型生成之前**插入一个“可选的联网搜索增强步骤”，但不改变后续 TTS 和 SSE 主流程。

### 本期具体修改点

#### A. 新增参数读取

在 `post()` 中读取：

- `enable_web_search = request.data.get('enable_web_search', False)`

注意事项：

- 要兼容前端不传该字段的情况
- 要把字符串 / 布尔值统一归一化为布尔值

#### B. 新增 web search 服务调用

在构造 `inputs` 之前加入：

- 如果 `enable_web_search` 为真，则调用服务层生成 `web_context`
- 如果失败，则 `web_context = ''`

建议调用形式：

- `web_context = build_web_context_for_query(message)`

说明：

- 只传当前用户原始 message
- 不传 recent messages
- 不传角色 profile 给 browser use
- 保证行为简单可控

#### C. 新增 `add_web_context(state, web_context)`

在本文件中新增一个与 `add_system_prompt` / `add_recent_messages` 同级的小函数：

- 当 `web_context` 为空时，原样返回
- 当有值时，把它作为 `SystemMessage` 插入到 messages 中

建议插入顺序：

1. `add_system_prompt`
2. `add_web_context`
3. `add_recent_messages`

这样 `web_context` 的语义是：

- 系统级补充事实
- 不是用户消息
- 不是历史消息
- 不污染长期记忆

#### D. 增加基础日志

至少用 Python logging 记录：

- friend_id
- user id
- enable_web_search
- browser search 是否成功
- 是否降级

一期可以先用模块级 logger，不需要建表。

#### E. 保持以下逻辑完全不动或最小改动

1. `tts_sender()`
2. `tts_receiver()`
3. `run_tts_tasks()`
4. `work()`
5. `event_stream()` 中的 chunk 发送与 Message 存储主逻辑

说明：
本期必须保住现有 `app.astream(...) -> mq -> SSE/TTS` 主链路。

### Cursor patch 要点

1. 新增对 `enable_web_search` 的读取和归一化
2. 从服务层导入 `build_web_context_for_query`
3. 新增 `add_web_context`
4. 在构造 `inputs` 时插入 `add_web_context`
5. 使用 try/except 包裹 browser search，异常时降级为空上下文
6. 不要把 browser use 的结果直接 `yield` 给前端
7. 不要把 browser use 结果写进 `Message.output`
8. 不要在本期改 memory 写入策略

### 验收标准

- 开启联网搜索时，后端会先检索再聊天
- 检索失败时仍正常回复
- 回复继续流式输出
- 音频继续按 chunk 播放
- `ChatGraph` 主逻辑不被破坏

---

## 3.4 `backend/web/services/__init__.py`

### 当前职责

当前目录不存在，本文件用于把 `services` 目录显式变成 Python 包。

### 本期修改目标

创建空文件即可。

### Cursor patch 要点

1. 新建该文件
2. 文件内容可以为空，或只写一行注释

### 验收标准

- `web.services...` 路径可被正常 import

---

## 3.5 `backend/web/services/web_search/__init__.py`

### 当前职责

当前目录不存在，本文件用于把 `web_search` 目录显式变成 Python 包。

### 本期修改目标

创建空文件即可。

### Cursor patch 要点

1. 新建该文件
2. 文件内容可以为空，或导出 service 层方法

### 验收标准

- `web.services.web_search...` 路径可被正常 import

---

## 3.6 `backend/web/services/web_search/browser_executor.py`

### 当前职责

新文件。

### 本期职责

封装 browser use 的**实际执行逻辑**，只负责：

- 构建 browser 模型
- 构建搜索任务 prompt
- 调用 Agent
- 返回原始文本结果

### 本期建议实现职责边界

这个文件只负责“跑 browser use”，不要负责：

- 提取最终答案
- 拼 web_context
- 与 Django request 直接耦合

### 需要包含的能力

#### A.构建搜索任务模板

复用 `main.py` 中 `build_search_answer_task(query)` 的思路：

#### C. 运行搜索

提供一个 service 级可调用函数，例如：

- `run_browser_search(query: str) -> str`

要求：

- 输入是用户原始问题
- 输出是 main.py中的final_text
- 一期可以同步调用一个内部 async runner

### Cursor patch 要点

1. 把 `main.py` 里的 browser 部分拆进来
2. 只保留 search 模式，不要保留 fill_form 模式
3. 不要在这个文件里写 Django 视图逻辑
4. 不要在这个文件里拼接主模型 prompt

### 验收标准

- 可以从 Python 层单独调用 `run_browser_search("问题")`
- 返回 browser use 结果：final_text
- 异常可向上抛出给 service 层统一处理

---

## 3.7 `backend/web/services/web_search/service.py`

### 当前职责

新文件。

### 本期职责

作为 web search 的**编排层**，对上给 `chat.py` 提供一个简单函数，对下协调：

- `browser_executor.py`

### 推荐对外暴露的方法

- `build_web_context_for_query(query: str) -> str`

### 内部流程

1. 调 `run_browser_search(query)` 拿到final_text
4. 返回 `web_context`

### 错误处理策略

一期建议：

- 这里不要吞掉所有异常并静默返回
- 可以记录日志后返回空字符串
- 对 `chat.py` 暴露“失败时返回空字符串”的稳定行为

这样 `chat.py` 的调用就很简单：

- 不会因为 browser use 异常而整轮崩掉

### Cursor patch 要点

1. 这个文件要成为 `chat.py` 的唯一入口
2. `chat.py` 不要直接 import parser 或 executor
3. 统一在这里处理日志和异常兜底

### 验收标准

- `chat.py` 只需调用一个函数即可拿到 `web_context`
- 搜索失败时返回空字符串
- 成功时返回可注入主模型的上下文块

---

# 4. Cursor 直接可执行的分步 Patch 计划

下面是推荐的执行顺序。Cursor 应按顺序打 patch，避免同时大改造成回归难定位。

---

## Patch Step 1：新增服务层目录和包文件

### 目标

创建新的服务层目录结构。

### 要做的事

1. 新建目录：`backend/web/services/`
2. 新建目录：`backend/web/services/web_search/`
3. 新建文件：
   - `backend/web/services/__init__.py`
   - `backend/web/services/web_search/__init__.py`

### 完成标准

- `web.services.web_search` 可 import

---

## Patch Step 2：引入 browser use 执行器

### 目标文件

`backend/web/services/web_search/browser_executor.py`

### 要做的事

1. 从 `/Users/liuchang/Desktop/browser use/main.py` 参考提取 browser search 相关逻辑
2. 只保留 search_answer 模式
3. 实现：
   - browser llm 构建
   - search task 构建
   - Agent 调用
   - 原始结果返回
4. 支持环境变量：
   - `API_KEY`
   - `BASE_URL`
   - `MODEL`
   - `USE_VISION`
   - `MAX_STEPS`

### 注意事项

- 不要带入 fill_form 逻辑
- 不要依赖 Django request
- 不要在这里处理主模型上下文

### 完成标准

- service 层可以调用一个函数得到 browser 的final_text

---

## Patch Step 3：实现 service 编排层

### 目标文件

`backend/web/services/web_search/service.py`

### 要做的事

1. 串起 executor
2. 暴露统一入口：`build_web_context_for_query(query)`
3. 在这里做日志和失败兜底
4. 失败返回空字符串

### 完成标准

- 上层只调用一个函数即可完成一期联网搜索增强

---

## Patch Step 6：修改聊天主入口

### 目标文件

`backend/web/views/friend/message/chat/chat.py`

### 要做的事

1. 导入 `build_web_context_for_query`
2. 增加参数 `enable_web_search`
3. 增加布尔归一化
4. 在构造 inputs 之前生成 `web_context`
5. 新增 `add_web_context(state, web_context)`
6. 调整构造顺序：
   - `add_system_prompt`
   - `add_web_context`
   - `add_recent_messages`
7. 保持 `event_stream()` / `tts_sender()` / `tts_receiver()` 主逻辑不变

### 注意事项

- browser use 失败时必须降级为空上下文
- 不要把 browser 返回内容直接 SSE 给前端
- 不要改动现有 TTS chunk 机制

### 完成标准

- 文本聊天接口支持联网搜索增强
- 现有流式与音频主链路不回归

---

## Patch Step 7：修改前端输入组件

### 目标文件

`frontend/src/components/character/chat_field/input_field/InputField.vue`

参考联网搜索组件：
'''

<template>
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 24 24"
    :width="size"
    :height="size"
    fill="none"
  >
    <!-- 外圆 -->
    <circle
      cx="12"
      cy="12"
      r="8"
      stroke="currentColor"
      stroke-width="2"
    />
    <!-- 中间竖线 -->
<path
  d="M12 4C9.8 6.2 8.5 9 8.5 12C8.5 15 9.8 17.8 12 20"
  stroke="currentColor"
  stroke-width="2"
  stroke-linecap="round"
/>
<path
  d="M12 4C14.2 6.2 15.5 9 15.5 12C15.5 15 14.2 17.8 12 20"
  stroke="currentColor"
  stroke-width="2"
  stroke-linecap="round"
/>

<!-- 横线 -->
<path
  d="M4 12H20"
  stroke="currentColor"
  stroke-width="2"
  stroke-linecap="round"
/>

  </svg>
</template>

<script setup>
defineProps({
  size: {
    type: [Number, String],
    default: 24
  }
})
</script>

'''



### 要做的事

1. 增加 `enableWebSearch` 状态
2. 增加一个联网搜索开关按钮
3. 文本聊天请求体增加 `enable_web_search`
4. 摄像头模式保持不变
5. 麦克风模式保持不变

### 注意事项

- 尽量小改 template，不要重构整个输入区
- 不要破坏原有发送 / 麦克风 / 摄像头布局
- 一期不做来源展示

### 完成标准

- 前端可以显式开关联网搜索
- 请求能把状态透传到后端

---

## Patch Step 8：补依赖

### 目标文件

`requirements.txt`

### 要做的事

1. 加入 `browser-use`
2. 不做无关升级

### 完成标准

- 后端安装依赖后可 import browser_use

---

# 6. 给 Cursor 的实施约束

## 必须遵守

1. 一期不要引入 DeepSeek query 拆解
2. 一期不要改 `visionApi` / `stream_vision.py`
3. 一期不要修改 `graph.py`
4. 一期不要新增新的聊天接口 URL
5. 一期不要让 browser use 直接输出给前端
6. 一期不要破坏当前 `app.astream -> TTS -> SSE` 主链路
7. 一期不要把联网搜索结果写入长期记忆
8. 一期不要新增数据库表

## 可以接受的小优化

1. 在 `chat.py` 中加入 logger
2. 在 service 层加入超时封装
3. 在 parser 中兼容多种标题分隔写法

---

# 7. 最终交付判定

当以下条件都满足时，一期可以认为落地成功：

1. 前端输入框能手动开启联网搜索
2. 文本聊天请求能把 `enable_web_search` 发到后端
3. 后端在开启时会调用 browser use 搜索
4. 搜索结果能解析出“最终答案”
5. 主模型会把该结果作为额外知识纳入回答
6. 回复仍然是主模型流式输出
7. TTS 仍然按 chunk 边收边播
8. 搜索失败时，系统会自动降级为普通聊天而不是报错中断

---

# 8. 给 Cursor 的一句话任务定义

为 Aimi 的文本聊天链路实现第一期最小可用的联网搜索增强：当输入框开启 `enable_web_search` 时，后端先调用 browser use 搜索网页并提取“最终答案”，将其包装为 `web_context` 注入聊天上下文，随后仍由现有主模型流式输出并继续走 TTS 播报链路；搜索失败时自动降级为普通聊天。


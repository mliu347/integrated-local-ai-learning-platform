# 本地化 AI 支持的多模态英语学习与研究治理一体化平台

英文名称：

**A Locally Hosted AI-Supported Multimodal English Learning and Research Governance Platform**

这是前面 System 1 / System 2 / System 3 的合并版。它们不再是三个割裂系统，而是一个统一平台中的三个功能模块：

- **AI Content Adaptation Module / System 1**：学生或教师上传本地视频，或输入视频主题，生成英文学习视频、旁白、字幕和脚本。
- **Student Learning Interface**：学生在同一页面观看视频、上传本地视频、输入对话任务，并启动/关闭语音 chatbot。
- **Teacher Governance Dashboard**：教师实时监控学生会话，调取每个学生的后台对话记录，进行干预、审计、备注和数据导出。

## 运行

```bash
cd /Users/xiaojiudechaojizhandouji/Documents/Codex/2026-06-08/new-chat/outputs/integrated-local-ai-learning-platform
./run.sh
```

打开：

```text
学生端：http://127.0.0.1:8790/student
教师端：http://127.0.0.1:8790/teacher
```

教师端默认登录：

```text
teacher / teacher-demo
researcher / researcher-demo
```

## 根据你的修改意见已调整

### 1. System 1 视频不能播放的问题

已重写为浏览器兼容的 MP4 输出：

- H.264 video
- AAC audio
- `yuv420p`
- `+faststart`
- VTT 外挂字幕

生成的视频通过 `/media/.../learning_video.mp4` 提供给学生端 `<video>` 播放。

### 2. System 2 语音实时对话

学生端现在有明确的 Chatbot 状态：

- 点击 **启动 Chatbot**：创建学生 session，启动浏览器语音识别，AI 回复会朗读。
- 点击 **关闭 Chatbot**：停止语音识别，停止 speech synthesis，后端也标记 `chatbot_listening=false`。
- 关闭后不会继续听，也不会继续朗读。
- 如果浏览器不支持 Web Speech API，学生仍可用文字输入。
- 页面会显示麦克风测试、实时识别文本和 AI 声音风格。
- AI 朗读时会暂停听写，朗读结束后再恢复，避免把 AI 自己的声音识别成学生发言。

### 2.1 学生端 System 1：本地视频或主题生成英文学习视频

学生端新增：

- 上传本地视频：MP4 / M4V / MOV / WebM，当前本地配置支持 5 分钟以内视频。
- 学生主界面只保留 choose file 或 video topic；更多设置收在 Settings。
- 如果没有本地 Whisper，可在 Settings 输入 video notes or transcript。
- System 1 优先根据原视频转写/说明生成英文版本，不再只按主题套模板。
- 或直接输入视频主题。
- System 1 会生成英文脚本、A1/A2/B1 适配脚本、旁白音频、VTT 字幕和浏览器可播放 MP4。
- 如果使用上传视频，输出视频会使用原视频画面，并配上新生成的英文旁白和字幕。
- 学生观看这个英文版本后，再启动 System 2 chatbot 对话。
- System 2 启动后是连续语音循环：学生说话，AI 回答，AI 说完自动继续听。

### 3. 学生页面和教师页面分开

- `/student`：只显示学生学习体验，包含视频 + chatbot。
- `/teacher`：只显示教师治理与监控，不和学生页面混在一起。

### 4. 学生可以直接看到 System 1 的视频

学生端加载当前教师生成的视频材料，并显示：

- 视频播放器
- 字幕 track
- 学习主题
- 关键词
- chatbot 对话区

### 5. 教师端是 System 3 相关页面

教师端包含：

- 研究监控总览
- 学生对话后台搜索
- 学生研究画像
- 实时学生 session 列表
- turn count
- participation indicators
- reasoning indicators
- average English ratio
- speech / typed input count
- uploaded video metadata
- student dialogue task
- flags / safeguarding events
- pause / resume / terminate
- live transcript
- explainability audit
- teacher notes
- full session record retrieval
- anonymised dataset export

### 6. 三个系统已经连接成一个系统

现在是一个后台服务、一个共享数据层：

```text
AI Content Adaptation Module
        ↓
Student Learning Interface
        ↓
AI Dialogic Interaction Module
        ↓
Teacher Governance Dashboard
        ↓
Research Data Governance Layer
```

## 当前实现边界

- 语音识别依赖浏览器 Web Speech API；不同浏览器/学校设备支持程度不同。
- 当前 chatbot 是本地规则型 Tech-SEDA 对话引擎，后续可接本地 Qwen/Ollama。
- 当前视频为本地生成的浏览器可播学习视频，字幕通过 VTT track 显示。
- 当前 access control 是 demo passcode；正式研究部署需要真实账号和审计签名。
- 数据导出已匿名化，但正式研究仍建议使用机构批准的加密存储方案。

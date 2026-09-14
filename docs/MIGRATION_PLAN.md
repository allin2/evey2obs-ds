# bili2text 到 evey2obs 迁移计划

## 迁移策略

采用渐进迁移，不将旧项目整体复制后再重构。
每一阶段先定义合约与测试，再迁移最小必要实现，并保留旧项目作为行为对照。

## 迁移来源

- 旧项目：`../AI信息流/bili2text`
- 新项目：当前 `evey2obs` 目录
- 需求基线：`docs/PRODUCT_REQUIREMENTS.html`

不应迁移的内容：

- 真实 `.env`、API Key、Cookie 和浏览器数据
- 已下载音视频、Whisper 模型缓存和生成结果
- 旧虚拟环境、IDE 配置和临时日志
- 未经确认的过期文案与平台特判

## 阶段 0：合约与工程基线

**状态：**公共契约已完成（2026-06-17）；平台实现继续按后续阶段迁移。

**目标：**建立可持续迁移的新项目，不实现平台业务。

- 确定 Python 3.11+、`src/` 布局、pytest 和 ruff。
- 定义 `ContentDocument`、`Task`、`SummaryResult` 和 `ExportResult`。
- 定义平台适配器、转写器、总结器和导出器协议。
- 定义稳定错误码、任务阶段和进度事件。
- 建立配置脱敏与临时目录测试。

已交付：

- `ContentDocument`、`SummaryResult`、`ExportResult`、`Task` 与进度事件。
- 来源适配器、转写器、总结器、导出器和清理器协议。
- 六个平台与本地媒体的统一输入识别、批量去重和稳定错误提示。
- 配置校验、Vault 可写探测、URL/凭据脱敏及对应离线测试。
- 平台 HTTP 抓取已接入域名白名单、私网地址拦截、有限重定向和响应大小限制。
- CLI 通过 `TaskService` 使用应用层，不直接调用平台实现。
- Markdown/JSON、附件相对引用和 Obsidian 临时文件原子替换导出。
- 导出完整性校验通过后才允许执行的临时媒体清理器。
- 应用服务启动时会按 `EVEY2OBS_TEMP_RETENTION_HOURS` 清理过期临时文件。
- `adapters/sources/` 已建立六个平台与本地媒体的适配器注册表。
- CLI `resolve` 可离线验证输入到统一 `ContentDocument` 的转换结果。
- `SubtitleProcessor` 已迁移 VTT 字幕解析、语言优先级和稳定错误映射。
- B站与 YouTube source adapter 已接入 yt-dlp 字幕下载器，默认不读取 Cookie。
- B站与 YouTube source adapter 已接入 yt-dlp 最小媒体下载器，不默认下载高清视频。
- yt-dlp 媒体下载前已检查临时目录可用空间，空间不足时映射 `DISK_FULL`。
- ffmpeg 音频标准化/切片与 Whisper 转写器已接入应用层兜底链路。
- OpenAI-compatible 与 Anthropic-compatible 总结器已接入应用层，输出 `SummaryResult`。
- 应用层 `process`/CLI `run` 已编排提取、总结、Obsidian 导出和导出后清理。
- Obsidian 导出失败时已保存脱敏的本地待导出草稿，GUI “待导出草稿”/“仅重试导出”和 CLI
  `export-list`、`export-retry`、`export-remove` 可在修复 Vault 后管理草稿并只重试导出，
  不重新下载、转写或总结。
- 微信公众号公开文章正文清洗、图片下载和访问限制错误映射已接入。
- 小红书公开笔记正文/图片解析、必要 token 保留和视频媒体兜底入口已接入。
- 抖音字幕优先与媒体转写兜底入口已接入。
- 小宇宙 show notes 提取、音频 URL 识别和媒体转写兜底入口已接入。
- 应用层 `TaskQueue` 已支持批量入队、串行运行、单项取消、失败隔离和重试。
- `setup-check` 已支持大模型连接测试和 Obsidian Vault 可删除测试笔记。
- `evey2obs-gui` 初版已接入应用层队列、单项取消/重试、本地文件选择和首次配置诊断。
- GUI 结果动作已支持打开 Markdown、复制摘要、打开原文、打开导出笔记和导出失败诊断。
- GUI 已支持提交前输入识别/去重反馈，以及来源、准确性、摘要和完整原文结果预览。
- 结构化总结已补齐通用、课程、会议、短视频和文章五种稳定模板。
- 转写缓存已按内容指纹与 Whisper 模型复用，并在媒体下载前命中；CLI/GUI 支持强制刷新，
  缓存文件不保存 URL、凭据或本地路径。
- 应用层稳定进度回调已覆盖解析、提取、下载、转写、总结、导出和清理；yt-dlp 提供百分比、
  速度与 ETA，Whisper 提供分片和处理时长。
- GUI 队列已移至后台线程，运行中取消可终止 yt-dlp/ffmpeg 并在 Whisper 分片边界生效；
  队列展示耗时并可清理成功/已取消记录。
- 首次配置诊断已补充 ffmpeg、yt-dlp 和 openai-whisper 轻量可用性检查。
- GUI 设置页已支持大模型、Whisper、Vault/子目录和高级 Cookie 配置；普通设置持久化到
  平台配置目录，API Key 使用系统密钥链且不回显，环境变量可覆盖。
- 保存设置会通过应用服务重配置现有队列的后续运行；yt-dlp 设置显式注入平台适配器。
- GUI 已在配置 Vault 时优先生成 `obsidian://open` 深链，无法推导时回退到文件 URI。
- 新手指南与隐私说明已作为可直接浏览的 HTML 文档交付。
- `package-check` 已提供桌面分发前预验证：入口、依赖、文档、Tkinter 和路径可移植性。
- `package-build --target macos-app` 已可生成未签名的 macOS `.app` 包骨架。
- `package-verify --target macos-app` 已可验证 `.app` 结构、Info.plist、启动器和随包资源。
- `package-build --target windows-portable` 已可生成 Windows 便携目录和 ZIP。
- `package-verify --target windows-portable` 已可验证 Windows 启动器、随包资源、
  缓存排除、ZIP 完整性和路径安全。
- macOS 与 Windows 产物已随附 `RELEASE_CHECKLIST.json`；`package-verify` 会检查发行清单，
  明确签名/公证、真实安装/升级、Windows 10/11、中文路径和 ffmpeg/yt-dlp 子进程门禁。
- `package-verify --release` 已提供严格发行语义：macOS 实际执行 codesign、Gatekeeper
  与 stapler 票据验证；Windows 静态包会因缺少实机证据而保持失败，不再把结构通过等同发行通过。
- `macos-standalone` / `windows-standalone` 已提供 PyInstaller 自包含构建与验证路径，冻结
  Python/运行依赖并纳入 ffmpeg；必须在目标系统本机构建，真实构建、签名、安装和许可证
  审查仍属于发行验收。
- 2026-06-18 已在 macOS arm64 完成一次真实 `macos-standalone` 构建；产物约 562 MB，
  冻结后的 yt-dlp、Whisper、keyring 导入与随包 ffmpeg `-version` 自检通过。Developer ID
  签名、Gatekeeper、公证票据、干净用户首次启动和升级仍未通过发行验收。
- 真实平台验收测试框架与私有样例清单模板已接入，默认测试不访问网络。
- `acceptance-report` 已可读取私有真实样例清单并生成脱敏覆盖报告，追踪六个平台、
  小红书异常路径和本地音视频样例缺口。
- `acceptance-run` 已提供真实样例 v2 执行证据：逐项隔离运行完整应用管线，验证提取方法、
  文本、附件、AI 总结、导出、清理和预期错误码；报告不包含 URL、正文或本机路径。

**退出条件：**核心契约有单元测试，GUI/CLI 不需要了解平台实现。

## 阶段 1：迁移现有核心能力

**目标：**在新架构中恢复旧项目已验证行为。

- 为字幕、转写、结构化总结和笔记输出添加回归测试。

**退出条件：**B站和 YouTube 真实样例能生成与 PRD 契约一致的 Obsidian 笔记。
当前已有显式运行的集成验收框架、覆盖报告和执行报告生成器；私有真实样例数据与实际
12 案例全通过结果仍待补充。

## 阶段 2：短视频平台

**目标：**稳定支持抖音和小红书分享链接。

- 接受纯链接、Markdown 链接和整段分享文案。
- 抖音使用字幕优先、音频转写兜底。（已接入入口；真实样例待验收。）
- B站、YouTube 与抖音的 yt-dlp 路径已在字幕/媒体调用中白名单回写标题、作者、时长、
  发布时间和描述；描述内嵌 URL 会移除 token 与追踪参数。
- 小红书保留抓取所需 token，但在日志与笔记中移除追踪参数。（已接入。）
- 小红书图文保存正文与图片，不做 OCR。（公开笔记路径已接入。）
- 建立脱敏夹具、真实公开链接集成测试与过期 token 错误提示。

**退出条件：**两个平台均通过至少一个真实公开样例和离线夹具测试。

## 阶段 3：文章与播客

**目标：**支持微信公众号文章和小宇宙单集。

- 提取公众号标题、作者、正文、发布时间、图片与原始链接。（公开 HTML 可用字段已接入。）
- 将图片安全写入 Vault 附件目录并重写为相对引用。（已接入。）
- 提取小宇宙单集元数据、show notes、官方文稿或音频。
- 无官方文稿的播客走 Whisper，完成后清理音频。（已接入入口；真实样例待验收。）
- 长文与长音频已按自然边界分段总结并归并；模型请求支持重试，持续失败时使用完整原文
  生成本地确定性摘要并继续导出。
- 抓取所需分享 token 已与公开输出分离，不进入模型、笔记、清单、CLI 或诊断。

**退出条件：**图文附件可在 Obsidian 正常显示，播客有/无文稿两条路径均通过。

## 阶段 4：桌面产品化

**目标：**从开发者工具升级为可分发给普通用户的桌面产品。

- 首次设置：大模型连接测试、Whisper 模型和 Obsidian Vault 验证。（GUI 设置持久化、
  系统密钥链、大模型/Vault 测试笔记及 ffmpeg、yt-dlp、openai-whisper 轻量检查已接入。）
- 单链接与批量队列、单项取消、重试与结果操作。（队列、取消、重试、待导出草稿管理、仅重试导出、
  结果打开、摘要复制、Obsidian 深链、后台运行、标题/链接列、细粒度进度、耗时和失败诊断导出已接入 CLI/GUI。）
- 稳定进度事件，不将原始第三方日志当作产品交互。
- macOS 签名/公证、真实安装、升级。（未签名源码包、自包含构建路径、结构验证、新手说明、
  隐私说明、分发预验证、发行门禁清单和签名/Gatekeeper/公证票据严格验证已接入。）
- Windows 路径和打包产物已具备离线预验证；Windows 10/11 实机启动、中文路径及
  ffmpeg/yt-dlp 子进程仍待发行验收，门禁已写入随包发行清单。
- `evey2obs.task` v1.0 协议 manifest 已固化任务命令、进度事件、结果对象、稳定枚举和安全边界，
  CLI `protocol` 可直接输出给未来移动端或自动化客户端使用。

**退出条件：**六个平台通过 PRD 验收，非开发者可在 15 分钟内生成首篇笔记。

## 阶段 5：移动端准备

- 将任务命令、进度事件和结果固化为版本化协议。（`evey2obs.task` v1.0 manifest 已接入。）
- 评估 Android/iOS 本地处理与用户自托管处理节点。
- 实现移动系统“分享到 evey2obs”的最小原型。（`protocol-run` 已可执行分享 JSON 请求；
  原生 Android/iOS 分享扩展仍待实现。）

## 迁移评审清单

每次从旧项目迁移代码时都要回答：

- 这段代码属于平台适配、处理、应用编排还是导出？
- 是否携带了旧的全局变量、绝对路径或 UI 副作用？
- 是否可以使用领域模型和显式依赖代替字典与隐式环境读取？
- 旧行为是有意需求还是历史偶然？
- 是否有离线测试和敏感数据脱敏？
- 失败后是否会给用户可执行的下一步？

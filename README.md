# YT-live-cruise
自动转播无巡航版本
核心是将原本高度耦合的程式码，拆分成更清晰、更专业、更易于维护的模组，并围绕「以主播为中心的配置档案系统」来重组整个架构。

-----

### 1\. 核心架构与档案结构调整

放弃在主目录下散落 `yt_*.ini` 和 `stream_info_*.json` 档案的作法，改用更整洁的资料夹结构。

**新的档案结构提议：**

```
/Douyin-YouTube-Streamer/
├── credentials/                 # 【新增】集中存放所有YouTube凭证档案
│   ├── account1_token.json
│   └── account2_token.json
│
├── profiles/                    # 【新增】所有主播的独立设定档资料夹
│   ├── 11111111/                # 以主播ID命名的资料夹
│   │   ├── config.ini           # 该主播的所有设定
│   │   └── stream_info.json     # 该主播的YouTube固定推流码资讯
│   │
│   └── 22222222/
│       ├── config.ini
│       └── stream_info.json
│
├── manager.py                   # 【重构】主控台/仪表板 (UI)
├── streamer.py                  # 【重构】核心推流工作者
├── douyin.py                    # 【新增】独立的抖音抓流模组
├── yt.ini                       # (保留) 作为创建新主播时的预设模板
└── README.md
```

### 2\. 主界面 (manager.py) 功能重构

`manager.py` 将转变为一个视觉化的「仪表板」，所有操作和资讯都将围绕卡片式佈局展开。

#### 2.1. 卡片式佈局 (Dashboard)

  * **取代列表**：原本的 `CTkScrollableFrame` 中，每一行都将被一个更丰富的「主播卡片」(`StreamerCard` class) 所取代。
  * **卡片元素**：
    1.  **主播ID**：显示在卡片顶部。
    2.  **状态显示**：一个带有颜色和文字的标籤 (e.g., 🟢 正在推流, 🟡 正在检查, ⚪ 已停止, 🔴 错误)。
    3.  **实时推流时长**：一个标籤，从推流开始后每秒更新 (e.g., `推流时长: 01:23:45`)。
    4.  **分组设定**：一个下拉式选单 (`CTkOptionMenu`)，允许用户直接在卡片上修改该主播的分组。修改后会立即保存到该主播的 `config.ini` 档案中。
    5.  **操作按钮**：
          * `▶ 启动`
          * `■ 停止`
          * `⚙️ 设定`
          * `🗑️ 删除`

#### 2.2. 统一日志系统

  * **位置**：主界面下方保留一个大的 `CTkTextbox` 作为日志显示区。
  * **集中显示**：所有来自 `manager.py` 本身的操作日志，以及所有 `streamer.py` 后台进程回传的日志，都会被定向到这裡。
  * **日志等级与颜色**：
      * `streamer.py` 回传的日志将带有等级标籤，例如 `[INFO]`, `[WARN]`, `[ERROR]`。
      * `manager.py` 会根据这些标籤，使用 `tkinter.Text` 的 `tag_config` 功能为不同等级的日志设定不同的颜色（例如：错误为红色，警告为黄色）。
  * **清理按钮**：在日志区域旁增加一个「🧹 清理日志」按钮，点击后可清空当前的日志显示。

#### 2.3. 多用户凭证 (Token) 管理

  * **独立设定**：在每个主播的 `设定` 窗口中 (`EditSettingsWindow`)。
  * **图形化选择**：
      * 原本 `token_file` 的输入框将被一个显示当前档案名的标籤和一个「浏览...」按钮所取代。
      * 点击「浏览...」按钮会打开一个档案选择对话框，预设指向 `/credentials/` 目录。
      * 用户可以选择一个 `_token.json` 档案。储存后，`config.ini` 中只会记录档案名 (e.g., `token_file = account2_token.json`)。
      * `streamer.py` 在读取配置时，会自动将 `credentials/` 路径和档案名拼接起来，找到正确的凭证。

-----

### 3\. 后台功能 (streamer.py & douyin.py) 重构

后台将被拆分为两个模组，职责更分明。

#### 3.1. 独立的抖音抓流模组 (`douyin.py`)

这是一个全新的档案，专门负责从抖音获取直播资讯。

  * **核心功能**：建立一个名为 `DouyinHandler` 的类别，或一个名为 `get_stream_data` 的函式。
  * **稳定抓流**：其内部将完全採用您提供的 `test.py` 中的核心逻辑 (例如使用 Playwright 搭配特定的页面操作和网路请求拦截)。
  * **代理支持**：`get_stream_data` 函式将接受代理 URL 作为参数。例如 `get_stream_data(douyin_id, proxy_url)`。在 Playwright 启动时，会将此代理设定应用于浏览器实例，确保抓流过程通过指定的代理进行。
  * **返回值**：函式成功时返回 `(flv_url, title)`，失败时返回 `(None, None)`。

#### 3.2. 核心推流工作者 (`streamer.py`)

`streamer.py` 将不再包含任何 Playwright 或抓流的程式码，它只做三件事：读取配置、呼叫 `douyin.py`、呼叫 FFmpeg。

  * **日志处理（核心变更）**：

      * `streamer.py` **不再将日志写入任何档案**。
      * 它内部所有的 `print()` 语句都将被格式化，以便 `manager.py` 解析。
      * **格式范例**：
        ```python
        # 普通日志
        print("LOG:INFO:正在呼叫 douyin.py 获取直播资讯...")
        # 警告日志
        print("LOG:WARN:获取到的直播标题为空。")
        # 错误日志
        print("LOG:ERROR:FFmpeg 启动失败，返回码 1。")
        # 状态更新 (保留)
        print("STATUS:streaming")
        # 标题更新 (保留)
        print("TITLE:今天来做宫保鸡丁")
        ```
      * `manager.py` 的 `read_output` 执行绪会解析这些前缀，并将带有 `LOG:` 的讯息发送到统一日志区域（并上色），将 `STATUS:` 和 `TITLE:` 的讯息用于更新UI。

  * **防止 403 Forbidden 错误**：

      * 在 `_start_ffmpeg_stream` 函式中，组建 FFmpeg 命令时，将强制加入浏览器标头。
      * **程式码示例**：
        ```python
        # ... existing FFmpeg command building ...
        cmd = [
            ffmpeg_path,
            "-re",
            # 【新增】伪装 User-Agent
            "-user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            # 【新增】伪装 Referer
            "-headers", f"Referer: https://live.douyin.com/{douyin_id}\r\n",
            "-i", flv_url,
            # ... rest of the command ...
        ]
        ```

  * **呼叫 `douyin.py`**：

      * `streamer.py` 会 `import douyin`。
      * 在主循环中，它会从自己的 `config.ini` 读取代理设定，然后呼叫 `douyin.get_stream_data(douyin_id, proxy_url)` 来获取 `flv_url`。


1.  **结构清晰**：每个档案和资料夹的用途都非常明确，新用户更容易上手，也更方便未来的功能扩展。
2.  **稳定性提升**：通过整合有效的抓流方法、增加FFmpeg标头和完善的代理支持，可以显著降低抓流和推流失败的机率。
3.  **管理方便**：新的仪表板界面提供了更直观的资讯展示和更便捷的操作。多帐号凭证管理和按主播独立备份/迁移配置也变得非常简单。
4.  **易于除错**：统一日志系统集中了所有后台进程的输出，并以颜色区分，使得追踪问题变得前所未有的轻鬆。



pip install customtkinter configobj google-api-python-client google-auth-httplib2 google-auth-oauthlib pyperclip playwright
playwright install chromium

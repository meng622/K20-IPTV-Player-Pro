# K20 IPTV Player Pro 代码审查报告

- 审查日期：2026-10-19
- 审查对象：`E:\Harness\K20_Pro`（18 个 Python 文件，约 6,000 行）
- 审查方式：逐文件静态阅读 + 全模块导入检查 + 无头启动/关闭实测 + 关键交互最小复现 + PyInstaller 6 布局核对
- 代码改动：本文件最初为纯审查；后续已按“批次 A”修复了一部分，进度见下方。

## 修复进度（2026-10-19）

- [x] 搜索框被全局热键吞输入（已实测 `sport` 正常输入）
- [x] M3U 失败不再写空缓存、不再清空旧列表
- [x] 设置原子写入 + `.bak` + 损坏档保留 + 读回退
- [x] 文件日志 + `sys.excepthook`；接入 `errorOccurred` / `channelTimeout`
- [x] `logo_cache` / `hotkeys.json` 改用 `_script_dir` 绝对路径
- [x] 画面比例、缓冲大小、音量持久化
- [x] 切换分屏不再重开正在播/隐藏屏的串流；隐藏屏完全清空
- [x] 搜索框：点外部退出焦点、四个视图共用、切换列表清空
- [x] 全屏边缘面板：左缘频道、右缘节目表+刷新/关闭、上缘标题栏
- [x] 版本号统一为 `APP_VERSION = 1.2.0`（窗口标题/README）
- [x] 打包 DLL 路径改用 `sys._MEIPASS`；spec 支持 `K20_LIBS`；新增 `requirements.txt`
- [x] M3U BOM/GBK 编码探测（UTF-8-sig / GB18030 / Big5）
- [x] EPG 单源失败提示 / EPG URL 缓存校验
- [x] PiP：点击任务栏还原主窗口时自动退出 PiP
- [ ] PiP 的 mpv 窗口重绑定（需真机验证）
- [ ] 真实打包 + 干净机器测试（下一批）
- [ ] 死代码/重复实现/star import 整理（后续）

---

## 0. 总体结论

这个项目的**功能完成度相当高**：多源 M3U、Xtream、EPG 多源合并/繁简匹配、四屏、PiP、主题、收藏/历史、测速、截图、热键都已打通，模块拆分也基本清楚。全模块可以正常导入，无头启动实测成功拉取 121 个频道。

但目前更像“长期由 AI 增量补丁堆起来的作品”，主要问题不在功能多少，而在**边界条件、生命周期和工程化**：

1. **有 2 个会直接影响正常使用的交互/数据问题**：全局热键会吞掉搜索框输入；M3U 下载失败会把空列表写进当日缓存，之后一整天可能都启动为空。
2. **打包/分发链路没有闭环**：`.venv` 已损坏、没有 `requirements.txt`、spec 写死 `D:\Libs`，且 PyInstaller 6 的 `_internal` 布局与 `player_engine` 的 DLL 路径不一致。
3. **错误处理是“静默”的**：63 处 `print`、没有日志文件、没有 `sys.excepthook`；mpv 初始化失败和频道超时信号都没有接。
4. **大量死代码和重复实现**：EPG 的 sqlite 类、FastCache 的下载/解析路径、两套 M3U 解析、三套时间解析、四套频道名清洗，后续改一处很容易漏另一处。

建议按第 7 节的三个批次处理，不要一次性大重构。

---

## 1. P0：建议优先修（会影响正常使用/分发）

### 1.1 全局热键吞掉搜索框输入 ✅ 已实测

**位置**：`hotkey_and_help.py:144-158`

`HotkeyAndHelpManager` 把事件过滤器装在 `QApplication` 上，`eventFilter` 只排除了模态窗口，没有排除文本输入控件。因此焦点在搜索框时：

- 输入 `s` 触发截图；
- 输入 `p` 触发 PiP；
- 输入 `i` 切换统计；
- 方向键触发快进/快退/音量。

**实测**：在 QLineEdit 中输入 `sport`，实际得到 `ort`，同时触发了截图和 PiP。

**修复**：

```python
from PyQt6.QtWidgets import QLineEdit, QAbstractSpinBox, QTextEdit
from PyQt6.QtWidgets import QKeySequenceEdit

focus = QApplication.focusWidget()
if isinstance(focus, (QLineEdit, QAbstractSpinBox, QTextEdit, QKeySequenceEdit)):
    return False
if event.isAutoRepeat():
    return True
```

更好的做法是把这些动作改成 `QShortcut`（`Qt.ShortcutContext.WidgetWithChildrenShortcut`），让 Qt 自己处理焦点和冲突，而不是全局吞键。

---

### 1.2 M3U 下载失败会把空列表写进“今日缓存” ✅ 已确认（代码路径）

**位置**：`m3u_manager.py:118-126`、`main_window.py:483-542`、`fastcache_manager.py:232-252`

`M3UFetchWorker.run()` 在异常时先 `emit(error_signal)`，**随后仍然** `emit(finished_signal, [], "")`。`on_m3u_parsed` 不检查频道数，继续走 EPG/保存流程，最终 `_save_current_playlist_cache()` 把 `channels=[]` 写进 `*_channels.pkl` 并标记“今天已更新”。

后果：一次网络抖动、或订阅源临时 502，就可能把好缓存覆盖成空缓存；当天再启动 `_is_cache_valid()` 为真、`_load_from_parsed_cache()` 成功返回空列表，界面一直空，直到手动“刷新”或第二天。

**修复**：

- `M3UFetchWorker` 失败时不要发 `finished_signal`，或增加 `success` 参数；
- `on_m3u_parsed` 开头：`if not channels: return`（保留旧列表/旧缓存）；
- `_save_current_playlist_cache` 增加 `if not self.all_channels_data: return`；
- `_is_cache_valid` 也要求缓存里的 `channels` 非空。

---

### 1.3 未捕获异常会直接杀掉进程，且没有任何日志 ✅ 已实测

**位置**：全局；`main.py` 没有 `sys.excepthook`；`player_engine` 的 `errorOccurred` 未连接

PyQt6 对 slot 中未捕获的 Python 异常会调用 `qFatal`，进程直接退出（实测退出码 `0xC0000409`）。项目中大量 slot 存在 `None` 访问、索引访问、`QTimer.singleShot` 延迟回调等风险，例如：

- `epg_panel.py:234-236`：50ms 后按旧行号 `item(r)`，列表已重建时得到 `None`，`scrollToItem(None)` 抛异常；
- `screen_manager.py:166-191`：`blockSignals` 无 `try/finally`；
- `channel_panel.py:439-462`：`setUpdatesEnabled(False)` 无 `finally`。

同时所有 `print` 在打包为无控制台程序后没有输出，用户只能看到“闪退”。

**修复**（最小可用版）：

```python
import logging, sys, traceback
logging.basicConfig(
    filename=os.path.join(_script_dir, "k20.log"),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    encoding="utf-8",
)

def _excepthook(exc_type, exc, tb):
    logging.critical("Unhandled exception", exc_info=(exc_type, exc, tb))
    QMessageBox.critical(None, "K20 發生錯誤",
                         f"{exc_type.__name__}: {exc}\n\n詳細資訊已寫入 k20.log")
sys.excepthook = _excepthook
```

另外把 `player_engine.errorOccurred` 接到一个统一处理函数：记录日志、显示 OSD/弹窗；如果是 `mpv_initialize` 失败，自动降级 `hwdec=no` 再试一次。

---

### 1.4 设置文件写入不是原子操作，损坏后会静默重置并覆盖

**位置**：`config.py:122-151`

- `_load_settings()` 任何异常都 `return {}`，不备份、不提示；
- `_save_settings()` 直接 `open(..., "w")`，写到一半崩溃/断电就得到半截 JSON；
- 下次启动读到坏文件 → 返回 `{}` → 用户播放一次频道就 `_save_settings` 覆盖，订阅、收藏、历史全部丢失；
- 设置写在 exe 同目录。若装到 `C:\Program Files`，普通用户不可写，`_save_settings` 只打印一句“保存設置失敗”，然后继续运行，用户以为保存了。

**修复**：

1. 写入临时文件 + `os.replace`，并保留 `k20_settings.json.bak`；
2. 读取失败时先把坏文件改名为 `.corrupt-时间戳`，再尝试 `.bak`，并提示用户；
3. 首次启动检查目录可写；不可写就回退到 `%APPDATA%\K20_Pro\`（或提供“便携模式”开关）；
4. 增加配置 schema/版本号，至少校验 `m3u_sources`、`favorites_list` 是 list。

---

### 1.5 切换分屏会重开全部串流，包括被隐藏的屏幕

**位置**：`screen_manager.py:80-86, 116-121`

`set_screen_layout()` 先对 `i >= count` 的隐藏屏 `stop()`，但 `stop()` 不清 `_current_url`；随后：

```python
if w.has_media and not w._current_url:
    continue
QTimer.singleShot(idx * 200, lambda ...: w.play(w._current_url))
```

- 正在播的可见屏：`has_media=True`、`_current_url` 有值 → **被重新 play**，画面闪断、重新缓冲；
- 被隐藏的屏：`stop()` 后 `has_media=False`，但 `_current_url` 仍在 → 条件不成立 → **也被重新 play**，白白占带宽，四屏全部在后台拉流。

**修复**：删除 116-121 行的“重播”逻辑（mpv 在隐藏时本来就保留解码器/流），或只对 `idx < count and not w._current_url` 的屏做恢复；`stop()` 里不要保留误导性的 `_current_url`。

---

### 1.6 PiP 重新挂父窗口后，mpv 可能黑屏/冻结 ⚠️ 需真机实测

**位置**：`pip_manager.py:125, 154, 203-205`；`player_engine.py:117, 164`

PiP 把 `video_container` 从主窗口 `reparent` 到新的顶层窗口。Qt 在 reparent 原生窗口时通常会销毁并重建 HWND，而 mpv 的 `wid` 只在 `_init_mpv()` 时绑定一次。结果可能是：进入 PiP 后视频黑屏/停在旧位置，退出后也不恢复。

同类问题：`screen_manager.py:72-75` 对已经 `mpv_initialize` 的实例调用 `_set_option("demuxer-max-bytes", ...)`，但 mpv 选项只能在 initialize 前设置，**这行不会生效**（`set_aspect` 同理，见 2.1）。

**修复方向**：

- 最稳妥：进出 PiP 时不 reparent 播放器，改为在主窗口内做浮层/缩放；或
- 进入/退出 PiP 后销毁并重建 mpv 上下文（`mpv_terminate_destroy` + `_init_mpv`），重新绑定新 `winId`；或
- 若保持 reparent，至少在 `showEvent` 后重新 `mpv_set_property_string(ctx, "wid", ...)`（能否运行时改 wid 取决于 mpv 版本，需实测）。

---

### 1.7 启动时的 emoji `print` 在输出被重定向时会崩

**位置**：`channel_panel.py:154` 等 63 处 `print`

**实测**：在 GBK 管道下运行 `python main.py`（或任何把 stdout 重定向到文件/IDE 的启动方式），启动即崩：

```
UnicodeEncodeError: 'gbk' codec can't encode character '\U0001f680'
  at channel_panel.py:154
```

Windows 真实控制台因为 PEP 528 通常是 UTF-8，所以交互式运行不一定复现；但打包成 `console=False` 后 `print` 没有输出目标，日志/崩溃信息全部丢失，重定向到日志时又会复现。

**修复**：统一改 `logging`，或至少在 `main.py` 开头：

```python
for stream in (sys.stdout, sys.stderr):
    if stream and hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")
```

---

## 2. P1：功能缺陷（用户能感知，但不至于崩）

### 2.1 画面比例菜单实际无效

`player_engine.py:369-375` 的 `set_aspect()` 调用 `_set_option("video-aspect-override", ...)`，但此时 mpv 已经 initialize，选项不再生效（`mpv_set_option_string` 只允许在 init 前）。另外：

- “預設 (原始)”传 `None`，走 `not ratio` 分支；
- “填滿畫面”传 `-1`，`ratio == "-1"` 为假、`not -1` 为假，最终仍写 `-1`，和“原始”没区别。

**修复**：

```python
if ratio is None:                       # 原始
    self._set_property_string("video-aspect-override", "no")
    self._set_property_string("keepaspect", "yes")
elif ratio == "fill":                   # 填滿
    self._set_property_string("keepaspect", "no")
else:
    self._set_property_string("keepaspect", "yes")
    self._set_property_string("video-aspect-override", str(ratio))
```

### 2.2 “緩衝區大小”设置是摆设

- `dialogs.py:107` 保存 `cache_mb`；
- `hotkey_and_help.py:209` 只更新 `win.cache_mb`；
- `main_window.py:311` 用 `self.config.get("cache_mb", 100)`，但 `self.config` 在 67 行初始化为 `{}` 后**从未写入**，所以永远是 100；
- `player_engine.py:37` 保存了 `self.cache_mb`，但 `_init_mpv()` 里完全没用，硬编码 30/15 MB。

**修复**：`MpvEmbedWidget._init_mpv()` 使用 `self.cache_mb` 计算 `demuxer-max-bytes`/`cache-secs`；设置对话框保存后，对现有播放器重建或提供“重启生效”提示；删掉 `self.config` 这条死路。

### 2.3 音量不保存、启动也不恢复

`control_bar.py:105` 固定 `setValue(100)`；`main_window.set_volume()` 只改当前 mpv，不写 `_settings["volume"]`；全项目没有任何地方读取保存的音量。结果每次启动都是 100。

**修复**：`_settings.get("volume", 100)` 在播放器初始化后应用；`set_volume` 用 300ms 防抖写回设置。

### 2.4 `errorOccurred` / `channelTimeout` 都没有接

- `player_engine.py:28, 179, 224` 发出 `errorOccurred`，但 `main_window` 没有 connect → mpv 初始化失败/加载失败只打印，用户看到黑屏。
- `player_engine.py:29, 237` 发出 `channelTimeout`，也没有 connect → 5 秒无画面时只弹一句 OSD，不做重试/切换。

**修复**：连接这两个信号；`channelTimeout` 可以自动重试一次，再失败则提示并跳到下一个频道；`errorOccurred` 弹窗并写日志。

### 2.5 EPG 全部下载失败时，UI 把“空”当成“成功”

`epg_manager.py:375-382` 的 `run()` 无论每个源成功与否都 `emit(merged)`；`_fetch_and_parse` 的异常只 `print`（465-466）。所有源都失败时 `merged={}`，`on_epg_memory_loaded({})` 照常走完进度条、保存空 EPG、解锁界面，用户只看到空白面板，不知道是网络问题还是源没有节目。

**修复**：`finished_signal` 改为 `pyqtSignal(dict, list)` 带上失败 URL/原因；`on_epg_memory_loaded` 在空数据且 errors 非空时显示“EPG 下載失敗：…”，并允许重试。

### 2.6 EPG 缓存不校验 EPG URL

`fastcache_manager.py:260-264` 只校验 `version` 和 `m3u_url`。用户改了某个订阅的 EPG 地址后，当天仍会从旧缓存加载旧 EPG，并把旧 `epg_url` 写回实例（272 行）。

**修复**：把 `epg_url`/`epg_hash` 纳入缓存校验；不一致就重建；或在 `_save_parsed_cache` 里同时保存配置的 EPG。

### 2.7 M3U 解析只认 UTF-8，BOM 会让 EPG 头失效

`m3u_manager.py:62-66` 对网络流逐行 `decode('utf-8', errors='ignore')`，本地文件 `open(..., encoding='utf-8', errors='ignore')`。

- GBK/GB18030 的中文频道名会被丢掉或乱码；
- UTF-8 BOM 会保留在首行：`'\ufeff#EXTM3U'`，`startswith('#EXTM3U')` 为 False（已实测），于是头部的 `x-tvg-url` 完全不会被提取，EPG 静默缺失。

**修复**：

```python
raw = response.read()
text = None
for enc in ("utf-8-sig", "gb18030", "big5"):
    try:
        text = raw.decode(enc)
        break
    except UnicodeDecodeError:
        continue
if text is None:
    text = raw.decode("utf-8", errors="replace")
```

或者用 `charset-normalizer`（requests 已依赖）做探测；先 `lstrip('\ufeff')`。

### 2.8 台标缓存路径相对 CWD，线程只增不减

`channel_panel.py:738-741` 用 `'logo_cache'` 相对当前工作目录，而 `config.py:169-171` 在 `_script_dir/logo_cache` 建了目录。打包后 `main.py` 又 `chdir(_MEIPASS)`，于是台标写进 `_internal/logo_cache`，和 `_script_dir/logo_cache` 不是同一个地方。

`750-766`：每个缺图频道新建 `LogoFetchThread`，append 到 `_logo_threads` 后**永不移除**；下载失败时线程不 emit 信号，URL 永久留在 `_logo_download_set`，同会话不再重试。

**修复**：用 `_script_dir` 拼路径；改用 `QThreadPool` 限并发（例如 4）；线程 finished 后 `deleteLater` 并从列表移除；失败路径也清理 `_logo_download_set`，缓存文件为 0 字节/HTML 时删除重下。

### 2.9 历史/本地视图的收藏按钮被删掉

`channel_panel.py:321-329` 认为“布局里最后一个是旧按钮”，但 `_get_channel_row_widget()` 最后添加的是**星标按钮**（838 行）。因此切到“最近播放/本地媒体”时，星标被 `deleteLater()`，换成删除按钮。

结果：这两个视图不能收藏；同时 `local_media_list` 完全没有落盘（842-869），重启就丢；`remove_history_or_local_item` 用 `ch in target_list` 判断身份（882），但列表项里存的可能是 `all_match` 对象（317 行），删除常常不生效。

**修复**：按 `role="del_btn"` 精确查找旧删除按钮，不要动星标；`local_media_list` 增删时写回 `_settings`；删除按 URL 匹配。

### 2.10 热键配置路径相对 CWD，保存无异常处理

`hotkey_and_help.py:12` 默认 `config_file="hotkeys.json"`，`save_hotkeys()` 直接 `open(..., "w")`。打包后 `main.py` chdir 到 `_MEIPASS`，会去 `_internal/hotkeys.json` 读写；spec 又没有把 `hotkeys.json` 打进去 → 用户自定义热键丢失，写入还可能因安装目录只读而抛异常。

**修复**：`os.path.join(_script_dir, "hotkeys.json")`；写入加 try/except + 原子替换；spec 的 `datas` 加入 `('hotkeys.json', '.')`。

### 2.11 `_set_option` 在运行时被误用（同类问题）

除 2.1 外：

- `screen_manager.py:75` 的 `demuxer-max-bytes` 不会生效；
- `player_engine.toggle_hw()` 用的是 `_set_property_string`，这个是对的；
- 任何播放开始后的 `set_aspect`/缓存调整都应走 `set_property`。

建议给 `MpvEmbedWidget` 增加明确的 `set_option_before_init()` 和 `set_property()` 两个入口，避免后续再写错。

---

## 3. P2：代码整理（“能用但会越来越难改”）

### 3.1 死代码清单

| 位置 | 内容 | 说明 |
|---|---|---|
| `epg_manager.py:82-338` | `EPGDatabase`、`EPGDownloaderWorker` | 只 import/实例化，方法从未调用；仍创建 20 KB sqlite；含 `CERT_NONE` |
| `fastcache_manager.py:91-383` | `_download_file`/`_parse_m3u`/`_parse_epg`/`load`/`refresh`/`auto_update_check` | 当前只用到 `_is_cache_valid`、`_load_from_parsed_cache`、`_save_parsed_cache`、`_set_epg_url`、字段；下载/解析全走 `M3UFetchWorker`/`MemoryEPGWorker` |
| `main_window.py:1249-1257` | `set_quality_filter` | 实际连接的是 `channel_mgr.set_quality_filter`，此方法从未被调用 |
| `main_window.py:60,67,65,1284` | `self.channels`、`self.config`、`self.is_pip_mode`、`_event_filter_install_for_widgets` | 从不写入/被覆盖/被替代 |
| `channel_panel.py:44-51` | `_clean_epg_key` | 仅被 import，无调用，且与 `normalize_channel_key` 重复 |
| `config.py:115-119` | `get_resource_path` | 无调用；且 `abspath(".")` 依赖 CWD |
| `player_engine.py` | `pauseChanged`、`self.cache_mb` | 信号未连接；字段未使用 |
| `widgets.py` 早期注释 | “解決圓角黑邊” | 实际只设透明/无边框，没有绘制圆角 |

清理这些大约能减少 500-700 行，且不会改变行为。建议用 `ruff`/`pyflakes` 先扫一遍未使用 import/变量，再人工删。

### 3.2 重复实现（最容易“改一处漏一处”）

| 功能 | 现有实现 |
|---|---|
| 频道名清洗 | `channel_panel._clean_epg_key`、`epg_manager.clean_channel_name`、`channel_panel` 台标正则（725）、`channel_panel` 显示名正则（788）、`epg_panel` 自己的正则（136-137） |
| XMLTV 时间解析 | `epg_manager.MemoryEPGWorker._parse_xmltv_time`（371）、`epg_panel._format_time_range`（113-117）、`epg_panel.update_epg_content`（211-218）、`channel_panel._get_current_epg_title`（691-695） |
| M3U 解析 | `m3u_manager.M3UFetchWorker.run`、`fastcache_manager._parse_m3u`（死） |
| EPG 解析 | `epg_manager.MemoryEPGWorker`、`fastcache_manager._parse_epg`（死）、`EPGDownloaderWorker`（死） |
| SVG 图标按钮 | `main_window._set_btn_svg_icon`、`control_bar._set_btn_svg_icon` |
| 主题色 | `skin.py` 主题 dict、`channel_panel` 硬编码 `#00f2fe/#ef4444/...`、`m3u_manager` 默认色、`screen_manager` `#2a2a38` |

建议抽成 3 个共享模块：

- `channel_names.py`：`clean_channel_name`、`normalize_channel_key`、`channel_match_keys`；
- `xmltv_time.py`：`parse_xmltv_time`（带 `%z`）、`format_range`、`is_current`；
- `icon_utils.py`：带 `(name,color,size,dpr)` 缓存的 `get_icon`，两个 `_set_btn_svg_icon` 合并。

### 3.3 时间解析忽略时区（影响显示与“正在播放”）

`epg_manager.py:371` 的 `_parse_xmltv_time` 只取 `.split()[0][:14]`，丢弃 `+0800/+0000`；`epg_panel` 和 `channel_panel` 也用同样的 naive 解析并与本地 `datetime.now()` 比较。若 EPG 源是 UTC，节目时间会整体差 8 小时，“当前节目”标记也会错。

**修复**：统一用

```python
datetime.strptime(value, "%Y%m%d%H%M%S %z").astimezone()
```

并兼容没有时区的旧格式。

### 3.4 GUI 线程上的重活

- `main_window.py:434`：启动时同步 `pickle.load` 5.9-10.2 MB 的 `*_channels.pkl`（实测缓存文件大小），再 `build_epg_lookup`；启动会卡一下。
- `main_window.py:421`：EPG 加载完成后在 GUI 线程 `pickle.dump` 同一量级数据，界面可能冻结数百毫秒。
- `channel_panel.py:799` + `675-702`：每渲染一行频道都重新做 EPG 当前节目查找（ctypes 繁简转换 + 逐节目 `strptime`），30 行/批，滚动/搜索时明显。
- `skin.py:758-782`：`IconManager.get_icon` 没有缓存，每行两个图标都重新读 SVG/渲染。

**修复**：EPG 载入后预算 `channel_url -> current_program` 字典，渲染时 O(1) 查；图标加类级缓存；pickle 放 worker 或至少用 `QTimer.singleShot(0, ...)` 分片。

### 3.5 线程生命周期

| 位置 | 风险 |
|---|---|
| `main_window.py:455-464` | 旧 `m3u_worker` `quit()+wait(1000)`，超时后仍替换引用 → “QThread: Destroyed while thread is still running” |
| `main_window.py:575` | 每次 `load_epg` 新建 worker 覆盖属性，旧 worker 可能仍在跑 |
| `channel_panel.py:750-766` | 台标线程只增不减 |
| `channel_panel.py:600-607` | 停止后立刻重启测速，旧 `finished` 回调会操作新 `ping_worker` |
| 全局 | 没有 `closeEvent`/`aboutToQuit` 统一停止 worker、销毁 mpv |

**修复**：每个 worker 只允许一个在跑；替换前 `requestInterruption()` + `wait()`；在 `closeEvent` 里停止所有 worker 并 `mpv_terminate_destroy`。

### 3.6 `config.py` 的 star import 架构

`from config import *` 出现在每个模块，而 `config.py` 又 import 了 20 多个标准库/第三方库和 80 多个 Qt 名称。结果是：

- 每个模块的依赖不可见（用了 `QLabel` 却不知道从哪来）；
- `config` 变成一个“万能命名空间”，改 import 容易连锁出错；
- 无 `__all__`，新增名称会意外泄漏；
- `config` 在 import 时创建目录、改 PATH、写默认设置，有副作用。

**整理建议**（渐进，不必一次做完）：

1. 新增 `paths.py`（`_script_dir`、`SETTINGS_FILE`、缓存目录），只放路径；
2. 各模块显式 `from PyQt6.QtWidgets import QLabel, ...`；
3. `config.py` 只保留设置读写和常量；
4. 用 `ruff check --select F401,F821,F841` 清理未使用 import/未定义名/未使用变量。

### 3.7 其他值得顺手修的

- `main.py:1,12` 重复 `from config import *`；`7-10` 的 `chdir(sys._MEIPASS)` 没有必要，反而让 `logo_cache`/`hotkeys.json` 的相对路径跑偏，建议删掉。
- `skin.py:424` 少写 `::handle`（写成 `QDialog QScrollBar:horizontal`），且 446-466 又重复定义 QDialog 水平滚动条，互相冲突。
- `skin.py:712-719` 全屏时把整份 600+ 行 QSS 设置给 `bottom_bar`，退出时置 `""` 会清掉控件自身样式；`get_skin_stylesheet` 每次 apply 调用两次。
- `control_bar.py:238-244` 读 `main_win.is_pip_mode`，但主窗口这个属性从不更新（只有 `PiPManager.is_pip_mode`）→ 早退分支永远不生效；`269` 的 `middle_unit` 定义了没用。
- `control_bar.py:313-345` 每次淡入/淡出新建 `QTimer`，旧的只 stop 不 delete。
- `dialogs.py:57-64` 的 `parent.current_theme_config.get('gradient')` 可能为 `None`，`set_theme_colors(*None)` 会 TypeError。
- `dev_run.py:23-25,32` 递归监控整个目录（包括 `.venv`、`__pycache__`），且每次保存立即 kill/restart，无防抖；建议排除 `.venv`、`build`、`dist`、缓存目录，并加 300ms debounce。
- ~~`main_window.py:30,857` 版本号写死 `v1.0.0`~~ → 已改为 `config.APP_VERSION = "1.2.0"`，窗口标题统一引用。
- 63 处 `print` 中有不少带 emoji 的调试输出（频道名、EPG 名），建议改 `logging.debug`，生产日志只留关键事件。

---

## 4. 打包与工程化（这是目前最大的“交付缺口”）

### 4.1 `.venv` 已经损坏

`.venv\pyvenv.cfg` 内容：

```
home = C:\Program Files\Python312
command = C:\Program Files\Python312\python.exe -m venv e:\player\v21-v40\K20_Pro_v39-2\.venv
```

- `C:\Program Files\Python312\python.exe` 不存在（实际 Python 在 `C:\Users\meng\AppData\Local\Programs\Python\Python312`）；
- venv 是在旧路径 `e:\player\v21-v40\...` 创建的，复制到 `E:\Harness` 后路径失效。

现在 `.\\.venv\\Scripts\\python.exe -V` 直接报 `No Python at 'C:\Program Files\Python312\python.exe'`。交接笔记里的 `python main.py` 如果先 activate 了这个 venv，会失败。

**修复**：

```powershell
Remove-Item -Recurse -Force .venv
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -U pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 4.2 没有依赖清单

全项目第三方依赖只有 3 个（AST 扫描结果）：`PyQt6`、`requests`、`watchdog`。建议新增：

`requirements.txt`

```
PyQt6==6.11.0
requests>=2.32
watchdog>=4.0
```

`requirements-dev.txt`

```
-r requirements.txt
pyinstaller==6.22.3
ruff>=0.6
pytest>=8.0
```

### 4.3 spec 写死 `D:\Libs`，且与 PyInstaller 6 的 `_internal` 布局不匹配

`K20_IPTV_Player-internal.spec:6` 写死 `SHARED_LIBS = r"D:\Libs"`，换机器/换目录就失败；`12-18` 把 `libmpv-2.dll`、`ffmpeg.exe`、`yt-dlp.exe` 作为 `datas` 放到 `'.'`。

PyInstaller 6 默认把 datas/binaries 放进 `_internal` 子目录（6.22 源码 `EXE` 的 `contents_directory` 默认 `"_internal"`），而 `player_engine.py:8-19` 在 frozen 时用 `os.path.dirname(sys.executable)` 找 DLL，也就是 exe 根目录，**找不到 `_internal\libmpv-2.dll`**。同理 `config.py:157-166` 把 exe 根目录加进 PATH，`ffmpeg/yt-dlp` 也可能找不到。

**修复（推荐）**：

`player_engine.py`

```python
def _app_base_dir():
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.environ.get("K20_LIBS", r"D:\Libs")
```

spec 里用环境变量 + 相对目录兜底：

```python
SHARED_LIBS = os.environ.get("K20_LIBS", os.path.join(SPECPATH, "libs"))
```

并把 DLL 放 `binaries=[(os.path.join(SHARED_LIBS, name), ".") for name in (...)]`，或在 `EXE(..., contents_directory=".")` 恢复旧扁平布局。两种方式选一种，别混用。

同时补：

- `datas` 加入 `('hotkeys.json', '.')`；
- `EXE(..., version='version_info.txt')`；
- `upx=False`（对 123 MB 的 libmpv 做 UPX 收益有限，且可能破坏 DLL）；
- 在干净虚拟机/另一台机器上实测启动，不要只在本机 `dist` 目录里跑。

### 4.4 设置/缓存写在 exe 目录

便携是优点，但装到 `Program Files` 就会写失败（见 1.4）。建议明确一种模式：

- 便携模式：设置/缓存放 exe 同目录，启动时检测可写；
- 安装模式：放 `%APPDATA%\K20_Pro\`，日志也放这里。

### 4.5 工程化缺项

- 没有 `README.md`（只有交接笔记），没有安装/运行/打包/依赖说明；
- 没有 `LICENSE` 和第三方（libmpv/ffmpeg/yt-dlp）许可说明；
- 没有测试，纯函数（`parse_xtream_url`、`clean_channel_name`、`channel_match_keys`、XMLTV 时间、M3U 解析）最适合先补 pytest；
- Git 只有 2 个 commit、1 个分支，没有 tag（交接笔记说会打 `v39-3`，但实际没有）；
- `k20_settings.json` 被 Git 跟踪（见 5.1）。

---

## 5. 安全与隐私

### 5.1 `k20_settings.json` 含明文账号密码，且已入库

订阅 URL 里带 `username=...&password=...`，该文件被 `.gitignore` 特意保留入库，并在 M3U 管理界面的 URL 标签里**完整显示**（`m3u_manager.py:496-498`）。截图、录屏、分享仓库都会泄露。

**建议**：

- `git rm --cached k20_settings.json`，加入 `.gitignore`；
- 提供 `k20_settings.example.json`（占位符）；
- UI 列表把 `username/password` 参数打码；
- 如果这个仓库曾经推到任何地方，换掉 Xtream 密码。

### 5.2 `CERT_NONE`（死代码里）

`epg_manager.py:238-241` 关闭了主机名校验和证书校验。当前 `EPGDownloaderWorker` 是死代码，所以还没实际影响；但一旦有人把它接回去，就是可被中间人替换 EPG 内容的入口。删除该类，或恢复默认证书校验。

### 5.3 pickle 缓存

`fastcache_manager.py:254-277` 直接 `pickle.load` 本地缓存。缓存目录可写者可以构造恶意 pickle 执行任意代码。对本机单用户工具风险不高，但如果以后支持“导入别人的缓存/配置”，建议改 JSON 或加 HMAC。

### 5.4 PATH 注入

`config.py:164-166` 把 `_script_dir` 加到 PATH 最前面。便携目录通常可写，属于低风险 DLL 预加载面；如果做安装版，建议不要无条件加 PATH，改用绝对路径调用 ffmpeg/yt-dlp。

---

## 6. 已实测/已核对的事实

| 项目 | 结果 |
|---|---|
| 全模块导入 | `config, player_engine, m3u_manager, epg_manager, fastcache_manager, channel_panel, control_bar, skin, widgets, dialogs, screen_manager, pip_manager, drop_manager, hotkey_and_help, epg_panel` 全部 OK |
| 无头启动 | 窗口构造成功，M3U 拉取 121 个频道，EPG 开始下载；mpv 在 offscreen 下初始化失败（无 GPU，属预期） |
| 全局热键 | QLineEdit 输入 `sport` → 实际 `ort`，触发截图 + PiP |
| 未捕获 slot 异常 | 进程以 `0xC0000409` 退出（PyQt6 qFatal） |
| UTF-8 BOM | `'\ufeff#EXTM3U'.strip().startswith('#EXTM3U')` 为 False |
| 设置文件编码 | 当前 `k20_settings.json` 是合法 UTF-8，之前的“乱码”是 PowerShell 控制台显示问题，不是文件损坏 |
| 缓存大小 | 4 个 `*_channels.pkl` 分别约 5.9 / 10.2 / 9.5 / 5.9 MB |
| `.venv` | `No Python at 'C:\Program Files\Python312\python.exe'` |
| PyInstaller | 6.22.3；默认 `contents_directory="_internal"`，spec 未覆盖 |

---

## 7. 建议的修复顺序

### 批次 A：半天内，低风险、立刻见效

1. 热键过滤器跳过文本输入 + `isAutoRepeat`（1.1）。
2. M3U 失败不写空缓存（1.2）。
3. 加 `sys.excepthook` + 文件日志；接 `errorOccurred`/`channelTimeout`（1.3、2.4）。
4. 设置原子写入 + `.bak` + 失败提示（1.4）。
5. 删掉 `main.py` 的 `chdir(_MEIPASS)`，把 `logo_cache`、`hotkeys.json` 改成 `_script_dir` 绝对路径（1.7、2.8、2.10）。
6. 修正 `set_aspect`、`cache_mb`、音量持久化（2.1-2.3）。

**验收**：搜索框能正常输入；断网启动不会清空列表；关掉 EPG 源时能看到错误提示；换主题/全屏不再重载列表；比例/缓冲/音量设置实际生效。

### 批次 B：1-2 天，影响分发和播放稳定性

1. 重建 venv、补 `requirements*.txt`（4.1、4.2）。
2. 修 spec/`_MEIPASS`/`hotkeys.json`/版本资源，在干净机器上打包实测（4.3）。
3. 修布局切换重播（1.5）；PiP 真机验证并按结果处理 HWND（1.6）。
4. EPG 失败信号、EPG URL 缓存校验、M3U BOM/GBK（2.5-2.7）。
5. 台标线程池/路径、历史/本地视图（2.8-2.9）。
6. worker 生命周期与 `closeEvent`（3.5）。

**验收**：打包后的 exe 在另一台没有 `D:\Libs` 的机器能启动、播放、截图、换主题、进 PiP；切换 1/2/3/4 屏不重开流；断网/坏源有明确提示。

### 批次 C：整理与长期可维护性

1. 删除死代码（3.1），合并重复实现（3.2），统一时间解析（3.3）。
2. 拆 `config` 的 star import，显式 import；引入 `ruff`（3.6）。
3. GUI 线程减负：EPG 当前节目缓存、图标缓存、pickle 移 worker（3.4）。
4. 补 README、pytest、Git tag（4.5）。
5. 处理设置凭据入库（5.1）。

---

## 8. 一句话总结

**先修“热键吞输入、空缓存覆盖、打包 DLL 路径、静默崩溃”这四件事，再谈重构。** 这个项目的功能已经足够完整，真正缺的是发布前的收尾：依赖/虚拟环境、打包验证、日志与错误提示、以及把 AI 增量补丁留下的死代码和重复实现收敛掉。

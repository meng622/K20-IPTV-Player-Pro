<img width="256" height="256" alt="httpsicon-icons comicon-play-video297750-256px" src="https://github.com/user-attachments/assets/ff292756-db74-4cec-a2be-209697a29f00" />

# K20 IPTV Player Pro

Windows 桌面 IPTV 播放器（PyQt6 + libmpv），目前版本 **v1.2.1**。

## 功能

- 多源 M3U / Xtream 訂閱，支援 UTF-8（含 BOM）、GB18030、Big5 播放列表
- 多源 EPG 合併、繁簡頻道名匹配、節目表與簡介
- 直播 / 我的收藏 / 最近播放 / 本地媒體四個視圖，共用搜尋
- 單屏 / 雙屏 / 三屏 / 四屏，PiP 畫中畫
- 全屏邊緣面板：左緣頻道列表、右緣標題欄＋節目表
- 主題切換、截圖、測速、自訂快捷鍵、拖放檔案
- 播放清單與 EPG 本地快取（可重建）

## 環境需求

- Windows 10 / 11 x64
- Python 3.12
- `libmpv-2.dll`、`ffmpeg.exe`、`yt-dlp.exe`

三大核心放哪裡都可以，程式會自動依序找：

1. 進階：`K20_LIBS` 環境變數指定的目錄（沒設定就跳過）
2. `K20_Pro\`（和 `main.py` 同目錄）
3. `K20_Pro\libs\`
4. `D:\Libs\`

打包後會優先找 `_internal`（`sys._MEIPASS`）裡隨程式附帶的核心。

## 最快執行

```powershell
python main.py
```

如果系統 Python 還缺套件：

```powershell
python -m pip install -r requirements.txt
```

## 可選：建立 venv

想讓這個專案的套件跟其他專案隔離時才需要：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

## 打包

```powershell
pyinstaller K20_IPTV_Player-internal.spec
```

spec 會用同樣的順序找核心；找不到會直接列出缺少的檔名和搜尋過的路徑。PyInstaller 6 會把 DLL 放進 `_internal`，程式用 `sys._MEIPASS` 查找。

> `K20_LIBS` 只是給「核心放在其他磁碟/目錄」的人用的可選開關，一般情況不用設定。

## 設定與資料

- `k20_settings.json`：訂閱、收藏、歷史、音量、主題。**含明文帳密，不進 Git**；新環境請複製 `k20_settings.example.json`。
- `hotkeys.json`：自訂快捷鍵。
- `epg_cache/`、`logo_cache/`、`snapshots/`：可重建快取/截圖。
- `k20.log`：執行日誌。

## 版本規則

`major.minor.patch`：

- major：不相容變更
- minor：新增功能（本次全屏邊緣面板、跨視圖搜尋）
- patch：向後相容的錯誤修正

## 授權

本專案採用 MIT License，見 [LICENSE](LICENSE)。

`libmpv` / `ffmpeg` / `yt-dlp` 為第三方元件，散布時請各自確認其授權與再散布要求。

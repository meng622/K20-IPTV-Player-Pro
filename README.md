# K20 IPTV Player Pro

Windows 桌面 IPTV 播放器（PyQt6 + libmpv），目前版本 **v1.2.0**。

## 功能

- 多源 M3U / Xtream 訂閱，支援 UTF-8（含 BOM）、GB18030、Big5 播放列表
- 多源 EPG 合併、繁簡頻道名匹配、節目表與簡介
- 直播 / 我的收藏 / 最近播放 / 本地媒體四個視圖，共用搜尋
- 單屏 / 雙屏 / 三屏 / 四屏，PiP 畫中畫
- 全屏邊緣面板：左緣頻道列表、右緣節目表、上緣標題欄
- 主題切換、截圖、測速、自訂快捷鍵、拖放檔案
- 播放清單與 EPG 本地快取（可重建）

## 環境需求

- Windows 10 / 11 x64
- Python 3.12
- `libmpv-2.dll`、`ffmpeg.exe`、`yt-dlp.exe`（開發時預設放 `D:\Libs`，可用 `K20_LIBS` 覆寫）

## 開發執行

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

若 `D:\Libs` 不存在，先設定：

```powershell
$env:K20_LIBS = "你的\libs\目錄"
```

## 打包

```powershell
$env:K20_LIBS = "D:\Libs"
pyinstaller K20_IPTV_Player-internal.spec
```

PyInstaller 6 會把 DLL 放進 `_internal`，程式已用 `sys._MEIPASS` 查找。

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

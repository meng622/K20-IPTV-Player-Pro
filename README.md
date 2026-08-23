# K20 IPTV Player Pro (Editor Version)
### 專為 M3U 直播與多屏觀看打造的高效能播放器
### A High-Performance Media Player Built for M3U Live Streaming & Multi-Screen Viewing

[繁體中文](https://www.google.com/search?q=%23%E7%B9%81%E9%AB%94%E4%B8%AD%E6%96%87) | [English](https://www.google.com/search?q=%23english)

---

## 繁體中文

### 簡介

**K20 IPTV Player Pro (Editor Version)** 是一款基於 PyQt6 與 libmpv-2.dll 開發的高效能多功能媒體播放器。本專案衍生自原始 **K20 Player**，核心深度魔改與重構的高效能媒體播放器。專為 IPTV/M3U 直播源優化，支援多屏分屏、畫中畫 (PiP) 及極速頻道加載。並在 **Gemini AI** 的協同合作下完成架構重構、效能優化與功能擴充。

### 核心特色

* 📺 **多屏分屏播放**：支援 1~4 分屏同時播放，獨佔焦點聲音切換與獨立選單。
* 🖼️ **畫中畫模式 (PiP)**：一鍵切換懸浮小視窗，具備強行搶焦點機制，支援全域快捷鍵。
* ⌨️ **全域自訂快捷鍵**：支援全螢幕、快進快退、截圖 (S)、PiP (P) 等靈活自訂按鍵。
* 📋 **EPG 與 M3U 管理**：整合節目表解析與動態播放清單管理。
* 🎨 **動態主題 UI**：現代化極簡漸變進度條與主題配色切換。

### 最新優化與修復

* ⚡ **M3U 解析與渲染效能優化**：重構進度條 Signal 發送機制（改為每 1% 觸發一次），大幅降低背景線程對 UI 主線程的重繪壓力，徹底解決加載大容量 M3U 清單時的畫面卡頓問題。
* ⏳ **加載狀態與反饋同步**：導入 `is_m3u_loading` 主控標誌與即時 UI 觸發機制，消除切換訂閱源時出現的黑屏與「一瞬即逝」誤報問題，確保「正在加載...」提示與進度條完美同步。
* 🛡️ **多線程數據交接防錯**：優化背景 Worker 與 UI 視窗的狀態判定邏輯，解決交接微秒級時間差導致的 Race Condition 與 NameError 等潛在崩潰漏洞。

### 特別致謝

* 本專案基於 **K20 Player** 基礎進行二次開發。
* 特別感謝 **Gemini AI** 在代碼重構、Bug 定位與邏輯優化上的全力協助。

### 許可證

本專案採用 [MIT License](https://www.google.com/search?q=LICENSE) 開源許可證。

---

## English

### Overview

**K20 IPTV Player Pro (Editor Version)** is a high-performance, multi-functional media player built with PyQt6 and `libmpv-2.dll`. Derived from the original **K20 Player**, this project features a deeply modded and restructured core specifically optimized for IPTV/M3U live streams—supporting multi-screen split views, Picture-in-Picture (PiP), and ultra-fast channel loading. Architecture refactoring, performance optimizations, and feature enhancements were completed in collaboration with **Gemini AI**.

### Key Features

* 📺 **Multi-Screen Playback**: Supports 1 to 4 split-screen views with active audio focus sync and individual screen controls.
* 🖼️ **Picture-in-Picture (PiP)**: Smooth floating window mode with auto-focus recovery and global hotkey support.
* ⌨️ **Global Custom Hotkeys**: Fully customizable shortcuts for Play/Pause, Seek, Snapshot (S), PiP (P), and Fullscreen.
* 📋 **EPG & M3U Management**: Integrated stream playlist parser and program guide viewer.
* 🎨 **Dynamic UI Themes**: Modern aesthetic featuring flat gradient sliders and customizable skin themes.

### Recent Optimizations & Fixes

* ⚡ **M3U Parsing & Rendering Performance**: Refactored progress signal emissions to 1% step intervals, drastically reducing UI thread re-render overhead and eliminating UI freezing/stuttering during large M3U processing.
* ⏳ **Synchronized Loading State Feedback**: Introduced `is_m3u_loading` master state tracking and immediate UI re-rendering to eliminate black screen gaps and premature false-positive "Failed to Load" error flashes.
* 🛡️ **Thread Synchronization & Race Condition Guard**: Improved data handoff logic between background worker threads and the UI panel, resolving microsecond timing issues and preventing runtime `NameError` bugs.

### Acknowledgments

* Based on the original **K20 Player**.
* Co-developed and optimized with **Gemini AI** for modular architecture refactoring and debugging.

### License

This project is licensed under the [MIT License](https://www.google.com/search?q=LICENSE).

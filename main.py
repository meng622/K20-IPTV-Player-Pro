from config import *  # 匯入設定
from config import _script_dir  # 明確匯入私有路徑

# 屏蔽 Qt 多國語言 OpenType 排版警告 (使用萬用字元徹底關閉 font.db 警告)
os.environ["QT_LOGGING_RULES"] = "qt.text.font.db*=false;qt.gui.text*=false"  # 關閉警告

# 檔案日誌：打包成無控制台程式後，print 會消失，至少把錯誤留在 k20.log
try:  # 目錄可能不可寫
    logging.basicConfig(
        filename=os.path.join(_script_dir, "k20.log"),  # 日誌位置
        level=logging.INFO,  # 級別
        encoding="utf-8",  # 編碼
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",  # 格式
    )  # 設定完成
except Exception:  # 退回只輸出到 stderr
    logging.basicConfig(level=logging.INFO)  # 基本設定

def _log_uncaught(exc_type, exc, tb):  # 全域未捕獲異常
    logging.critical("Unhandled exception", exc_info=(exc_type, exc, tb))  # 寫入日誌

sys.excepthook = _log_uncaught  # 安裝鉤子

from main_window import K20PlayerUI主視窗  # 載入主頁

def main():  # 主程式入口
    app = QApplication(sys.argv)  # 建立應用

    # 🎯 雙重保險防無效字型：指定系統微軟正黑體
    font_family = "Microsoft JhengHei"  # 預設字型
    if font_family not in QFontDatabase.families():  # 檢查字型
        font_family = "Segoe UI"  # 備用字型

    global_font = QFont(font_family, 9)  # 建立字型
    global_font.setStyleHint(QFont.StyleHint.SansSerif)  # 無襯線體
    app.setFont(global_font)  # 套用字型

    app.setStyle("Fusion")  # 套用風格

    player = K20PlayerUI主視窗()  # 建立視窗
    player.show()  # 顯示視窗

    sys.exit(app.exec())  # 安全退出

if __name__ == "__main__":  # 執行入口
    main()  # 啟動程式

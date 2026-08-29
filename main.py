import os
import sys

# 屏蔽 Qt 多國語言 OpenType 排版警告 (使用萬用字元徹底關閉 font.db 警告)
os.environ["QT_LOGGING_RULES"] = "qt.text.font.db*=false;qt.gui.text*=false"

# 📌 關鍵修復：如果是 --onefile 打包，自動將工作目錄切換至 sys._MEIPASS 臨時資料夾
if hasattr(sys, '_MEIPASS'):
    os.chdir(sys._MEIPASS)

from config import *
from main_window import K20PlayerUI主視窗

def main():
    app = QApplication(sys.argv)
    
    # 🎯 雙重保險防無效字型：指定系統微軟正黑體
    font_family = "Microsoft JhengHei"
    if font_family not in QFontDatabase.families():
        font_family = "Segoe UI"

    global_font = QFont(font_family, 9)
    global_font.setStyleHint(QFont.StyleHint.SansSerif)
    app.setFont(global_font)

    app.setStyle("Fusion")

    player = K20PlayerUI主視窗()
    player.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()

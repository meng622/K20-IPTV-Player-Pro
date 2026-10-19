import sys  # 系統參數
import time  # 時間控制
import subprocess  # 進程管理
from watchdog.observers import Observer  # 檔案監控
from watchdog.events import FileSystemEventHandler  # 事件處理

class ReloadHandler(FileSystemEventHandler):  # 熱加載器
    def __init__(self, script):  # 初始化
        self.script = script  # 紀錄腳本
        self.process = None  # 初始進程
        self.start_process()  # 啟動腳本

    def start_process(self):  # 重啟進程
        if self.process:  # 若有舊進程
            self.process.kill()  # 強行關閉
            self.process.wait()  # 等待結束
        print("\n🔄 偵測到代碼變更 / 啟動中...")  # 印出提示
        # 啟動你嘅主程式
        self.process = subprocess.Popen([sys.executable, self.script])  # 執行腳本

    def on_modified(self, event):  # 檔案修改
        # 只針對 .py 檔案變更時重啟，忽略其他暫存檔
        if event.src_path.endswith(".py"):  # 是Python檔
            print(f"📝 檔案已儲存: {event.src_path}")  # 印出路徑
            self.start_process()  # 重建進程

if __name__ == "__main__":  # 執行入口
    target_script = "main.py"  # 目標檔案
    
    event_handler = ReloadHandler(target_script)  # 建監聽器
    observer = Observer()  # 建觀察者
    observer.schedule(event_handler, path=".", recursive=True)  # 綁定監控
    observer.start()  # 啟動監控

    print(f"🚀 [Dev Mode] 熱加載監控中... (修改任何 .py 並 Save 就會自動重啟)")  # 啟動提示
    try:  # 嘗試執行
        while True:  # 無限迴圈
            time.sleep(1)  # 暫停一秒
    except KeyboardInterrupt:  # 手動中斷
        observer.stop()  # 停止監控
        if event_handler.process:  # 若進程在
            event_handler.process.kill()  # 殺掉進程
    observer.join()  # 等待結束
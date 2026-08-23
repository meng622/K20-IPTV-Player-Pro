import sys
import time
import subprocess
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class ReloadHandler(FileSystemEventHandler):
    def __init__(self, script):
        self.script = script
        self.process = None
        self.start_process()

    def start_process(self):
        if self.process:
            self.process.kill()
            self.process.wait()
        print("\n🔄 偵測到代碼變更 / 啟動中...")
        # 啟動你嘅主程式
        self.process = subprocess.Popen([sys.executable, self.script])

    def on_modified(self, event):
        # 只針對 .py 檔案變更時重啟，忽略其他暫存檔
        if event.src_path.endswith(".py"):
            print(f"📝 檔案已儲存: {event.src_path}")
            self.start_process()

if __name__ == "__main__":
    target_script = "main.py"  # 你 Entry Point 嘅檔名
    
    event_handler = ReloadHandler(target_script)
    observer = Observer()
    observer.schedule(event_handler, path=".", recursive=True)
    observer.start()

    print(f"🚀 [Dev Mode] 熱加載監控中... (修改任何 .py 並 Save 就會自動重啟)")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        if event_handler.process:
            event_handler.process.kill()
    observer.join()
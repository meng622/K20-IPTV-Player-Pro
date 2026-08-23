import os
import re
import gzip
import zlib
import html
import sqlite3
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from PyQt6.QtCore import QThread, pyqtSignal

def clean_channel_name(name):
    """淨化頻道名稱，移除前綴數字、[HD]、m3u4u 特有後綴如 (src05) 等標籤"""
    if not name:
        return ""
    # 1. 移除開頭的數字標點，例如 "1. ", "02 - "
    name = re.sub(r'^\d+[\.\-\s]+', '', name)
    # 2. 移除中括號內容，例如 [HD], [News], [geo-blocked]
    name = re.sub(r'\[.*?\]', '', name)
    # 3. 移除小括號內容及其裡面的後綴（如 (src05), (src01), (L) 等）
    name = re.sub(r'\(.*?\)', '', name)
    # 4. 移除 *tt 等常見雜訊標籤
    name = re.sub(r'\*+\w*', '', name)
    # 5. 移除常見解析度字眼（如 4K, FHD, HD, SD, HEVC）以提高 EPG 匹配率
    name = re.sub(r'(?i)\b(4k|fhd|hd|sd|hevc|uhd)\b', '', name)
    return name.strip()

# ==================== EPG 資料庫管理 ====================
class EPGDatabase:
    def __init__(self, db_dir="epg_cache", db_name="epg_cache.db"):
        self.db_dir = db_dir
        self.db_path = os.path.join(self.db_dir, db_name)
        self.init_db()

    def init_db(self):
        if not os.path.exists(self.db_dir):
            os.makedirs(self.db_dir, exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS programmes (
                start TEXT,
                stop TEXT,
                channel TEXT,
                title TEXT,
                desc TEXT,
                category TEXT
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_programmes_start ON programmes (start)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_programmes_stop ON programmes (stop)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_programmes_channel ON programmes (channel)')
        conn.commit()
        conn.close()

    def get_current_program(self, tvg_id, channel_name):
        """查詢指定頻道當前時間正在播放的節目標題（支援名稱淨化與模糊匹配）"""
        if not os.path.exists(self.db_path):
            return ""
        
        now_str = datetime.now().strftime("%Y%m%d%H%M%S")
        cleaned_name = clean_channel_name(channel_name)
        like_pattern = f"%{cleaned_name}%" if cleaned_name else "%"

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 優先順序：tvg_id -> 原始名稱 -> 淨化後名稱 -> 模糊 LIKE 搜尋
        query = '''
            SELECT title FROM programmes 
            WHERE (channel = ? OR channel = ? OR channel = ? OR channel LIKE ?) 
              AND start <= ? AND stop >= ?
            LIMIT 1
        '''
        cursor.execute(query, (tvg_id, channel_name, cleaned_name, like_pattern, now_str, now_str))
        row = cursor.fetchone()
        conn.close()
        
        return row[0] if row else ""

    def get_channel_programmes(self, tvg_id, channel_name):
        """查詢指定頻道的完整節目清單 (提供給右側 EPG 面板使用)"""
        if not os.path.exists(self.db_path):
            return []

        cleaned_name = clean_channel_name(channel_name)
        like_pattern = f"%{cleaned_name}%" if cleaned_name else "%"

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        query = '''
            SELECT start, stop, title, desc, category FROM programmes 
            WHERE (channel = ? OR channel = ? OR channel = ? OR channel LIKE ?)
            ORDER BY start ASC
        '''
        cursor.execute(query, (tvg_id, channel_name, cleaned_name, like_pattern))
        rows = cursor.fetchall()
        conn.close()

        results = []
        for r in rows:
            results.append({
                "start": r[0],
                "stop": r[1],
                "title": r[2],
                "desc": r[3],
                "category": r[4]
            })
        return results

# ==================== EPG 下載與解析 Worker ====================
class EPGDownloaderWorker(QThread):
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, epg_url, db_dir="epg_cache", db_name="epg_cache.db", xml_name="cache_0.xml"):
        super().__init__()
        self.epg_url = epg_url
        self.db_dir = db_dir
        self.xml_path = os.path.join(db_dir, xml_name)
        self.db_path = os.path.join(db_dir, db_name)

    def _decompress_payload(self, raw_data, content_encoding=''):
        """
        穩健地解壓 EPG 回應內容：
        - 依 Content-Encoding 標頭決定優先嘗試 gzip 還是 deflate
        - deflate 同時嘗試標準 zlib 格式與「raw deflate」(無 zlib 標頭) 兩種變體，
          因為部份伺服器對 Content-Encoding: deflate 的實作並不標準
        - 最多嘗試兩輪，以因應極少數「雙重壓縮」的伺服器
        - 所有已知格式都失敗時回傳 None，交由呼叫端明確回報錯誤
          （而不是像舊版一樣，把仍未解壓的資料直接當成 XML 繼續往下跑）
        """
        if not raw_data:
            return raw_data

        data = raw_data
        content_encoding = (content_encoding or '').lower()

        for _ in range(2):
            if data.lstrip().startswith(b'<') or data.startswith(b'\xef\xbb\xbf'):
                return data  # 已經是可用內容，毋須再解壓

            order = ['deflate', 'gzip'] if 'deflate' in content_encoding else ['gzip', 'deflate']
            decompressed = None

            for method in order:
                try:
                    if method == 'gzip':
                        decompressed = gzip.decompress(data)
                    else:
                        try:
                            decompressed = zlib.decompress(data)
                        except zlib.error:
                            # 部分伺服器送出不含 zlib 標頭的 raw deflate 資料
                            decompressed = zlib.decompress(data, -zlib.MAX_WBITS)
                    break
                except Exception:
                    decompressed = None
                    continue

            if decompressed is None:
                # 回應內容前面可能夾雜其他資料，嘗試定位 gzip 魔術頭部後再解壓一次
                gz_start = data.find(b'\x1f\x8b')
                if gz_start > 0:
                    try:
                        decompressed = gzip.decompress(data[gz_start:])
                    except Exception:
                        decompressed = None

            if decompressed is None:
                return None  # 所有已知格式都嘗試失敗

            data = decompressed
            content_encoding = ''  # 第二輪不再假設編碼，交給內容特徵判斷

        return data

    def run(self):
        if not self.epg_url:
            self.finished_signal.emit(False, "EPG 網址為空")
            return

        try:
            if not os.path.exists(self.db_dir):
                os.makedirs(self.db_dir, exist_ok=True)

            # 建立偽裝 Chrome 的完整 Headers，並忽略 SSL 憑證檢查（部分 EPG 來源憑證有問題）
            import ssl
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive'
            }

            # 注意：urllib 會自動跟隨重定向，但「不會」自動解壓 gzip/deflate 內容，須自行處理
            req = urllib.request.Request(self.epg_url, headers=headers)
            with urllib.request.urlopen(req, timeout=30, context=ssl_context) as response:
                raw_data = response.read()
                content_encoding = response.headers.get('Content-Encoding', '')

            # 依 Content-Encoding 與內容特徵，穩健解壓 gzip / deflate
            raw_data = self._decompress_payload(raw_data, content_encoding)
            if raw_data is None:
                self.finished_signal.emit(False, "Gzip/Deflate 解壓失敗：無法辨識伺服器回傳的壓縮格式")
                return

            # 清除 UTF-8 BOM 頭 (\xef\xbb\xbf)
            if raw_data.startswith(b'\xef\xbb\xbf'):
                raw_data = raw_data[3:]

            # 尋找真正的 XML 標籤開頭 '<'
            xml_start = raw_data.find(b'<')
            if xml_start > 0:
                raw_data = raw_data[xml_start:]

            # 驗證最終內容：若依然不是 < 開頭，代表下載到了網頁或垃圾數據
            if not raw_data.lstrip().startswith(b'<'):
                preview_text = raw_data[:60].decode('utf-8', errors='ignore')
                preview_hex = raw_data[:12].hex()
                self.finished_signal.emit(
                    False,
                    f"解析失敗，回傳內容非 XML (hex: {preview_hex} / 預覽: {preview_text})"
                )
                return

            # 寫入本地 XML 快取檔 (此時保證是純文字 XML)
            with open(self.xml_path, 'wb') as out_file:
                out_file.write(raw_data)

            # 改用流式解析 (iterparse) 替代正則表達式，徹底解決 50MB 爆記憶體問題
            channel_map = {}
            programmes_batch = []

            # 第一階段：提取 channel mapping (只讀取 channel 標籤)
            try:
                context = ET.iterparse(self.xml_path, events=('end',))
                for event, elem in context:
                    if elem.tag == 'channel':
                        ch_id = elem.get('id', '')
                        disp_node = elem.find('display-name')
                        if ch_id and disp_node is not None and disp_node.text:
                            channel_map[ch_id] = disp_node.text.strip()
                        elem.clear() # 釋放記憶體
            except Exception as e:
                print(f"Channel parsing notice: {e}")

            # 第二階段：流式提取 programme (逐筆讀取，即時 clear 釋放記憶體)
            context = ET.iterparse(self.xml_path, events=('end',))
            context = iter(context)
            event, root = next(context) # 取得 root 引用

            for event, elem in context:
                if elem.tag == 'programme':
                    ch_id = elem.get('channel', '')
                    start_raw = elem.get('start', '').split()[0] if elem.get('start') else ''
                    stop_raw = elem.get('stop', '').split()[0] if elem.get('stop') else ''

                    if ch_id and start_raw and stop_raw:
                        title_m = elem.find('title')
                        desc_m = elem.find('desc')
                        cat_m = elem.find('category')

                        title = title_m.text.strip() if (title_m is not None and title_m.text) else ''
                        desc = desc_m.text.strip() if (desc_m is not None and desc_m.text) else ''
                        category = cat_m.text.strip() if (cat_m is not None and cat_m.text) else ''

                        channel_disp = channel_map.get(ch_id, ch_id)

                        # 同時寫入原始 ID 與頻道顯示名稱
                        programmes_batch.append((start_raw, stop_raw, ch_id, title, desc, category))
                        if channel_disp != ch_id:
                            programmes_batch.append((start_raw, stop_raw, channel_disp, title, desc, category))

                    # 關鍵：清空當前節點與 root，防止記憶體積累
                    elem.clear()
                    root.clear()

            # 批次寫入 SQLite 資料庫
            if programmes_batch:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute('DELETE FROM programmes') # 清空舊資料
                cursor.executemany('''
                    INSERT INTO programmes (start, stop, channel, title, desc, category)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', programmes_batch)
                conn.commit()
                conn.close()
                self.finished_signal.emit(True, f"成功解析並寫入 {len(programmes_batch)} 筆 EPG 節目資料！")
            else:
                self.finished_signal.emit(False, "未能在 EPG 檔案中解析到任何節目數據")

        except Exception as e:
            self.finished_signal.emit(False, f"EPG 處理失敗: {str(e)}")

# [代碼起點]
from config import *  # 匯入配置

def clean_channel_name(name):  # 淨化檔名
    if not name:  # 名稱空白
        return ""  # 回傳空字
    name = re.sub(r'^\d+[\.\-\s]+', '', name)  # 刪前數字
    name = re.sub(r'\[.*?\]', '', name)  # 刪中括號
    name = re.sub(r'\(.*?\)', '', name)  # 刪小括號
    name = re.sub(r'\*+\w*', '', name)  # 刪雜訊標
    name = re.sub(r'(?i)\b(4k|fhd|hd|sd|hevc|uhd)\b', '', name)  # 刪解析度
    return name.strip()  # 整理去空

    
# ====================== 頻道名歸一化（繁簡 / 符號） ======================
try:  # Windows 專用繁簡轉換
    import ctypes as _ctypes  # 匯入 C 介面
    from ctypes import wintypes as _wintypes  # 匯入型別
    _LCMAP_SIMPLIFIED_CHINESE = 0x02000000  # 簡體轉換旗標
    _LOCALE_SYSTEM_DEFAULT = 0x0800  # 系統地區
    _kernel32 = _ctypes.WinDLL('kernel32', use_last_error=True)  # 取得核心庫
    _kernel32.LCMapStringW.argtypes = [_wintypes.DWORD, _wintypes.DWORD, _wintypes.LPCWSTR, _ctypes.c_int, _wintypes.LPWSTR, _ctypes.c_int]  # 參數型別
    _kernel32.LCMapStringW.restype = _ctypes.c_int  # 回傳型別
except Exception:  # 非 Windows 或載入失敗
    _ctypes = None  # 標記不可用
    _kernel32 = None  # 標記不可用

def to_simplified(text):  # 繁轉簡
    """繁體轉簡體（用 Windows API，失敗時原樣回傳，不影響任何既有流程）"""
    source = str(text or '')  # 轉字串
    if not source or _kernel32 is None:  # 無需轉換
        return source  # 原樣回傳
    try:  # 嘗試轉換
        buffer = _ctypes.create_unicode_buffer(len(source) * 2 + 8)  # 建立緩衝
        result = _kernel32.LCMapStringW(_LOCALE_SYSTEM_DEFAULT, _LCMAP_SIMPLIFIED_CHINESE, source, -1, buffer, len(buffer))  # 呼叫轉換
        return buffer.value if result > 0 else source  # 回傳結果
    except Exception:  # 轉換失敗
        return source  # 原樣回傳

def normalize_channel_key(value):  # 歸一化鍵
    """頻道名歸一化：繁→簡、小寫、去畫質詞與所有符號，用於跨來源比對"""
    value = to_simplified(str(value or '')).lower()  # 轉簡體小寫
    value = re.sub(r'(8k|4k|fhd|uhd|hd|sd|hevc|60fps)', '', value)  # 去畫質詞
    value = re.sub(r'[^0-9a-z\u4e00-\u9fff]+', '', value)  # 只留中英數
    return value.strip()  # 去頭尾

def channel_match_keys(*values):  # 產生比對鍵
    """由頻道各欄位產生一組比對鍵（原名／清洗名／歸一化名／去尾綴名）"""
    keys = set()  # 鍵集合
    for value in values:  # 巡迴欄位
        text = str(value or '').strip()  # 轉字串
        if not text:  # 空值
            continue  # 跳過
        keys.add(text.lower())  # 原字小寫
        cleaned = clean_channel_name(text).lower()  # 清洗後
        if cleaned:  # 有值
            keys.add(cleaned)  # 加入清洗
        normalized = normalize_channel_key(text)  # 歸一化
        if normalized:  # 有值
            keys.add(normalized)  # 加入歸一化
            base = re.sub(r'(衛視|卫视)', '', normalized)  # 去「衛視/卫视」
            for candidate in {normalized, base}:  # 兩種基準
                trimmed = re.sub(r'(电视台|電視台|频道|頻道|台)$', '', candidate)  # 去尾綴
                if trimmed:  # 仍有值
                    keys.add(trimmed)  # 加入去尾綴
    keys.discard('')  # 移除空值
    return keys  # 回傳集合

def build_epg_lookup(epg_data):  # 建 EPG 查表
    """建立 EPG 查表：原鍵 + 繁簡/符號歸一化變體（精確鍵優先，變體不覆蓋原鍵）"""
    lookup = {}  # 查表
    if not isinstance(epg_data, dict):  # 格式檢查
        return lookup  # 回傳空表
    for key, programmes in epg_data.items():  # 第一輪：原鍵
        lookup.setdefault(str(key).lower(), programmes)  # 精確鍵優先
    for key, programmes in epg_data.items():  # 第二輪：變體
        for variant in channel_match_keys(key):  # 產生變體
            lookup.setdefault(variant, programmes)  # 只補缺、不覆蓋
    return lookup  # 回傳查表

# ====================== EPG 資料庫管理 =======================
class EPGDatabase:  # 資料庫類
    def __init__(self, db_dir="epg_cache", db_name="epg_cache.db"):  # 初始化
        self.db_dir = db_dir  # 快取目錄
        self.db_path = os.path.join(self.db_dir, db_name)  # 快取路徑
        self.init_db()  # 建資料庫

    def init_db(self):  # 建表方法
        if not os.path.exists(self.db_dir):  # 資料夾無
            os.makedirs(self.db_dir, exist_ok=True)  # 建立資料

        conn = sqlite3.connect(self.db_path)  # 連資料庫
        cursor = conn.cursor()  # 取游標
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS programmes (
                start TEXT,
                stop TEXT,
                channel TEXT,
                title TEXT,
                desc TEXT,
                category TEXT
            )
        ''')  # 建立節目
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_programmes_start ON programmes (start)')  # 建始索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_programmes_stop ON programmes (stop)')  # 建末索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_programmes_channel ON programmes (channel)')  # 建頻索引
        conn.commit()  # 提交變更
        conn.close()  # 關閉連線

    def get_current_program(self, tvg_id, channel_name):  # 查當前檔
        if not os.path.exists(self.db_path):  # 無資料庫
            return ""  # 回傳空白
        
        now_str = datetime.now().strftime("%Y%m%d%H%M%S")  # 當前時間
        cleaned_name = clean_channel_name(channel_name)  # 淨化名稱
        like_pattern = f"%{cleaned_name}%" if cleaned_name else "%"  # 模糊匹配

        conn = sqlite3.connect(self.db_path)  # 連資料庫
        cursor = conn.cursor()  # 取游標

        short_now = now_str[:12]  # 時間前段
        query = '''
            SELECT title FROM programmes
            WHERE (channel = ? OR channel = ? OR channel = ? OR channel LIKE ?)
              AND substr(start, 1, 12) <= ? AND substr(stop, 1, 12) >= ?
            LIMIT 1
        '''  # 查詢語法

        cursor.execute(query, (tvg_id, channel_name, cleaned_name, like_pattern, short_now, short_now))  # 執行查詢
        row = cursor.fetchone()  # 抓取單筆
        conn.close()  # 關閉連線
        
        return row[0] if row else ""  # 回傳檔名

    def get_channel_programmes(self, tvg_id, channel_name):  # 查頻道表
        if not os.path.exists(self.db_path):  # 無資料庫
            return []  # 回傳空清

        cleaned_name = clean_channel_name(channel_name)  # 淨化名稱
        like_pattern = f"%{cleaned_name}%" if cleaned_name else "%"  # 模糊匹配

        conn = sqlite3.connect(self.db_path)  # 連資料庫
        cursor = conn.cursor()  # 取游標

        query = '''
            SELECT start, stop, title, desc, category FROM programmes 
            WHERE (channel = ? OR channel = ? OR channel = ? OR channel LIKE ?)
            ORDER BY start ASC
        '''  # 查詢語法
        cursor.execute(query, (tvg_id, channel_name, cleaned_name, like_pattern))  # 執行查詢
        rows = cursor.fetchall()  # 抓取多筆
        conn.close()  # 關閉連線

        results = []  # 結果陣列
        for r in rows:  # 遍歷資料
            results.append({
                "start": r[0],
                "stop": r[1],
                "title": r[2],
                "desc": r[3],
                "category": r[4]
            })  # 組合字典
        return results  # 回傳清單

# ==================== EPG 下載與解析 Worker ====================
class EPGDownloaderWorker(QThread):  # 下載線程
    finished_signal = pyqtSignal(bool, str)  # 完成訊號

    def __init__(self, epg_url, db_dir="epg_cache", db_name="epg_cache.db", xml_name="cache_0.xml"):  # 初始化
        super().__init__()  # 呼叫父類
        self.epg_url = epg_url  # 下載網址
        self.db_dir = db_dir  # 快取目錄
        self.xml_path = os.path.join(db_dir, xml_name)  # 快取檔名
        self.db_path = os.path.join(db_dir, db_name)  # 資料庫路

    def _decompress_payload(self, raw_data, content_encoding=''):  # 解壓內容
        if not raw_data:  # 資料空白
            return raw_data  # 直接回傳

        data = raw_data  # 賦值數據
        content_encoding = (content_encoding or '').lower()  # 取小寫碼

        for _ in range(2):  # 重試兩次
            if data.lstrip().startswith(b'<') or data.startswith(b'\xef\xbb\xbf'):  # 明文XML
                return data  # 直接回傳

            order = ['deflate', 'gzip'] if 'deflate' in content_encoding else ['gzip', 'deflate']  # 順序判定
            decompressed = None  # 解壓結果

            for method in order:  # 嘗試解壓
                try:  # 捕捉例外
                    if method == 'gzip':  # Gzip模式
                        decompressed = gzip.decompress(data)  # Gzip解壓
                    else:  # Deflate
                        try:  # 嘗試標準
                            decompressed = zlib.decompress(data)  # zlib解壓
                        except zlib.error:  # 標準失敗
                            decompressed = zlib.decompress(data, -zlib.MAX_WBITS)  # Raw解壓
                    break  # 解壓成功
                except Exception:  # 解壓失敗
                    decompressed = None  # 清空變數
                    continue  # 換種試試

            if decompressed is None:  # 依然失敗
                gz_start = data.find(b'\x1f\x8b')  # 找魔術標
                if gz_start > 0:  # 找到頭標
                    try:  # 嘗試解壓
                        decompressed = gzip.decompress(data[gz_start:])  # 切割解壓
                    except Exception:  # 解壓失敗
                        decompressed = None  # 清空變數

            if decompressed is None:  # 全數失敗
                return None  # 回傳空值

            data = decompressed  # 更新數據
            content_encoding = ''  # 重置編碼

        return data  # 回傳數據

    def run(self):  # 執行線程
        if not self.epg_url:  # 網址空白
            self.finished_signal.emit(False, "EPG 網址為空")  # 發送失敗
            return  # 結束執行

        CACHE_EXPIRE_SECONDS = 86400  # 過期時間
        if os.path.exists(self.db_path):  # 快取存在
            db_mtime = os.path.getmtime(self.db_path)  # 取修改日
            import time  # 匯入時間
            if (time.time() - db_mtime) < CACHE_EXPIRE_SECONDS:  # 未滿一天
                print("⚡ [EPG Cache] 偵測到有效 EPG 本地快取 (未滿24hr)，直接直通 Bypass 解壓！")  # 印出訊息
                self.finished_signal.emit(True, "使用 24 小時內本地 EPG 有效快取")  # 發送成功
                return  # 結束執行

        try:  # 捕捉例外
            if not os.path.exists(self.db_dir):  # 快取無資
                os.makedirs(self.db_dir, exist_ok=True)  # 建立目錄

            import ssl  # 匯入SSL
            ssl_context = ssl.create_default_context()  # 建立 context
            ssl_context.check_hostname = False  # 不驗主機
            ssl_context.verify_mode = ssl.CERT_NONE  # 不驗憑證

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive'
            }  # 偽裝標頭

            req = urllib.request.Request(self.epg_url, headers=headers)  # 建請求物件
            with urllib.request.urlopen(req, timeout=30, context=ssl_context) as response:  # 請求網頁
                raw_data = response.read()  # 讀取數據
                content_encoding = response.headers.get('Content-Encoding', '')  # 取得編碼

            raw_data = self._decompress_payload(raw_data, content_encoding)  # 解壓數據
            if raw_data is None:  # 解壓失敗
                self.finished_signal.emit(False, "Gzip/Deflate 解壓失敗：無法辨識伺服器回傳的壓縮格式")  # 發送失敗
                return  # 結束執行

            if raw_data.startswith(b'\xef\xbb\xbf'):  # 特殊BOM頭
                raw_data = raw_data[3:]  # 去除BOM

            xml_start = raw_data.find(b'<')  # 尋找XML
            if xml_start > 0:  # 標頭靠後
                raw_data = raw_data[xml_start:]  # 裁切開頭

            if not raw_data.lstrip().startswith(b'<'):  # 非XML語法
                preview_text = raw_data[:60].decode('utf-8', errors='ignore')  # 文字預覽
                preview_hex = raw_data[:12].hex()  # 十六進制
                self.finished_signal.emit(
                    False,
                    f"解析失敗，回傳內容非 XML (hex: {preview_hex} / 預覽: {preview_text})"
                )  # 發送失敗
                return  # 結束執行

            with open(self.xml_path, 'wb') as out_file:  # 開快取檔
                out_file.write(raw_data)  # 寫入XML

            channel_map = {}  # 頻道字典
            programmes_batch = []  # 節目列表

            try:  # 捕捉例外
                context = ET.iterparse(self.xml_path, events=('end',))  # 流式解析
                for event, elem in context:  # 遍歷節點
                    if elem.tag == 'channel':  # 頻道節點
                        ch_id = elem.get('id', '')  # 取頻道ID
                        disp_node = elem.find('display-name')  # 取顯示名
                        if ch_id and disp_node is not None and disp_node.text:  # 屬性齊全
                            channel_map[ch_id] = disp_node.text.strip()  # 寫入對照
                        elem.clear() # 釋放記憶
            except Exception as e:  # 解析錯誤
                print(f"Channel parsing notice: {e}")  # 印出通知

            context = ET.iterparse(self.xml_path, events=('end',))  # 流式解析
            context = iter(context)  # 取疊代器
            event, root = next(context) # 取根節點

            for event, elem in context:  # 遍歷節目
                if elem.tag == 'programme':  # 節目節點
                    ch_id = elem.get('channel', '')  # 取頻道ID
                    start_raw = elem.get('start', '').split()[0] if elem.get('start') else ''  # 取開始時
                    stop_raw = elem.get('stop', '').split()[0] if elem.get('stop') else ''  # 取結束時

                    if ch_id and start_raw and stop_raw:  # 屬性齊全
                        title_m = elem.find('title')  # 取得標題
                        desc_m = elem.find('desc')  # 取得描述
                        cat_m = elem.find('category')  # 取得分類

                        title = title_m.text.strip() if (title_m is not None and title_m.text) else ''  # 清理標題
                        desc = desc_m.text.strip() if (desc_m is not None and desc_m.text) else ''  # 清理描述
                        category = cat_m.text.strip() if (cat_m is not None and cat_m.text) else ''  # 清理分類

                        channel_disp = channel_map.get(ch_id, ch_id)  # 取對照名

                        programmes_batch.append((start_raw, stop_raw, ch_id, title, desc, category))  # 寫入批次
                        if channel_disp != ch_id:  # 名稱不同
                            programmes_batch.append((start_raw, stop_raw, channel_disp, title, desc, category))  # 補寫顯示名

                    elem.clear()  # 釋放記憶
                    root.clear()  # 釋放根項

            if programmes_batch:  # 批次有值
                conn = sqlite3.connect(self.db_path)  # 連資料庫
                cursor = conn.cursor()  # 取游標
                cursor.execute('DELETE FROM programmes') # 刪舊節目
                cursor.executemany('''
                    INSERT INTO programmes (start, stop, channel, title, desc, category)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', programmes_batch)  # 寫入新表
                conn.commit()  # 提交變更
                conn.close()  # 關閉連線
                self.finished_signal.emit(True, f"成功解析並寫入 {len(programmes_batch)} 筆 EPG 節目資料！")  # 發送成功
            else:  # 無解析值
                self.finished_signal.emit(False, "未能在 EPG 檔案中解析到任何節目數據")  # 發送失敗

        except Exception as e:  # 捕捉例外
            self.finished_signal.emit(False, f"EPG 處理失敗: {str(e)}")  # 發送失敗
            
# ==================== 內存版 EPG Worker（純字典模式，快取速度極快） ====================
class MemoryEPGWorker(QThread):  # 記憶體線程
    finished_signal = pyqtSignal(dict)  # 完成訊號
    error_signal = pyqtSignal(str)  # 單一來源失敗訊號
    MAX_PAST_HOURS = 12  # 過去時數
    MAX_FUTURE_HOURS = 48  # 未來時數

    def __init__(self, epg_url):  # 初始化
        super().__init__()  # 呼叫父類
        # 支援「單一字串」或「逗號分隔多個 EPG」，統一拆成清單
        if isinstance(epg_url, (list, tuple, set)):  # 已是清單
            raw_urls = [str(u) for u in epg_url]  # 直接取用
        else:  # 字串型式
            raw_urls = str(epg_url or '').split(',')  # 以逗號切割
        self.epg_urls = [u.strip() for u in raw_urls if u and u.strip()]  # 過濾空值
        self.epg_url = self.epg_urls[0] if self.epg_urls else ''  # 保留舊屬性相容

    @staticmethod
    def _keys_for_channel(channel_id, display_name):  # 產生鍵值
        keys = set()  # 建立集合
        for value in (channel_id, display_name):  # 遍歷屬性
            value = str(value or '').strip()  # 字串清理
            if value:  # 內容不空
                keys.add(value.lower())  # 加小寫鍵
                cleaned = clean_channel_name(value).lower()  # 淨化小寫
                if cleaned:  # 淨化有值
                    keys.add(cleaned)  # 加淨化鍵
        return keys  # 回傳集合

    @staticmethod
    def _parse_xmltv_time(value):  # 解析時間
        try:  # 嘗試轉化
            return datetime.strptime((value or '').split()[0][:14].ljust(14, '0'), '%Y%m%d%H%M%S')  # 轉為物件
        except (TypeError, ValueError):  # 轉化失敗
            return None  # 回傳空值

    def run(self):  # 執行線程
        merged = {}  # 合併結果
        for url in self.epg_urls:  # 巡迴全部來源
            part = self._fetch_and_parse(url)  # 解析單一來源
            for key, programmes in part.items():  # 巡迴節目
                if key not in merged:  # 先到先得（避免重複膨脹）
                    merged[key] = programmes  # 寫入結果
        self.finished_signal.emit(merged)  # 發送合併數據

    def _fetch_and_parse(self, url):  # 下載解析單源
        """下載並解析單一 EPG 網址，回傳 {鍵: [節目]}"""
        epg_data = {}  # 資料字典
        temp_path = None  # 暫存路徑
        try:  # 捕捉例外
            import shutil  # 匯入工具
            import tempfile  # 匯入暫存
            import urllib.request  # 匯入網絡
            from datetime import timedelta  # 匯入時差

            cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'epg_cache')  # 建立目錄
            os.makedirs(cache_dir, exist_ok=True)  # 生成目錄
            with tempfile.NamedTemporaryFile(prefix='epg_', suffix='.xml', dir=cache_dir, delete=False) as temp_file:  # 開暫存檔
                temp_path = temp_file.name  # 取暫存名
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})  # 偽裝標頭
                with urllib.request.urlopen(req, timeout=20) as resp:  # 下載檔案
                    shutil.copyfileobj(resp, temp_file, length=1024 * 1024)  # 複製流向

            with open(temp_path, 'rb') as probe:  # 讀取測試
                is_gzip = probe.read(2) == b'\x1f\x8b'  # 是否Gzip
            open_xml = gzip.open if is_gzip else open  # 選擇開啟

            alias_candidates = {}  # 別名 -> 候選 ID 集合
            with open_xml(temp_path, 'rb') as stream:  # 開啟檔案
                root = None  # 根項初始化
                for event, elem in ET.iterparse(stream, events=('start', 'end')):  # 流式解析
                    if event == 'start' and root is None:  # 開始標籤
                        root = elem  # 設置根項
                    elif event == 'end' and elem.tag == 'channel':  # 頻道結尾
                        channel_id = elem.get('id', '').strip().lower()  # 取小寫ID
                        if channel_id:  # ID有值
                            for key in self._keys_for_channel(channel_id, elem.findtext('display-name', '')):  # 產生別名
                                alias_candidates.setdefault(key, set()).add(channel_id)  # 記錄候選ID
                        elem.clear()  # 釋放記憶
                        root.clear()  # 釋放根項

            now = datetime.now()  # 當前時間
            min_stop = now - timedelta(hours=self.MAX_PAST_HOURS)  # 最早時間
            max_start = now + timedelta(hours=self.MAX_FUTURE_HOURS)  # 最晚時間
            with open_xml(temp_path, 'rb') as stream:  # 開啟檔案
                root = None  # 根項初始化
                for event, elem in ET.iterparse(stream, events=('start', 'end')):  # 流式解析
                    if event == 'start' and root is None:  # 開始標籤
                        root = elem  # 設置根項
                    elif event == 'end' and elem.tag == 'programme':  # 節目結尾
                        channel_id = elem.get('channel', '').strip().lower()  # 取小寫ID
                        start = elem.get('start', '')  # 開始時間
                        stop = elem.get('stop', '')  # 結束時間
                        start_dt = self._parse_xmltv_time(start)  # 開始物件
                        stop_dt = self._parse_xmltv_time(stop)  # 結束物件
                        if channel_id and start_dt and stop_dt and stop_dt >= min_stop and start_dt <= max_start:  # 符合範圍
                            description = (elem.findtext('desc', '') or '').strip()  # 取節目敘述
                            icon = elem.find('icon')  # 取得圖示
                            epg_data.setdefault(channel_id, []).append({
                                'start': start,
                                'stop': stop,
                                'title': (elem.findtext('title', '') or '').strip(),
                                'subtitle': (elem.findtext('sub-title', '') or '').strip(),
                                'desc': description[:2000],
                                'category': (elem.findtext('category', '') or '').strip(),
                                'episode_num': (elem.findtext('episode-num', '') or '').strip(),
                                'icon': (icon.get('src', '') if icon is not None else '').strip(),
                            })  # 加節目資料
                        elem.clear()  # 釋放記憶
                        root.clear()  # 釋放根項

            for alias, ids in alias_candidates.items():  # 遍歷別名
                if alias in epg_data:  # 本身就是真實頻道 ID 的資料
                    continue  # 絕不覆蓋（避免同名不同 ID 的簡介被吃掉）
                best_id, best_score = None, None  # 最佳候選
                for candidate_id in ids:  # 巡迴候選 ID
                    programmes = epg_data.get(candidate_id)  # 取節目清單
                    if not programmes:  # 無節目
                        continue  # 跳過
                    has_desc = 1 if any((p.get('desc') or '') for p in programmes) else 0  # 有無簡介
                    score = (has_desc, len(programmes), 0 if candidate_id.isdigit() else 1)  # 評分：有簡介 > 節目多 > 非數字ID
                    if best_score is None or score > best_score:  # 更佳候選
                        best_id, best_score = candidate_id, score  # 更新最佳
                if best_id:  # 找到最佳
                    epg_data[alias] = epg_data[best_id]  # 指向最佳清單

        except Exception as e:  # 捕捉例外
            print(f"MemoryEPGWorker 解析失敗 ({url}): {e}")  # 印出失敗
            self.error_signal.emit(f"{url}: {e}")  # 通知 UI
        finally:  # 必定執行
            if temp_path and os.path.exists(temp_path):  # 暫存存在
                try:  # 嘗試刪除
                    os.remove(temp_path)  # 移除暫存
                except OSError:  # 刪除失敗
                    pass  # 忽略錯誤

        return epg_data  # 回傳數據
# [代碼終點]
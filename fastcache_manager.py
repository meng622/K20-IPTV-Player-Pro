from config import *  # 載入設定

from epg_manager import clean_channel_name  # 載入名淨化

# 日誌設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')  # 設定記錄器
logger = logging.getLogger(__name__)  # 建立記錄物件

class FastCache:  # 清單管理類
    """  # 文件開頭
    極速三級緩存 M3U+EPG 管理器  # 文件簡介
    自動處理下載、解析、緩存，並支援每日自動更新  # 文件說明
    """  # 文件結尾
    CACHE_VERSION = 3  # 快取版本號

    def __init__(self, m3u_url: str, epg_url: Optional[str] = None, cache_dir: str = "./cache"):  # 初始化方法
        """  # 方法註解
        :param m3u_url: M3U 播放列表網址  # 網址參數
        :param epg_url: EPG 網址 (可為 None)  # 節目表網址
        :param cache_dir: 緩存目錄  # 資料夾路徑
        """  # 註解結尾
        self.m3u_url = m3u_url  # 存播放網址
        self.epg_url = epg_url  # 存節目網址
        self.cache_dir = cache_dir  # 存資料夾路
        self._ensure_cache_dirs()  # 建快取資料

        # 計算雜湊值
        self.url_hash = hashlib.md5(m3u_url.encode()).hexdigest()[:8]  # 算網址哈希
        self.epg_hash = None  # 節目表哈希

        # 路徑設定
        self.raw_m3u_path = os.path.join(cache_dir, "raw", f"{self.url_hash}.m3u")  # 原始播檔路
        self.raw_epg_path = None  # 原始節目路
        self.parsed_m3u_path = os.path.join(cache_dir, "parsed", f"{self.url_hash}_channels.pkl")  # 解析播檔路
        self.parsed_epg_path = None  # 解析節目路

        # 設元數據路
        self.meta_path = os.path.join(cache_dir, "meta", f"{self.url_hash}.meta")  # 記錄檔路徑

        # 初始化資料
        self.channels: List[Dict] = []  # 頻道清單
        self.epg_data: Dict[str, List[Dict]] = {}  # 節目對照表
        self._set_epg_url(epg_url)  # 設定節目網

    def _set_epg_url(self, epg_url: Optional[str]):  # 設節目網址
        """設定 EPG 來源並同步更新衍生快取路徑。"""  # 功能說明
        self.epg_url = (epg_url or "").strip()  # 清除前後空
        self.epg_hash = hashlib.md5(self.epg_url.encode("utf-8")).hexdigest()[:8] if self.epg_url else None  # 算節目哈希
        self.raw_epg_path = (  # 設原始節目
            os.path.join(self.cache_dir, "raw", f"{self.epg_hash}.xml")  # 拼 XML 路徑
            if self.epg_hash else None  # 判斷有無哈希
        )  # 括號結尾
        self.parsed_epg_path = (  # 設解析節目
            os.path.join(self.cache_dir, "parsed", f"{self.epg_hash}_epg.pkl")  # 拼 PKL 路徑
            if self.epg_hash else None  # 判斷有無哈希
        )  # 括號結尾

    def _ensure_cache_dirs(self):  # 建立資料夾
        """建立緩存目錄結構"""  # 功能說明
        for sub in ["raw", "parsed", "meta"]:  # 跑子目錄名
            path = os.path.join(self.cache_dir, sub)  # 拼目錄路徑
            os.makedirs(path, exist_ok=True)  # 自動建資料

    def _get_last_update_date(self) -> Optional[date]:  # 讀最後更新
        """讀取上次更新日期"""  # 功能說明
        if os.path.exists(self.meta_path):  # 檢查檔案在
            try:  # 嘗試讀取
                with open(self.meta_path, 'r') as f:  # 開啟記錄檔
                    date_str = f.read().strip()  # 讀取日期字
                    return datetime.strptime(date_str, "%Y-%m-%d").date()  # 轉日期物件
            except:  # 出錯抓取
                return None  # 回傳無資料
        return None  # 沒檔傳無

    def _set_last_update_date(self, dt: date):  # 寫更新日期
        """寫入更新日期"""  # 功能說明
        with open(self.meta_path, 'w') as f:  # 開檔準備寫
            f.write(dt.strftime("%Y-%m-%d"))  # 寫入年月日

    def _is_cache_valid(self) -> bool:  # 檢查快取效
        """  # 註解開頭
        檢查緩存是否有效：  # 功能說明
        - 如果今天日期與記錄日期相同，則有效  # 規則一
        - 否則失效（需要更新）  # 規則二
        """  # 註解結尾
        last = self._get_last_update_date()  # 取得上次日
        if last is None:  # 沒舊日期
            return False  # 回傳已失效
        return last == date.today()  # 比對是否今天

    def _download_file(self, url: str, save_path: str) -> bool:  # 下載檔案函
        """下載檔案到指定路徑，回傳成功與否"""  # 功能說明
        try:  # 嘗試下載
            logger.info(f"下載中: {url}")  # 印下載訊息
            resp = requests.get(url, timeout=30)  # 發下載請求
            resp.raise_for_status()  # 檢查 HTTP 碼
            with open(save_path, 'wb') as f:  # 開新檔準備
                f.write(resp.content)  # 寫入位元組
            logger.info(f"下載完成: {save_path}")  # 印完成訊息
            return True  # 回傳成功
        except Exception as e:  # 抓下載錯誤
            logger.error(f"下載失敗 {url}: {e}")  # 印失敗訊息
            return False  # 回傳失敗
    
    # 變更解析流程
    def _parse_m3u(self, file_path: str):  # 解析 M3U
        """  # 註解開頭
        解析 M3U 檔案，回傳 (channels, epg_url)  # 回傳說明
        epg_url 係從 #EXTM3U 提取嘅 x-tvg-url 或 url-tvg  # 提取說明
        """  # 註解結尾
        channels = []  # 建頻道列表
        epg_url = ""  # 預設節目網
        try:  # 嘗試讀檔
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:  # 開啟 M3U
                lines = f.readlines()  # 讀全部文字
        except Exception as e:  # 讀檔失敗
            logger.error(f"讀取 M3U 失敗: {e}")  # 印讀檔錯誤
            return channels, ""  # 回傳空資料

        i = 0  # 設行數索引
        while i < len(lines):  # 逐行看內容
            line = lines[i].strip()  # 拿行並掐頭
            if line.startswith('#EXTM3U'):  # 是標頭行
                # 抓節目網址
                import re  # 匯入正則列
                match = re.search(r'x-tvg-url="([^"]+)"', line)  # 找 x-tvg
                if not match:  # 沒找到前項
                    match = re.search(r'url-tvg="([^"]+)"', line)  # 找 url-tvg
                if match:  # 若有匹配到
                    epg_url = match.group(1)  # 取出網址值
                    # 修正特規網
                    epg_url = re.sub(r'm3u4u\.com/epg/', 'm3u4u.com/xml/', epg_url)  # 修正 m3u4u
                    if epg_url.endswith('.gz'):  # 是壓縮檔
                        epg_url = epg_url[:-3]  # 去除 gz 尾
            elif line.startswith('#EXTINF:'):  # 是頻道資訊
                # 提取頻道細節
                info = line[8:].strip()  # 截取資訊段
                import re  # 匯入正則列
                tvg_id = re.search(r'tvg-id="([^"]*)"', info)  # 找頻道 ID
                tvg_logo = re.search(r'tvg-logo="([^"]*)"', info)  # 找台標圖
                group = re.search(r'group-title="([^"]*)"', info)  # 找群組類別
                name = info.split(',')[-1].strip() if ',' in info else info  # 取頻道名稱
                i += 1  # 移至下一行
                if i < len(lines):  # 未超總行數
                    url = lines[i].strip()  # 取得播放網
                    if url and not url.startswith('#'):  # 確保是網址
                        channels.append({  # 加頻道資料
                            'name': name,  # 頻道名稱
                            'tvg_id': tvg_id.group(1) if tvg_id else '',  # 頻道 ID
                            'logo': tvg_logo.group(1) if tvg_logo else '',  # 台標網址
                            'group': group.group(1) if group else '',  # 群組名稱
                            'url': url  # 串流網址
                        })  # 字典結尾
            i += 1  # 行數加一
        logger.info(f"解析 M3U 完成，共 {len(channels)} 個頻道，提取 EPG URL: {epg_url}")  # 印解析結果
        return channels, epg_url  # 回傳頻道節目

    def _parse_epg(self, file_path: str) -> Dict[str, List[Dict]]:  # 解析 XML
        """  # 註解開頭
        解析 EPG (XMLTV) 檔案，回傳 dict: channel_id -> list of programmes  # 功能說明
        使用與 MemoryEPGWorker 完全相同嘅邏輯，確保解析結果一致  # 邏輯說明
        """  # 註解結尾
        epg_data = {}  # 建立節目對
        try:  # 嘗試解析
            # 判斷壓縮檔
            if file_path.endswith('.gz'):  # 是 gz 格式
                import gzip  # 匯入解壓模
                with gzip.open(file_path, 'rb') as f:  # 開解壓檔案
                    raw_data = f.read()  # 讀二進位碼
            else:  # 一般 XML
                with open(file_path, 'rb') as f:  # 開一般檔案
                    raw_data = f.read()  # 讀二進位碼

            # 解析 XML 結構
            import xml.etree.ElementTree as ET  # 匯入 XML 模
            root = ET.fromstring(raw_data)  # 轉 XML 樹狀

            # 建立名稱映射
            channel_map = {}  # 建立頻道表
            for ch in root.findall('channel'):  # 找 channel 標
                ch_id = ch.get('id', '')  # 拿頻道 ID
                display_name = ch.findtext('display-name', '')  # 拿顯示名稱
                if ch_id:  # 若 ID 存在
                    channel_map[ch_id.lower().strip()] = display_name  # 建立對應表

            # 遍歷節目資料
            for prog in root.findall('programme'):  # 找 programme
                ch_id = prog.get('channel', '').lower().strip()  # 拿頻道 ID
                start = prog.get('start', '')  # 拿開始時間
                stop = prog.get('stop', '')  # 拿結束時間
                title = prog.findtext('title', '')  # 拿節目名稱
                description = (prog.findtext('desc', '') or '').strip()  # 拿節目簡介
                icon = prog.find('icon')  # 拿節目圖示
                prog_dict = {  # 建節目字典
                    'start': start,  # 開始時間
                    'stop': stop,  # 結束時間
                    'title': title,  # 節目標題
                    'subtitle': (prog.findtext('sub-title', '') or '').strip(),  # 子標題
                    'desc': description[:2000],  # 限長度簡介
                    'category': (prog.findtext('category', '') or '').strip(),  # 節目類別
                    'episode_num': (prog.findtext('episode-num', '') or '').strip(),  # 集數編號
                    'icon': (icon.get('src', '') if icon is not None else '').strip(),  # 圖示網址
                }  # 字典結尾

                # 建立多重索引
                keys_to_index = set()  # 建索引集合
                if ch_id:  # 若 ID 存在
                    keys_to_index.add(ch_id)  # 加原 ID
                    keys_to_index.add(clean_channel_name(ch_id))  # 加乾淨 ID
                if ch_id in channel_map and channel_map[ch_id]:  # 在映射表內
                    disp_name = channel_map[ch_id]  # 拿顯示名稱
                    keys_to_index.add(disp_name)  # 加原顯示名
                    keys_to_index.add(clean_channel_name(disp_name))  # 加淨顯示名

                for ch_key in keys_to_index:  # 跑所有索引
                    if ch_key:  # 鍵不為空白
                        if ch_key not in epg_data:  # 不在節目表
                            epg_data[ch_key] = []  # 初始空清單
                        epg_data[ch_key].append(prog_dict)  # 加節目資料

        except Exception as e:  # 抓解析錯誤
            logger.error(f"解析 EPG XML 失敗: {e}")  # 印錯誤訊息
            import traceback  # 匯入追蹤模
            traceback.print_exc()  # 印完整報錯
            return {}  # 回傳空字典

        logger.info(f"解析 EPG 完成，共 {len(epg_data)} 個頻道有節目")  # 印完成數據
        return epg_data  # 回傳節目表
    
    # 快取儲存與載入
    # 存解析快取
    def _save_parsed_cache(self):  # 存解析檔案
        """原子化儲存單一快取快照；程式中斷不會留下半個 pickle 檔。"""  # 功能說明
        data = {  # 打包快取檔
            'version': self.CACHE_VERSION,  # 快取版本
            'saved_at': datetime.now().isoformat(timespec='seconds'),  # 儲存時間
            'm3u_url': self.m3u_url,  # 播放網址
            'channels': self.channels,  # 頻道列表
            'epg_data': self.epg_data,  # 節目對照
            'epg_url': self.epg_url,  # 節目網址
        }  # 打包結尾
        tmp_path = f"{self.parsed_m3u_path}.tmp"  # 暫存檔路徑
        try:  # 嘗試寫檔
            with open(tmp_path, 'wb') as f:  # 開暫存檔寫
                pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)  # 序列化寫入
                f.flush()  # 沖刷硬碟盤
                os.fsync(f.fileno())  # 強制同步檔
            os.replace(tmp_path, self.parsed_m3u_path)  # 蓋掉舊快取
            logger.info("已儲存快取：%s 個頻道、%s 個 EPG 索引", len(self.channels), len(self.epg_data))  # 印儲存資訊
        finally:  # 必定執行
            if os.path.exists(tmp_path):  # 若暫存還在
                os.remove(tmp_path)  # 刪除暫存檔

    def _load_from_parsed_cache(self) -> bool:  # 讀快取檔案
        if not os.path.exists(self.parsed_m3u_path):  # 沒快取檔案
            return False  # 回傳失敗
        try:  # 嘗試讀取
            with open(self.parsed_m3u_path, 'rb') as f:  # 開快取檔案
                data = pickle.load(f)  # 反序列化讀
            if (  # 條件檢查
                not isinstance(data, dict)  # 格式非字典
                or data.get('version') != self.CACHE_VERSION  # 版本不匹配
                or data.get('m3u_url', self.m3u_url) != self.m3u_url  # 網址不匹配
            ):  # 括號結尾
                return False  # 回傳失敗
            channels = data.get('channels')  # 取出頻道
            epg_data = data.get('epg_data')  # 取出節目
            if not isinstance(channels, list) or not isinstance(epg_data, dict):  # 型態不正確
                return False  # 回傳失敗
            if not channels:  # 空清單視為無效快取，重新下載
                logger.warning("快取頻道為空，忽略並重新下載")
                return False  # 回傳失敗
            if self.epg_url and data.get('epg_url', '') != self.epg_url:  # EPG 源被改過
                logger.warning("快取 EPG 網址已變更，重新建立")
                return False  # 回傳失敗
            self.channels = channels  # 賦值頻道
            self.epg_data = epg_data  # 賦值節目
            self._set_epg_url(data.get('epg_url', self.epg_url))  # 賦值網址
            logger.info("已載入快取：%s 個頻道、%s 個 EPG 索引", len(channels), len(epg_data))  # 印載入成功
            return True  # 回傳成功
        except (OSError, EOFError, pickle.PickleError, AttributeError, ImportError, ValueError) as exc:  # 抓讀檔例外
            logger.warning("快取無法讀取，將重新建立：%s", exc)  # 印警告訊息
            return False  # 回傳失敗

    def _download_and_parse(self):  # 下載兼解析
        """下載原始檔案、解析、儲存緩存"""  # 功能說明
        logger.info("開始下載及解析...")  # 印流程開始
        start_time = time.time()  # 記開始時間

        # 下載 M3U
        if not self._download_file(self.m3u_url, self.raw_m3u_path):  # 下載失敗
            raise RuntimeError("M3U 下載失敗")  # 拋錯例外
            
        # 解析 M3U
        self.channels, extracted_epg = self._parse_m3u(self.raw_m3u_path)  # 解析播檔
        if extracted_epg:  # 提取到網址
            self._set_epg_url(extracted_epg)  # 更新節目網

        # 下載 EPG
        if self.epg_url and isinstance(self.epg_url, str) and self.epg_url.strip():  # 有節目網址
            if not self._download_file(self.epg_url, self.raw_epg_path):  # 下載失敗
                logger.warning("EPG 下載失敗，將忽略 EPG")  # 印下載失敗
                self.epg_data = {}  # 清空節目檔
            else:  # 下載成功
                self.epg_data = self._parse_epg(self.raw_epg_path)  # 解析節目檔
                print(f"🔍 EPG 解析完成，共 {len(self.epg_data)} 個頻道有節目")  # 印頻道數量
                print(f"🔍 第一個頻道 ID: {list(self.epg_data.keys())[0] if self.epg_data else '無數據'}")  # 印首條數據
        else:  # 無效網址
            logger.warning("EPG URL 無效，跳過 EPG 下載")  # 印忽略下載
            self.epg_data = {}  # 清空節目檔

        # 儲存與更新
        self._save_parsed_cache()  # 寫入解析快
        # 更新日期
        self._set_last_update_date(date.today())  # 記今日日期
        logger.info(f"更新完成，耗時 {time.time() - start_time:.2f} 秒")  # 印花費時間

    def load(self, force_refresh: bool = False):  # 載入主函式
        """  # 註解開頭
        主載入方法：  # 功能說明
        - 若 force_refresh=True 則強制重新下載解析  # 強制規則
        - 否則檢查緩存有效性，有效則載入 parsed，無效則下載  # 快取規則
        """  # 註解結尾
        if force_refresh:  # 是強制刷新
            logger.info("強制刷新模式")  # 印刷新日誌
            self._download_and_parse()  # 抓檔兼解析
            return  # 結束執行

        # 檢查快取
        if self._is_cache_valid():  # 快取仍有效
            # 嘗試載快取
            if self._load_from_parsed_cache():  # 讀載成功
                logger.info("使用有效緩存數據")  # 印使用快取
                return  # 結束執行
            else:  # 快取壞掉
                logger.warning("緩存文件損壞，重新下載")  # 印檔案損壞
        else:  # 快取過期
            logger.info("緩存已過期（非今日），重新下載")  # 印過期日誌

        # 重新下載
        self._download_and_parse()  # 強制重新抓

    def refresh(self):  # 手動更新
        """手動強制更新（同 force_refresh=True）"""  # 功能說明
        self.load(force_refresh=True)  # 強制載資料

    def get_channels(self) -> List[Dict]:  # 拿頻道表
        """取得頻道列表"""  # 功能說明
        return self.channels  # 回傳頻道

    def get_epg(self, channel_id: str = None) -> Dict[str, List[Dict]]:  # 拿節目表
        """取得 EPG 數據，若提供 channel_id 則只回傳該頻道"""  # 功能說明
        if channel_id:  # 指定頻道 ID
            return {channel_id: self.epg_data.get(channel_id, [])}  # 回傳單頻道
        return self.epg_data  # 回傳全節目

    def auto_update_check(self):  # 自動檢查
        """  # 註解開頭
        自動更新檢查：若今日尚未更新，則自動觸發更新  # 功能說明
        適合放在定時器或每次啟動時呼叫  # 使用場景
        """  # 註解結尾
        if not self._is_cache_valid():  # 檢查已失效
            logger.info("自動更新觸發：緩存過期")  # 印觸發日誌
            self.load(force_refresh=False)  # 嘗試非強制
        else:  # 依然有效
            logger.info("自動更新檢查：緩存有效，無需更新")  # 印無需更新


# 測試範例區
if __name__ == "__main__":  # 主程式進入
    # 測試環境設定
    # 測試用網址
    M3U_URL = "http://example.com/playlist.m3u"  # 測試 M3U
    EPG_URL = "http://example.com/epg.xml.gz"  # 測試 EPG

    # 建物件測試
    manager = FastCache(M3U_URL, EPG_URL, cache_dir="./test_cache")  # 實體化類別

    # 執行首次載
    manager.load()  # 啟動載入
    print(f"載入頻道數: {len(manager.get_channels())}")  # 印頻道數量
    print(f"EPG 頻道數: {len(manager.get_epg())}")  # 印節目頻道

    # 測試模式備註
    # 手動更新示範
    # manager.refresh()  # 註解範例列

    # 自動檢查示範
    manager.auto_update_check()  # 測試自更新
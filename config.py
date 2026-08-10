# config.py
"""
教師研習檢核與統計管理系統 (TTVS) V2 - 全域系統配置檔
包含：
1. 四大層級 (Web UI, Business Service, Data Access, Storage) 運作參數
2. 各研習項目之校內 NAS 人工審核指定上傳資料夾路徑對照表
3. 承辦人員 / 系統管理員身份驗證 (Authentication) 參數配置
"""
import os
from datetime import timedelta

# 取得專案根目錄之絕對路徑
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    # ==========================================
    # 1. 系統安全性與 Session 身份驗證配置
    # ==========================================
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'ttvs-secret-key-v2-2026-safe-guard-auth'
    SYSTEM_NAME = "教師研習檢核與統計管理系統 (V2 AI 雙軌與權限版)"
    
    # 承辦人登入 Session 設定 (安全防禦：30 分鐘無操作自動登出)
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)
    
    # 預設系統管理員與各處室承辦人初始帳號配置 (啟動時自動寫入 User 表)
    DEFAULT_ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME') or 'admin'
    DEFAULT_ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD') or 'admin123'
    DEFAULT_ADMIN_EMAIL = 'admin@haps.tp.edu.tw'

    # ==========================================
    # 2. 資料庫與全文檢索配置 (Data Access Layer)
    # ==========================================
    # 主 SQLite 資料庫路徑
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(BASE_DIR, 'instance', 'database.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # SQLite 全文檢索 (FTS5) 虛擬資料表名稱
    FTS5_TABLE_NAME = "training_fts"
    
    # FAISS 向量索引檔儲存路徑
    FAISS_INDEX_PATH = os.path.join(BASE_DIR, 'instance', 'faiss_index.bin')
    
    # 政策指標關鍵字動態規則庫 (JSON 持久化)
    DYNAMIC_TAG_RULES_PATH = os.path.join(BASE_DIR, 'instance', 'dynamic_tag_rules.json')

    # ==========================================
    # 3. 實體儲存層資料夾目錄與各處室指定 NAS 路徑對照 (Storage Layer)
    # ==========================================
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')     # 上傳暫存總目錄
    EXPORT_FOLDER = os.path.join(BASE_DIR, 'exports')     # 雙欄 CSV 與全校 Excel 明細
    REPORT_FOLDER = os.path.join(BASE_DIR, 'reports')     # Word 簽呈公文與策進報告
    BACKUP_FOLDER = os.path.join(BASE_DIR, 'backups')     # 資料庫自動備份檔
    
    # 💡 幸安國小各研習項目指定人工審核證明上傳至校內 NAS 之相對路徑對照表
    # 系統將於啟動時自動於 uploads/ 下補齊這些子資料夾
    NAS_SPECIFIC_PATHS = {
        'traffic': r'nas2\16_共用分享\99_其他分享\生教組\生教組線上法定研習\114學年度',
        'aids': r'Nas2\16_共用分享\99_其他分享\衛生組\衛生組線上法定研習\114學年度\愛滋防治',
        'environment': r'Nas2\16_共用分享\99_其他分享\衛生組\衛生組線上法定研習\114學年度\氣候變遷',
        'gender': r'nas2/16共用分享/04輔導室分享/輔導室線上法定研習/性別平等研習/115年度性別平等研習',
        'suicide_prevention': r'16共用分享/04輔導室分享/輔導室線上法定研習/自殺防治研習/115年度自殺防治知能研習',
        'special_education': r'nas2/16共用分享/04輔導室分享/輔導室線上法定研習/特教研習',
        'family_education': r'nas2/16_共用分享/04_輔導室分享/輔導室線上法定研習/家庭教育研習',
        'counseling': r'nas2/16共用分享/04輔導室分享/輔導室線上法定研習/輔導知能研習/115年度',
        'info_security': r'nas2/16共用分享/01教務處分享/資安研習證明',
    }
    
    # 允許上傳之證書與名冊檔案格式驗證
    ALLOWED_EXTENSIONS = {'csv', 'xlsx', 'xls', 'docx', 'pdf', 'png', 'jpg', 'jpeg'}
    MAX_CONTENT_LENGTH = 32 * 1024 * 1024  # 單次上傳最大限制 32 MB

    # ==========================================
    # 4. Pipeline B：AI 人工輔助審核與模型配置 (Business Service Layer)
    # ==========================================
    # PP-OCRv6 設定
    OCR_USE_ANGLE_CLS = True   # 開啟文字角度自動旋轉校正
    OCR_LANG = 'ch'            # 語系設定 (繁體/簡體中文與英文)
    
    # 向量 Embedding 模型設定 (採用 CPU 友善之輕量化模型，記憶體 < 300MB)
    EMBEDDING_MODEL_NAME = "BAAI/bge-small-zh-v1.5"
    EMBEDDING_VECTOR_DIM = 512
    
    # 本地 LLM 連線設定 (Ollama)
    OLLAMA_API_URL = os.environ.get('OLLAMA_API_URL') or "http://127.0.0.1:11434/api/generate"
    OLLAMA_MODEL_NAME = "qwen2.5:1.5b-instruct"  # CPU 推論極速專用 1.5B 模型
    
    # Human Review 人工覆核信心值門檻
    CONFIDENCE_HIGH_THRESHOLD = 0.95  # 🟢 ≥ 95%: 系統自動採認通過 (綠燈免審)
    CONFIDENCE_MID_THRESHOLD = 0.70   # 🟡 70% ~ 94%: 醒目提示一鍵確認 (黃燈覆核)
                                      # 🔴 < 70%: 高風險，引導手動補登 (紅燈警示)

    # ==========================================
    # 5. 教育部「精進數位方案」預設標籤
    # ==========================================
    PRESET_TAGS = ['A1', 'A2', 'A3', 'B1', 'B2', 'B3', 'B4', 'B5-1', 'B5-2', 'C', 'D', 'E']
# config.py
import os

class Config:
    """系統全域設定類別"""
    
    # 獲取目前檔案所在的專案根目錄絕對路徑
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    
    # Flask 安全金鑰（用於 Session 與 CSRF 防護，生產環境建議改為亂數密碼）
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'teacher-training-verification-system-secret-key'
    
    # SQLite 資料庫檔案路徑設定
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(BASE_DIR, 'database.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # 檔案目錄規劃（對應專案目錄結構）
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
    EXPORT_FOLDER = os.path.join(BASE_DIR, 'exports')
    REPORT_FOLDER = os.path.join(BASE_DIR, 'reports')
    BACKUP_FOLDER = os.path.join(BASE_DIR, 'backups')
    
    # 允許上傳的副檔名限制（依規劃書 3.2 節需求：Excel 與 Word）
    ALLOWED_EXTENSIONS = {'csv', 'xlsx', 'xls', 'docx'}
    
    # 限制上傳檔案的最大容量（例如：16MB）
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024

    @staticmethod
    def init_app(app):
        """初始化應用程式時，自動建立所需的行政暫存目錄"""
        dirs = [
            Config.UPLOAD_FOLDER, 
            Config.EXPORT_FOLDER, 
            Config.REPORT_FOLDER, 
            Config.BACKUP_FOLDER
        ]
        for d in dirs:
            if not os.path.exists(d):
                os.makedirs(d)
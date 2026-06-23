# main.py
from flask import Flask, render_template
from config import Config
from models import db, Teacher

# 1. 引入四大主幹功能之模組化路由藍圖 (Blueprints)
from routes.teacher_routes import teacher_bp   # 教師名冊管理功能
from routes.import_routes import import_bp     # 研習/名冊大數據檔案匯入功能
from routes.training_routes import training_bp # 研習紀錄多重條件查詢與時數檢核功能
from routes.report_routes import report_bp     # 各指標通過率統計與公文報表輸出功能

def create_app():
    """
    建立並初始化 Flask 應用程式之工廠函數
    """
    app = Flask(__name__)
    
    # 2. 載入全域行政設定 (資料庫路徑、上傳上限與目錄結構)
    app.config.from_object(Config)
    
    # 3. 自動執行目錄防呆初始化 (若 uploads/、exports/、reports/ 不存在則自動建立)
    Config.init_app(app)
    
    # 4. 初始化 SQLAlchemy 資料庫連線
    db.init_app(app)
    
    # 5. 一鍵註冊四大主幹路由藍圖，實現功能完美解耦與整合
    app.register_blueprint(teacher_bp)
    app.register_blueprint(import_bp)
    app.register_blueprint(training_bp)
    app.register_blueprint(report_bp)
    
    # 6. 系統核心首頁儀表板路由
    @app.route('/')
    def dashboard():
        """
        七、系統首頁儀表板
        展現全校行政核心數據，如教師總數。
        可進一步擴充結合 ReportService 於此直接渲染各指標完成率圖表。
        """
        try:
            total_teachers = Teacher.query.count()
        except Exception:
            total_teachers = 0
            
        return render_template('dashboard.html', total_teachers=total_teachers)
        
    return app

# 系統啟動進入點
if __name__ == '__main__':
    app = create_app()
    
    # 首次啟動系統時，自動於專案根目錄下建立 SQLite database.db 檔案與 5 張實體資料表
    with app.app_context():
        db.create_all()
        
    # 啟動 Flask 本地行政主機，預設監聽連接埠 5000
    app.run(debug=True, port=5000)
 # main.py
import os
from flask import Flask, redirect, url_for, render_template
from models import db, Teacher, Training, TrainingRecord
from config import Config

# 引入四大行政業務藍圖路由 (Routes)
from routes.teacher_routes import teacher_bp
from routes.import_routes import import_bp
from routes.training_routes import training_bp
from routes.report_routes import report_bp
from routes.tag_routes import tag_bp

# 引入智慧標籤核心服務，用於系統初始化時加載規則庫
from services.tag_service import TagService


def create_app():
    """
    建立並配置 Flask 應用程式實體 (Application Factory 模式)
    """
    app = Flask(__name__)
    app.config.from_object(Config)

    # 初始化 SQLAlchemy 資料庫連動
    db.init_app(app)

    # 智慧型功能：啟動時自動初始化動態標籤規則庫 (持久化儲存於 instance 資料夾)
    TagService.init_rules(app.instance_path)

    # 註冊各行政業務模組藍圖 (Blueprints)
    app.register_blueprint(teacher_bp)
    app.register_blueprint(import_bp)
    app.register_blueprint(training_bp)
    app.register_blueprint(report_bp)
    app.register_blueprint(tag_bp)  # 註冊全新擴充的關鍵字自訂管理藍圖

    # 建立全站通用的首頁路由
    @app.route("/")
    def dashboard():
        """
        系統首頁儀表板 (七、系統首頁儀表板)
        動態統計全校編制教師總數，供前端 Jinja2 樣板即時計算推動達成率。
        """
        try:
            # 撈取全校目前已登錄的教師總人數
            total_teachers = Teacher.query.count()
        except Exception:
            total_teachers = 0

        return render_template("dashboard.html", total_teachers=total_teachers)

    # 建立全域上下文處理器，確保每個頁面在渲染導覽列時 request 變數均可用
    @app.context_processor
    def inject_auth_info():
        return dict(system_name="TTVS 教師研習檢核系統")

    # 配置全域應用程式啟動前置防呆檢查
    with app.app_context():
        # 1. 如果 SQLite 資料庫檔案不存在，自動執行 DDL 建立所有行政資料表
        db.create_all()

        # 2. 自動補齊系統運作所需的四大行政暫存與輸出資料夾
        for folder in [
            app.config["UPLOAD_FOLDER"],
            app.config["EXPORT_FOLDER"],
            app.config["REPORT_FOLDER"],
            app.config["BACKUP_FOLDER"],
        ]:
            if not os.path.exists(folder):
                os.makedirs(folder, exist_ok=True)

    return app


# 專案程式執行進入點
if __name__ == "__main__":
    app = create_app()

    # 以行政測試主機模式啟動 (自動偵測變更並重啟)
    # 預設埠號為 5000，本地存取網址為 http://127.0.0.1:5000/
    app.run(host="127.0.0.1", port=5000, debug=True)
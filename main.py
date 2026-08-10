# main.py
"""
教師研習檢核與統計管理系統 (TTVS) V2 - 系統核心啟動與初始化引擎
整合：
1. 首頁儀表板開放所有人免登入檢視指標達成率
2. 傳遞 tag_display_names (Pattern 第二個元素名稱) 至前端樣板
3. 動態檢核基準日：優先以批次匯入檔案建立日期為準，若無則以最新研習日期為準
4. 管理員 (Admin) 安全清空資料庫與系統重置 API
5. 各處室 (教務/輔導/學務/總務) 動態折疊大區塊統計
6. Waitress WSGI 生產環境多執行緒伺服器與區網 IP 自動偵測
"""
import os
import sys
import shutil
import socket
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, flash, request
from flask_login import LoginManager, current_user, login_required
from flask_migrate import Migrate
from waitress import serve
from werkzeug.security import generate_password_hash, check_password_hash

# 引入核心模型與設定檔
from models import db, Teacher, TrainingRecord, Training, User, SystemAuditLog
from config import Config

# 引入各大業務模組藍圖
from routes.auth_routes import auth_bp
from routes.teacher_routes import teacher_bp
from routes.import_routes import import_bp
from routes.training_routes import training_bp
from routes.report_routes import report_bp
from routes.tag_routes import tag_bp

# 引入核心服務層：政策知識庫標籤服務
from services.tag_service import TagService


def create_app():
    """
    Flask 應用程式工廠 (Application Factory)
    """
    app = Flask(__name__)
    app.config.from_object(Config)

    # 1. 初始化 SQLAlchemy 資料庫連動
    db.init_app(app)

    # 2. 初始化 Flask-Migrate 資料庫動態版控工具
    migrate = Migrate(app, db)

    # 3. 初始化 Flask-Login 承辦人身份驗證機制
    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.login_message = '請先登入承辦人帳號以進行資料庫修改與人工勾選採認。'
    login_manager.login_message_category = 'warning'
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # 4. 初始化教育部政策知識庫與動態標籤規則 (JSON 持久化)
    TagService.init_rules(app.config["DYNAMIC_TAG_RULES_PATH"])

    # 5. 註冊各大業務模組藍圖
    app.register_blueprint(auth_bp)      # 🔐 承辦人身份驗證 (登入/登出/密碼修改)
    app.register_blueprint(teacher_bp)   # 3.1 教師基本名冊管理
    app.register_blueprint(import_bp)    # 3.2 研習大數據批次匯入與名冊匯入
    app.register_blueprint(training_bp)  # 3.5 研習綜合查詢與審核
    app.register_blueprint(report_bp)    # 3.6 & 3.7 統計報表與儀表板
    app.register_blueprint(tag_bp)       # 政策指標關鍵字設定 API

    # =========================================================================
    # 6. 首頁儀表板路由 (開放所有人檢視 + 精準檔期與最新研習檢核基準日)
    # =========================================================================
    @app.route("/")
    def dashboard():
        try:
            # (A) 計算全校編制教師總數
            total_teachers = Teacher.query.count()
            if total_teachers == 0:
                total_teachers = db.session.query(TrainingRecord.teacher_id).distinct().count()

            denom = total_teachers if total_teachers > 0 else 1

            # (B) 精準計算「檢核基準日」
            audit_base_date = None
            upload_folder = app.config["UPLOAD_FOLDER"]
            if os.path.exists(upload_folder):
                imported_files = [
                    os.path.join(upload_folder, f) for f in os.listdir(upload_folder)
                    if f.lower().endswith(('.csv', '.xlsx', '.xls')) and os.path.isfile(os.path.join(upload_folder, f))
                ]
                if imported_files:
                    latest_file = max(imported_files, key=os.path.getmtime)
                    file_mtime = os.path.getmtime(latest_file)
                    audit_base_date = datetime.fromtimestamp(file_mtime).strftime("%Y-%m-%d")

            if not audit_base_date:
                latest_training = db.session.query(Training).filter(Training.course_date != None, Training.course_date != '').order_by(Training.id.desc()).first()
                if latest_training and latest_training.course_date:
                    audit_base_date = str(latest_training.course_date).strip()
                else:
                    latest_record = TrainingRecord.query.order_by(TrainingRecord.id.desc()).first()
                    if latest_record and latest_record.created_at:
                        audit_base_date = latest_record.created_at.strftime("%Y-%m-%d")
                    else:
                        audit_base_date = datetime.now().strftime("%Y-%m-%d")

            # (C) 計算所有處室與指標之達成率
            tag_stats = {}
            all_tags = set(TagService.PRESET_TAGS).union(set(TagService.get_rules().keys()))
            
            for tag in all_tags:
                passed_count = db.session.query(TrainingRecord.teacher_id)\
                    .filter(TrainingRecord.matched_tags.like(f'%{tag}%'), TrainingRecord.passed == True)\
                    .distinct().count()
                
                percentage = round((passed_count / denom) * 100, 1)
                tag_stats[tag] = {
                    'count': passed_count,
                    'percentage': percentage
                }

            # (D) 取得指標 Pattern 第二個元素的顯示名稱字典
            tag_display_names = {tag: TagService.get_display_name(tag) for tag in all_tags}

            # (E) 核心門檻 (以教務處 A1 數位學習工作坊為基準) 完成人數與待加強人數
            a1_count = tag_stats.get('A1', {}).get('count', 0)
            completed_teachers = min(a1_count, total_teachers)
            pending_teachers = max(0, total_teachers - completed_teachers)

        except Exception as e:
            print(f"⚠️ 統計儀表板數據時發生錯誤: {e}")
            total_teachers = 0
            completed_teachers = 0
            pending_teachers = 0
            audit_base_date = datetime.now().strftime("%Y-%m-%d")
            tag_stats = {}
            tag_display_names = {}

        return render_template(
            "dashboard.html",
            total_teachers=total_teachers,
            completed_teachers=completed_teachers,
            pending_teachers=pending_teachers,
            audit_base_date=audit_base_date,
            tag_stats=tag_stats,
            tag_display_names=tag_display_names,  # 💡 傳遞格式化的 Pattern 顯示名稱
            dept_groups=TagService.DEPARTMENT_GROUPS
        )

    # =========================================================================
    # 7. 🔐 Admin 專屬：安全清空資料庫與系統重置 API
    # =========================================================================
    @app.route("/admin/reset-database", methods=["POST"])
    @app.route("/reset-database", methods=["POST"])
    @login_required
    def reset_database():
        if current_user.role != 'admin':
            flash("權限不足！只有系統管理員 (Admin) 能夠執行清空資料庫操作。", "danger")
            return redirect(url_for("dashboard"))

        confirm_password = request.form.get("confirm_password", "").strip()
        if not check_password_hash(current_user.password_hash, confirm_password):
            flash("管理員密碼驗證失敗！無法執行清空作業。", "danger")
            return redirect(url_for("dashboard"))

        try:
            SystemAuditLog.query.delete()
            TrainingRecord.query.delete()
            Training.query.delete()
            Teacher.query.delete()
            db.session.commit()

            if os.path.exists(app.config.get("FAISS_INDEX_PATH", "")):
                os.remove(app.config["FAISS_INDEX_PATH"])

            for folder in [app.config["UPLOAD_FOLDER"], app.config["EXPORT_FOLDER"], app.config["REPORT_FOLDER"]]:
                if os.path.exists(folder):
                    for filename in os.listdir(folder):
                        file_path = os.path.join(folder, filename)
                        if os.path.isfile(file_path):
                            os.remove(file_path)
                        elif os.path.isdir(file_path):
                            shutil.rmtree(file_path)

            flash("全站資料庫與快取已成功清空重置！系統已恢復至初始狀態。", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"清空資料庫時發生錯誤: {e}", "danger")

        return redirect(url_for("dashboard"))

    # 8. 全域 Jinja2 樣板變數注入
    @app.context_processor
    def inject_global_vars():
        return dict(
            system_name=app.config["SYSTEM_NAME"],
            preset_tags=app.config["PRESET_TAGS"],
            current_user=current_user
        )

    # 9. 系統啟動前置檢查與初始化
    with app.app_context():
        db.create_all()

        default_admin = User.query.filter_by(username=app.config["DEFAULT_ADMIN_USERNAME"]).first()
        if not default_admin:
            hashed_pwd = generate_password_hash(app.config["DEFAULT_ADMIN_PASSWORD"], method='scrypt')
            admin_user = User(
                username=app.config["DEFAULT_ADMIN_USERNAME"],
                password_hash=hashed_pwd,
                real_name="教務處資訊組長",
                role="admin",
                department="教務處"
            )
            db.session.add(admin_user)
            db.session.commit()

        instance_dir = os.path.dirname(app.config["DYNAMIC_TAG_RULES_PATH"])
        if not os.path.exists(instance_dir):
            os.makedirs(instance_dir, exist_ok=True)

        for folder_path in [
            app.config["UPLOAD_FOLDER"],
            app.config["EXPORT_FOLDER"],
            app.config["REPORT_FOLDER"],
            app.config["BACKUP_FOLDER"],
        ]:
            if not os.path.exists(folder_path):
                os.makedirs(folder_path, exist_ok=True)

        for tag_key, nas_subpath in app.config.get("NAS_SPECIFIC_PATHS", {}).items():
            nas_local_folder = os.path.join(app.config["UPLOAD_FOLDER"], tag_key)
            if not os.path.exists(nas_local_folder):
                os.makedirs(nas_local_folder, exist_ok=True)

    return app


# =========================================================================
# 程式執行進入點 (Waitress Production Mode)
# =========================================================================
if __name__ == "__main__":
    def get_local_ip():
        """自動取得本機在校內區網的實體 IP 位址"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    app = create_app()

    host = "0.0.0.0"
    port = 5000
    threads = 6
    local_ip = get_local_ip()

    print("==========================================================")
    print(" 🚀 教師研習檢核與統計管理系統 (V2 權限版與AI驗證ready) 已成功啟動！")
    print(f" 📌 運行模式: Waitress WSGI Production Server (Threads: {threads})")
    print(f" 🔐 承辦人登入機制: 已開啟 (預設帳號: {Config.DEFAULT_ADMIN_USERNAME})")
    print(f" 📍 本機存取網址: http://127.0.0.1:{port}/")
    print(f" 📍 校內區網網址: http://{local_ip}:{port}/")
    print("==========================================================")

    try:
        serve(app, host=host, port=port, threads=threads)
    except Exception as e:
        print(f"❌ 伺服器啟動失敗: {e}", file=sys.stderr)
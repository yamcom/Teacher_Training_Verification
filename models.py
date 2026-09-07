# models.py
"""
教師研習檢核與統計管理系統 (TTVS) V2 - 資料庫模型檔 (Flask-Migrate 相容版)
包含 User, Teacher, Training, TrainingRecord 及 SystemAuditLog 資料表
"""
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(UserMixin, db.Model):
    """
    🔐 承辦人員與系統管理員模型 (User Model)
    用於系統登入驗證、權限控管與人工採認審核人追溯
    """
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(50), unique=True, nullable=False, index=True) # 登入帳號
    password_hash = db.Column(db.String(255), nullable=False)                    # 密碼雜湊碼 (scrypt/pbkdf2)
    real_name = db.Column(db.String(50), nullable=False)                        # 承辦人真實姓名 / 職稱
    role = db.Column(db.String(20), nullable=False, default='reviewer')         # 權限角色: 'admin' (系統管理員), 'reviewer' (處室承辦人)
    department = db.Column(db.String(50), nullable=True)                        # 所屬處室 (如: 教務處, 輔導室, 生教組)
    
    is_active = db.Column(db.Boolean, default=True)                             # 帳號是否啟用
    last_login = db.Column(db.DateTime, nullable=True)                          # 最後登入時間
    created_at = db.Column(db.DateTime, default=datetime.now)

    # 關聯人工審核紀錄
    reviewed_records = db.relationship('TrainingRecord', backref='reviewer', lazy=True)

    def set_password(self, password):
        """密碼加密設定"""
        self.password_hash = generate_password_hash(password, method='scrypt')

    def check_password(self, password):
        """密碼驗證比對"""
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.username} ({self.real_name}) - Role:{self.role}>"


class Teacher(db.Model):
    """
    3.1 教師基本名冊模型 (Teacher Model)
    儲存全校編制內教師母名單
    """
    __tablename__ = 'teachers'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    position = db.Column(db.String(50), nullable=False)      # 行政職位 / 班級職稱 (如：校長、教務主任、導師)
    name = db.Column(db.String(50), nullable=False)          # 教師真實姓名 (經標準化去除空白)
    teacher_code = db.Column(db.String(50), nullable=True)   # 教師編號 / 員工代碼 (選填)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    # 🔗 行政防呆連動：設定一對多級聯刪除 (Cascade Delete)
    training_records = db.relationship(
        'TrainingRecord',
        backref='teacher',
        lazy=True,
        cascade='all, delete-orphan'
    )

    @property
    def records(self):
        """相容舊版/統計服務存取 teacher.records"""
        return self.training_records

    def __repr__(self):
        return f"<Teacher {self.position} - {self.name}>"


class Training(db.Model):
    """
    3.2 研習課程主檔模型 (Training Model)
    儲存研習課程之靜態資訊及處室標籤分類
    """
    __tablename__ = 'trainings'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    course_code = db.Column(db.String(100), unique=True, nullable=False, index=True) # 教育部/進修網課程代碼
    title = db.Column(db.Text, nullable=False)                                         # 完整研習名稱
    organizer = db.Column(db.String(150), nullable=True)                               # 主辦單位
    course_date = db.Column(db.String(50), nullable=True)                              # 研習基準辦理日期 (通常同結束日期)
    
    # 💡 新增：明確記錄「課程開始時間」與「課程結束時間」
    start_date = db.Column(db.String(50), nullable=True)                               # 課程開始時間 (YYYY-MM-DD)
    end_date = db.Column(db.String(50), nullable=True)                                 # 課程結束時間 (YYYY-MM-DD)
    
    # 處室研習分類鍵 (用於對應 Config.NAS_SPECIFIC_PATHS)
    category_key = db.Column(db.String(50), nullable=True, default='general')

    # 關聯研習紀錄表
    records = db.relationship('TrainingRecord', backref='training', lazy=True)

    def __repr__(self):
        return f"<Training [{self.course_code}] {self.title[:15]}>"


class TrainingRecord(db.Model):
    """
    3.5 研習時數與審核紀錄關係表 (TrainingRecord Model)
    橋接教師與研習課程，包含 AI 輔助審核、人工採認與審核人追溯
    """
    __tablename__ = 'training_records'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'), nullable=False)
    training_id = db.Column(db.Integer, db.ForeignKey('trainings.id'), nullable=False)
    
    hours = db.Column(db.Float, nullable=False, default=0.0)             # 實核時數 (hours > 0 判定為通過)
    passed = db.Column(db.Boolean, nullable=False, default=True)         # 通過判定狀態
    certificate_no = db.Column(db.String(100), nullable=True)           # 通過字號 / 研習證書編號
    matched_tags = db.Column(db.String(100), nullable=True)             # 匹配之政策標籤 (如: "A1,B5-1")
    
    # 🤖 機器輔助與人工審核欄位 (Pipeline B & Human Review)
    is_manual = db.Column(db.Boolean, default=False)                     # 是否為人工採認/AI憑證審核紀錄
    confidence = db.Column(db.Float, default=1.0)                        # AI 判定信心值 (0.0 ~ 1.0)
    review_status = db.Column(db.String(20), default='passed')          # 審核狀態: 'passed', 'pending_review', 'rejected'
    proof_path = db.Column(db.Text, nullable=True)                       # 證書檔案名稱 / 原始上傳檔名
    nas_subpath = db.Column(db.Text, nullable=True)                      # 幸安國小指定處室 NAS 相對儲存路徑
    
    # 🔐 承辦人審核歷程追溯外鍵 (指向 users.id)
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)                  # 人工勾選採認之時間

    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    def __repr__(self):
        return f"<TrainingRecord TeacherID:{self.teacher_id} Hours:{self.hours} Passed:{self.passed}>"


class SystemAuditLog(db.Model):
    """
    13. AI 檢核稽核中心模型 (SystemAuditLog Model)
    完整記錄每次 AI 憑證審核之 OCR 原文、AI 輸出、信心值與人工修正履歷
    """
    __tablename__ = 'system_audit_logs'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    record_id = db.Column(db.Integer, db.ForeignKey('training_records.id'), nullable=True)
    
    file_name = db.Column(db.String(255), nullable=False)                # 上傳的證書原始檔名
    ocr_raw_text = db.Column(db.Text, nullable=True)                     # PyMuPDF / PP-OCR 萃取之原始文字
    ai_json_output = db.Column(db.Text, nullable=True)                   # Qwen2.5 LLM 輸出之原始 JSON 字串
    confidence = db.Column(db.Float, default=0.0)                        # 計算得出的信心值
    
    diff_log = db.Column(db.Text, nullable=True)                         # 人工覆核修正前後差異紀錄
    operator_id = db.Column(db.String(50), default='System_AI')         # 操作者 ID / 行政帳號
    created_at = db.Column(db.DateTime, default=datetime.now)

    def __repr__(self):
        return f"<SystemAuditLog [{self.id}] File:{self.file_name} Conf:{self.confidence}>"
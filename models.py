# models.py
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Teacher(db.Model):
    """教師資料表"""
    __tablename__ = 'teachers'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True) # 系統流水號
    position = db.Column(db.String(50), nullable=False)            # 職位 (校長、主任等)
    name = db.Column(db.String(50), nullable=False, index=True)     # 教師姓名
    teacher_code = db.Column(db.String(50), nullable=True)          # 教師編號 (選填)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 關聯到研習紀錄
    records = db.relationship('TrainingRecord', backref='teacher', lazy=True)

class Training(db.Model):
    """研習課程表"""
    __tablename__ = 'trainings'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    course_code = db.Column(db.String(50), unique=True, nullable=False) # 課程代碼
    title = db.Column(db.String(255), nullable=False)                  # 研習課程名稱
    organizer = db.Column(db.String(255), nullable=True)               # 主辦單位
    course_date = db.Column(db.String(50), nullable=True)              # 課程日期
    
    records = db.relationship('TrainingRecord', backref='training', lazy=True)

class TrainingRecord(db.Model):
    """教師研習紀錄表"""
    __tablename__ = 'training_records'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'), nullable=False)
    training_id = db.Column(db.Integer, db.ForeignKey('trainings.id'), nullable=False)
    cert_number = db.Column(db.String(100), nullable=True)             # 通過字號
    hours = db.Column(db.Float, default=0.0)                           # 實核時數
    
    @property
    def is_passed(self):
        """3.4 檢核規則：實核時數 > 0 為通過"""
        return "通過" if self.hours > 0 else "未通過"
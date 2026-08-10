# routes/training_routes.py
"""
教師研習檢核與統計管理系統 (TTVS) V2 - 3.5 教師研習查詢與審核路由模組
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, Teacher, TrainingRecord, Training, User
from services.tag_service import TagService

training_bp = Blueprint('training', __name__, url_prefix='/trainings')


@training_bp.route('/', methods=['GET'])
def list_trainings():
    """3.5 教師研習綜合查詢頁面"""
    search_keyword = request.args.get('keyword', '').strip()
    selected_tag = request.args.get('tag', '').strip()
    selected_teacher_id = request.args.get('teacher_id', type=int)

    try:
        # 1. 建立基礎查詢，關聯 Teacher 與 Training
        query = db.session.query(TrainingRecord).join(Teacher).join(Training)

        # 2. 條件篩選：關鍵字 (姓名、職稱、研習名稱、課程代碼)
        if search_keyword:
            query = query.filter(
                (Teacher.name.like(f"%{search_keyword}%")) |
                (Teacher.position.like(f"%{search_keyword}%")) |
                (Training.title.like(f"%{search_keyword}%")) |
                (Training.course_code.like(f"%{search_keyword}%"))
            )

        # 3. 條件篩選：特定標籤 (如 A1, B5-1)
        if selected_tag:
            query = query.filter(TrainingRecord.matched_tags.like(f"%{selected_tag}%"))

        # 4. 條件篩選：特定教師
        if selected_teacher_id:
            query = query.filter(TrainingRecord.teacher_id == selected_teacher_id)

        # 取得前 500 筆紀錄避免網頁過載
        records = query.order_by(TrainingRecord.id.desc()).limit(500).all()

        # 取得所有教師選單以供下拉式選單篩選
        teachers = Teacher.query.order_by(Teacher.position, Teacher.name).all()

    except Exception as e:
        print(f"❌ 查詢研習紀錄時發生錯誤: {e}")
        records = []
        teachers = []
        flash(f"查詢研習紀錄時發生資料庫錯誤: {e}", "danger")

    return render_template(
        'trainings.html',
        records=records,
        teachers=teachers,
        search_keyword=search_keyword,
        selected_tag=selected_tag,
        selected_teacher_id=selected_teacher_id
    )


@training_bp.route('/toggle-pass/<int:record_id>', methods=['POST'])
@login_required
def toggle_pass(record_id):
    """人工勾選採認 / 撤銷採認 API"""
    record = TrainingRecord.query.get_or_404(record_id)
    
    try:
        record.passed = not record.passed
        record.is_manual = True
        record.reviewed_by_id = current_user.id
        db.session.commit()
        
        status_str = "採認通過" if record.passed else "取消採認"
        flash(f"已成功將紀錄 #{record.id} 標記為：{status_str}！", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"更新審核狀態失敗: {e}", "danger")

    return redirect(request.referrer or url_for('training.list_trainings'))
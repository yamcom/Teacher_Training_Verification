# routes/training_routes.py
"""
教師研習檢核與統計管理系統 (TTVS) V2 - 3.5 教師研習綜合查詢與檢核模組
包含：
1. 動態讀取現行指標規則與中文名稱，供下拉選單即時連動
2. 多維度查詢 (教師姓名、研習關鍵字、特定政策標籤)
3. 支援分頁與人工審核狀態切換 API
"""
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required
from models import db, Teacher, Training, TrainingRecord
from services.tag_service import TagService

training_bp = Blueprint('training', __name__, url_prefix='/trainings')


@training_bp.route('/', methods=['GET'])
@training_bp.route('/list', methods=['GET'])
@login_required
def list_trainings():
    """3.5 教師研習綜合查詢與檢核主頁面"""
    teacher_name = request.args.get('teacher_name', '').strip()
    course_keyword = request.args.get('course_keyword', '').strip()
    selected_tag = request.args.get('selected_tag', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)

    # 1. 動態讀取現行所有指標標籤與顯示名稱 (同步 tag/settings 最新設定)
    current_rules = TagService.get_rules()
    all_tags = list(dict.fromkeys(TagService.PRESET_TAGS + list(current_rules.keys())))
    tag_display_names = {tag: TagService.get_display_name(tag) for tag in all_tags}

    # 2. 聯集查詢 TrainingRecord, Teacher, Training
    query = db.session.query(TrainingRecord, Teacher, Training).join(
        Teacher, TrainingRecord.teacher_id == Teacher.id
    ).join(
        Training, TrainingRecord.training_id == Training.id
    )

    if teacher_name:
        query = query.filter(Teacher.name.like(f'%{teacher_name}%'))
    if course_keyword:
        query = query.filter(Training.title.like(f'%{course_keyword}%'))
    if selected_tag:
        query = query.filter(TrainingRecord.matched_tags.like(f'%{selected_tag}%'))

    query = query.order_by(Training.course_date.desc(), TrainingRecord.id.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return render_template(
        'trainings.html',
        pagination=pagination,
        records=pagination.items,
        all_tags=all_tags,
        tag_display_names=tag_display_names,
        selected_tag=selected_tag,
        teacher_name=teacher_name,
        course_keyword=course_keyword
    )


@training_bp.route('/audit/<int:record_id>', methods=['POST'])
@login_required
def toggle_audit(record_id):
    """人工勾選審核切換 API"""
    record = TrainingRecord.query.get_or_404(record_id)
    data = request.get_json() or {}
    record.passed = bool(data.get('passed', False))
    db.session.commit()
    return jsonify({'success': True, 'passed': record.passed})
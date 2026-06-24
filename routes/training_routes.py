# routes/training_routes.py
from flask import Blueprint, render_template, request, jsonify
from models import db, Training, TrainingRecord, Teacher
from services.tag_service import TagService

# 建立研習課程與查詢專屬的藍圖
training_bp = Blueprint('training', __name__)

@training_bp.route('/trainings', methods=['GET'])
def list_trainings():
    """
    3.5 教師研習查詢 主頁
    支援多重條件式綜合查詢：教師姓名、職位、課程代碼、研習名稱、標籤。
    """
    # 獲取前端網頁傳遞的篩選參數
    search_teacher = request.args.get('teacher_name', '').strip()
    search_position = request.args.get('position', '').strip()
    search_code = request.args.get('course_code', '').strip()
    search_title = request.args.get('training_title', '').strip()
    search_tag = request.args.get('tag', '').strip()

    # 建立多表結合查詢 (Join)
    query = db.session.query(TrainingRecord).join(Teacher).join(Training)

    # 動態組合 SQL 查詢條件
    if search_teacher:
        query = query.filter(Teacher.name.like(f"%{search_teacher}%"))
    if search_position:
        query = query.filter(Teacher.position.like(f"%{search_position}%"))
    if search_code:
        query = query.filter(Training.course_code.like(f"%{search_code}%"))
    if search_title:
        query = query.filter(Training.title.like(f"%{search_title}%"))

    all_records = query.all()
    results = []

    # 走訪紀錄，並在 Python 層進行「3.3 研習標籤」與「3.4 狀態判定」處理
    for r in all_records:
        # 自動解析該研習名稱中的所有標籤
        tags = TagService.parse_training_name(r.training.title)
        
        # 如果使用者有篩選特定標籤（例如 A1 或 B5-1），則過濾不符者
        if search_tag and (search_tag not in tags):
            continue

        results.append({
            'id': r.id,
            'teacher_name': r.teacher.name,
            'position': r.teacher.position,
            'course_code': r.training.course_code,
            'training_title': r.training.title,
            'hours': r.hours,
            'is_passed': r.is_passed,  # 實核時數 > 0 為通過，= 0 為未通過
            'tags': tags,
            'course_date': r.training.course_date
        })

    return render_template(
        'trainings.html', 
        records=results,
        search_teacher=search_teacher,
        search_position=search_position,
        search_code=search_code,
        search_title=search_title,
        search_tag=search_tag,
        preset_tags=TagService.PRESET_TAGS
    )


@training_bp.route('/training/record/delete/<int:id>', methods=['POST'])
def delete_record(id):
    """
    手動修正功能：刪除某一筆錯誤或重複匯入的教師研習紀錄
    """
    try:
        # 修正：將 get_or_400 改為標準的 get_or_404
        record = TrainingRecord.query.get_or_404(id)
        teacher_name = record.teacher.name
        training_title = record.training.title
        
        db.session.delete(record)
        db.session.commit()
        return jsonify({"message": f"已成功移除教師 {teacher_name} 的研習紀錄：{training_title}"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"刪除研習紀錄失敗: {str(e)}"}), 500


@training_bp.route('/training/record/update_hours', methods=['POST'])
def update_hours():
    """
    手動更正實核時數，系統會依據 3.4 節自動重新判定「通過/未通過」狀態
    """
    try:
        record_id = request.form.get('record_id')
        new_hours = request.form.get('hours')

        if not record_id or new_hours is None:
            return jsonify({"error": "缺少必要參數"}), 400

        # 修正：將 get_or_400 改為標準的 get_or_404
        record = TrainingRecord.query.get_or_404(int(record_id))
        record.hours = float(new_hours)
        db.session.commit()

        return jsonify({
            "message": "時數已更新", 
            "new_status": record.is_passed, 
            "hours": record.hours
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"時數更正失敗: {str(e)}"}), 500
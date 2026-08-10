# routes/report_routes.py
"""
教師研習檢核與統計管理系統 (TTVS) V2 - 3.6 研習統計分析模組
修正重點：
1. 完整計算各指標之「已完成人數」與「未完成人數」
2. 匯整並傳遞「已完成教師名冊」與「未完成教師名冊」供前端 Modal 穿透查詢
3. 導入 tag_display_names 支援 Pattern 第二個元素顯示名稱
4. 保持指標排序穩定，避免前端卡片顯示順序錯亂
"""
from flask import Blueprint, render_template, request, flash, jsonify
from models import db, Teacher, TrainingRecord, Training
from services.tag_service import TagService

report_bp = Blueprint('report', __name__, url_prefix='/reports')


@report_bp.route('/statistics', methods=['GET'])
@report_bp.route('/', methods=['GET'])
def statistics_page():
    """3.6 研習統計分析頁面：計算各指標已完成與未完成教師明細"""
    try:
        # 1. 取得全校所有編制教師 (依處室與姓名排序)
        all_teachers = Teacher.query.order_by(Teacher.position.asc(), Teacher.name.asc()).all()
        total_teachers_count = len(all_teachers)
        
        # 若名冊為空，備援改抓 TrainingRecord 內有紀錄的不重複教師數
        if total_teachers_count == 0:
            total_teachers_count = db.session.query(TrainingRecord.teacher_id).distinct().count()

        denom = total_teachers_count if total_teachers_count > 0 else 1

        # 2. 匯整所有指標代碼 (保持固定排序)
        all_rules = TagService.get_rules()
        all_tags = list(dict.fromkeys(TagService.PRESET_TAGS + list(all_rules.keys())))

        tag_stats = {}
        tag_display_names = {}

        for tag in all_tags:
            # 取得顯示名稱 (優先採用 Pattern 第二個元素)
            tag_display_names[tag] = TagService.get_display_name(tag)

            # 查詢該指標通過採認的不重複教師 ID 集合
            passed_teacher_ids = set(
                r[0] for r in db.session.query(TrainingRecord.teacher_id)
                .filter(TrainingRecord.matched_tags.like(f'%{tag}%'), TrainingRecord.passed == True)
                .distinct().all()
            )

            completed_teachers = []
            pending_teachers = []

            # 將全校教師進行分類：已完成 vs 未完成
            for t in all_teachers:
                t_info = {
                    'id': t.id,
                    'name': t.name,
                    'position': t.position,
                    'code': t.teacher_code or '未設定'
                }
                if t.id in passed_teacher_ids:
                    completed_teachers.append(t_info)
                else:
                    pending_teachers.append(t_info)

            passed_count = len(completed_teachers)
            pending_count = len(pending_teachers)
            percentage = round((passed_count / denom) * 100, 1)

            # 組成完整指標統計結構
            tag_stats[tag] = {
                'count': passed_count,
                'pending_count': pending_count,
                'percentage': percentage,
                'completed_teachers': completed_teachers,
                'pending_teachers': pending_teachers
            }

    except Exception as e:
        print(f"❌ 載入 3.6 研習統計數據失敗: {e}")
        flash(f"無法載入研習統計數據: {e}", "danger")
        total_teachers_count = 0
        tag_stats = {}
        tag_display_names = {}

    return render_template(
        'statistics.html',
        total_teachers=total_teachers_count,
        tag_stats=tag_stats,
        tag_display_names=tag_display_names,
        preset_tags=all_tags,
        dept_groups=TagService.DEPARTMENT_GROUPS
    )
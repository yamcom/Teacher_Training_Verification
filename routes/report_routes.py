# routes/report_routes.py
"""
教師研習檢核與統計管理系統 (TTVS) V2 - 3.6 研習統計分析模組
修正重點：
1. 動態比對現行存在的指標（包含自訂指標與刪除指標），與 tag/settings 完全同步
2. 自動將自訂指標依前綴（AA、SP、SA、GA）歸類至對應處室，其他歸入自訂區塊
3. 完整計算各指標之已完成/未完成教師名冊供前端 Modal 查詢
"""
from flask import Blueprint, render_template, request, flash, jsonify
from models import db, Teacher, TrainingRecord, Training
from services.tag_service import TagService

report_bp = Blueprint('report', __name__, url_prefix='/reports')


@report_bp.route('/statistics', methods=['GET'])
@report_bp.route('/', methods=['GET'])
def statistics_page():
    """3.6 研習統計分析頁面：計算各指標已完成與未完成教師明細 (與設定動態連動)"""
    try:
        # 1. 取得全校所有編制教師 (依處室與姓名排序)
        all_teachers = Teacher.query.order_by(Teacher.position.asc(), Teacher.name.asc()).all()
        total_teachers_count = len(all_teachers)
        
        # 若名冊為空，備援改抓 TrainingRecord 內不重複教師數
        if total_teachers_count == 0:
            total_teachers_count = db.session.query(TrainingRecord.teacher_id).distinct().count()

        denom = total_teachers_count if total_teachers_count > 0 else 1

        # 2. 取得目前真正生效的指標清單 (排除已在 tag/settings 刪除的指標)
        current_rules = TagService.get_rules()
        # 只有在 current_rules 且關鍵字不為空的指標才算有效存在
        active_tags = [
            tag for tag, rule in current_rules.items()
            if (isinstance(rule, dict) and rule.get('keywords')) or (isinstance(rule, list) and rule)
        ]
        
        # 若設定檔尚未初始化，則使用預設指標
        if not active_tags:
            active_tags = list(TagService.PRESET_TAGS)

        # 3. 動態重構處室分類 (解決 dept_groups 靜態寫死問題)
        dynamic_dept_groups = {}
        assigned_tags = set()

        base_dept_groups = getattr(TagService, 'DEPARTMENT_GROUPS', {})
        for dept_name, tags in base_dept_groups.items():
            # 僅保留目前仍存在於設定檔中的指標
            valid_dept_tags = [t for t in tags if t in active_tags]
            if valid_dept_tags:
                dynamic_dept_groups[dept_name] = valid_dept_tags
                assigned_tags.update(valid_dept_tags)

        # 檢查是否有未被預設處室收納的新增自訂指標 (例如自訂的 AA02, SP02, NEW01 等)
        unassigned_tags = [t for t in active_tags if t not in assigned_tags]
        if unassigned_tags:
            # 依前綴自動嘗試歸類
            for tag in unassigned_tags:
                matched_dept = None
                for dept_name in dynamic_dept_groups.keys():
                    if '教務' in dept_name and tag.upper().startswith('AA'):
                        matched_dept = dept_name
                    elif '輔導' in dept_name and tag.upper().startswith('SP'):
                        matched_dept = dept_name
                    elif '學務' in dept_name and tag.upper().startswith('SA'):
                        matched_dept = dept_name
                    elif '總務' in dept_name and tag.upper().startswith('GA'):
                        matched_dept = dept_name

                if matched_dept:
                    dynamic_dept_groups[matched_dept].append(tag)
                else:
                    if '其他自訂政策指標' not in dynamic_dept_groups:
                        dynamic_dept_groups['其他自訂政策指標'] = []
                    dynamic_dept_groups['其他自訂政策指標'].append(tag)

        # 4. 計算各指標通過與未通過教師名冊
        tag_stats = {}
        tag_display_names = {}

        for tag in active_tags:
            tag_display_names[tag] = TagService.get_display_name(tag)

            # 查詢通過採認的不重複教師 ID
            passed_teacher_ids = set(
                r[0] for r in db.session.query(TrainingRecord.teacher_id)
                .filter(TrainingRecord.matched_tags.like(f'%{tag}%'), TrainingRecord.passed == True)
                .distinct().all()
            )

            completed_teachers = []
            pending_teachers = []

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
        dynamic_dept_groups = {}
        active_tags = []

    return render_template(
        'statistics.html',
        total_teachers=total_teachers_count,
        tag_stats=tag_stats,
        tag_display_names=tag_display_names,
        preset_tags=active_tags,
        dept_groups=dynamic_dept_groups
    )
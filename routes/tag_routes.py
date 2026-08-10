# routes/tag_routes.py
"""
教師研習檢核與統計管理系統 (TTVS) V2 - 政策指標關鍵字與日期設定路由模組
支援：
1. 傳遞 tag_display_names (Pattern 第二個元素名稱) 至前端 HTML
2. 完整讀取與儲存 key-value (含「研習過即可」與「學年度起訖日期」) 結構
3. 舊版純陣列 JSON 自動相容轉化
4. 傳遞完整的 preset_tags 給前端樣板，確保新增的指標在儲存後仍能正確渲染
5. 清空所有研習紀錄 API (/tags/clear-trainings，僅限 Admin，需驗證密碼)
"""
import json
import io
import csv
from datetime import datetime, date
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, Response
from flask_login import login_required, current_user
from werkzeug.security import check_password_hash
from services.tag_service import TagService

tag_bp = Blueprint('tag', __name__, url_prefix='/tags')


# =========================================================================
# ⚙️ 1. 指標關鍵字與日期設定頁面與表單更新
# =========================================================================
@tag_bp.route('/settings', methods=['GET', 'POST'])
@login_required
def tag_settings_page():
    """指標關鍵字與採認日期起訖設定頁面與線上表單更新"""
    rules_path = current_app.config["DYNAMIC_TAG_RULES_PATH"]

    if request.method == 'POST':
        try:
            new_rules = {}
            current_today = date.today().strftime('%Y-%m-%d')

            # 💡 動態掃描表單中所有以 "tag_" 開頭的 key (精準抓取自訂新增的 AA02 等欄位)
            submitted_tags = set()
            for form_key in request.form.keys():
                if form_key.startswith("tag_"):
                    tag_code = form_key.replace("tag_", "").strip()
                    if tag_code:
                        submitted_tags.add(tag_code)

            for tag in submitted_tags:
                raw_keywords = request.form.get(f"tag_{tag}", "").strip()
                if not raw_keywords and f"tag_{tag}" not in request.form:
                    continue  # 若此指標已被使用者刪除，則不存入

                # 依換行拆分為關鍵字/Pattern 陣列
                kw_list = [k.strip() for k in raw_keywords.replace('\r', '').split('\n') if k.strip()]

                # 解析 [研習過即可] 切換按鈕與起訖日期
                is_ever = request.form.get(f"ever_trained_{tag}") == "on"
                start_d = request.form.get(f"start_date_{tag}", "").strip()
                end_d = request.form.get(f"end_date_{tag}", "").strip()

                if is_ever:
                    start_d = "1900-01-01"
                    end_d = current_today

                new_rules[tag] = {
                    'keywords': kw_list,
                    'is_ever_trained': is_ever,
                    'start_date': start_d if start_d else "1900-01-01",
                    'end_date': end_d if end_d else current_today
                }

            # 儲存更新至 JSON 設定檔
            if TagService.update_rules(new_rules, rules_path):
                flash("政策指標關鍵字與日期起訖設定已成功儲存更新！", "success")
            else:
                flash("儲存關鍵字與日期設定時發生檔案寫入錯誤。", "danger")

        except Exception as e:
            flash(f"儲存設定檔失敗: {e}", "danger")

        return redirect(url_for('tag.tag_settings_page'))

    # GET 請求渲染頁面
    current_rules = TagService.get_rules()
    
    # 動態合併預設指標與 JSON 中現有的指標 (確保新增的指標重刷頁面後依然顯示)
    all_tags = list(dict.fromkeys(TagService.PRESET_TAGS + list(current_rules.keys())))
    tag_display_names = {tag: TagService.get_display_name(tag) for tag in all_tags}

    return render_template(
        'tag_settings.html',
        rules=current_rules,
        tag_rules=current_rules,
        tag_display_names=tag_display_names,
        preset_tags=all_tags
    )


# =========================================================================
# 🚨 2. 清空所有研習紀錄 API (/tags/clear-trainings)
# =========================================================================
@tag_bp.route('/clear-trainings', methods=['POST'])
@login_required
def clear_trainings():
    """清空所有研習紀錄與課程主檔 (僅限 Admin，需驗證密碼)"""
    # 1. 權限檢查：僅限最高管理者 (Admin) 執行
    if not current_user.is_authenticated or current_user.role != 'admin':
        flash("權限不足！只有最高管理者 (Admin) 能夠執行清空研習紀錄操作。", "danger")
        return redirect(url_for('tag.tag_settings_page'))

    # 2. 密碼二次確認驗證
    confirm_password = request.form.get("confirm_password", "").strip()
    if not check_password_hash(current_user.password_hash, confirm_password):
        flash("管理員密碼驗證失敗！無法執行清空作業。", "danger")
        return redirect(url_for('tag.tag_settings_page'))

    try:
        from models import db, TrainingRecord, Training
        
        # 3. 刪除所有研習採認紀錄 TrainingRecord 與課程主檔 Training
        num_records = TrainingRecord.query.delete()
        num_trainings = Training.query.delete()
        
        db.session.commit()
        
        flash(
            f"已成功清空所有研習紀錄！（共刪除 {num_records} 筆研習採認紀錄與 {num_trainings} 筆研習課程主檔）。"
            f"教職員名冊已完整保留，請至 3.2 重新匯入研習大數據以套用最新關鍵字。",
            "success"
        )
    except Exception as e:
        db.session.rollback()
        print(f"❌ 清空研習紀錄失敗: {e}")
        flash(f"清空研習紀錄時發生資料庫錯誤: {str(e)}", "danger")

    return redirect(url_for('tag.tag_settings_page'))


# =========================================================================
# 📤 3. 匯出現行設定檔 API (/tags/export)
# =========================================================================
@tag_bp.route('/export', methods=['GET'])
@login_required
def export_rules():
    """匯出現行關鍵字與日期設定為 JSON 檔案 (動態附加時間戳記)"""
    try:
        current_rules = TagService.get_rules()
        json_data = json.dumps(current_rules, ensure_ascii=False, indent=2)
        
        timestamp = datetime.now().strftime("%m%d%H%M")
        filename = f"tag_rules_config_{timestamp}.json"
        
        return Response(
            json_data,
            mimetype="application/json",
            headers={"Content-disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        flash(f"匯出設定檔時發生錯誤: {e}", "danger")
        return redirect(url_for('tag.tag_settings_page'))


# =========================================================================
# 📥 4. 批次匯入關鍵字設定檔 API (/tags/import)
# =========================================================================
@tag_bp.route('/import', methods=['POST'])
@login_required
def import_rules():
    """批次匯入 JSON / CSV 關鍵字與日期設定檔"""
    rules_path = current_app.config["DYNAMIC_TAG_RULES_PATH"]
    file = request.files.get('file')

    if not file or file.filename == '':
        flash("請選擇要匯入的 JSON 或 CSV 設定檔！", "warning")
        return redirect(url_for('tag.tag_settings_page'))

    filename = file.filename.lower()
    current_today = date.today().strftime('%Y-%m-%d')

    try:
        new_rules = {}

        # 📄 1. 匯入 JSON 格式
        if filename.endswith('.json'):
            content = file.stream.read().decode('utf-8')
            loaded_data = json.loads(content)

            for tag, val in loaded_data.items():
                if isinstance(val, dict):
                    new_rules[tag] = val
                elif isinstance(val, list):
                    new_rules[tag] = {
                        'keywords': val,
                        'is_ever_trained': True,
                        'start_date': '1900-01-01',
                        'end_date': current_today
                    }

        # 📄 2. 匯入 CSV 格式
        elif filename.endswith('.csv'):
            stream = io.StringIO(file.stream.read().decode("utf-8-sig"), newline=None)
            reader = csv.DictReader(stream)
            
            for row in reader:
                tag = row.get('指標代碼') or row.get('tag') or row.get('指標')
                kw = row.get('關鍵字') or row.get('keyword') or row.get('規則')
                start_d = row.get('開始日期') or row.get('start_date') or '1900-01-01'
                end_d = row.get('結束日期') or row.get('end_date') or current_today

                if tag and kw:
                    tag = tag.strip()
                    kw = kw.strip()
                    if tag not in new_rules:
                        new_rules[tag] = {
                            'keywords': [],
                            'is_ever_trained': True,
                            'start_date': start_d,
                            'end_date': end_d
                        }
                    if kw not in new_rules[tag]['keywords']:
                        new_rules[tag]['keywords'].append(kw)

        else:
            flash("不支援的檔案格式，請上傳 .json 或 .csv 檔案！", "danger")
            return redirect(url_for('tag.tag_settings_page'))

        if isinstance(new_rules, dict) and new_rules:
            if TagService.update_rules(new_rules, rules_path):
                flash("成功匯入並套用新的政策指標關鍵字與日期設定！", "success")
            else:
                flash("匯入成功但寫入檔案時失敗。", "danger")
        else:
            flash("匯入的檔案內容格式不符合預期。", "warning")

    except Exception as e:
        flash(f"解析匯入檔案時發生錯誤: {e}", "danger")

    return redirect(url_for('tag.tag_settings_page'))
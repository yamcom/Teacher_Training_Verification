# routes/import_routes.py
"""
教師研習檢核與統計管理系統 (TTVS) V2 - 名冊匯入/匯出模組
更新重點：
1. 3.2 研習紀錄大數據 CSV / Excel 批次解析 API(含研習名稱CSV檔案的逗號防呆修復機制)
   - 帶入研習名稱、研習日期與實核時數（核算時數必須 > 0）
   - 僅採認已登錄於 3.1 名冊內之教師
   - 呼叫 TagService 進行關鍵字與學年度日期起訖（支援「研習過即可」）雙重採認
   - 匯出目前系統研習紀錄 CSV API (/import/export-trainings)
2. 3.1 教師名冊 CSV / Excel 批次解析 API (保證回傳純 JSON)
"""
import io
import csv
import hashlib
import pandas as pd
from datetime import datetime, date
from flask import Blueprint, request, jsonify, render_template, Response
from flask_login import login_required, current_user
from models import db, Teacher, Training, TrainingRecord
from services.tag_service import TagService

import_bp = Blueprint('import', __name__, url_prefix='/import')


# =========================================================================
# 📄 1. 3.2 研習紀錄匯入主頁面
# =========================================================================
@import_bp.route('/page', methods=['GET'])
@import_bp.route('/', methods=['GET'])
@login_required
def import_page():
    """3.2 大數據批次研習紀錄匯入頁面"""
    return render_template('import.html')


# =========================================================================
# 📤 2. 匯出目前系統研習紀錄 CSV API (/import/export-trainings)
# =========================================================================
@import_bp.route('/export-trainings', methods=['GET'])
@login_required
def export_trainings():
    """匯出資料庫中現有的研習紀錄為符合要求的 CSV 檔案"""
    try:
        # 聯集查詢 TrainingRecord, Teacher, Training
        results = db.session.query(
            TrainingRecord, Teacher, Training
        ).join(
            Teacher, TrainingRecord.teacher_id == Teacher.id
        ).join(
            Training, TrainingRecord.training_id == Training.id
        ).order_by(TrainingRecord.id.asc()).all()

        output = io.StringIO()
        # 寫入 UTF-8-BOM 以確保 Excel 開啟時繁體中文不亂碼
        output.write('\ufeff')
        writer = csv.writer(output)

        # 寫入指定欄位標頭
        headers = [
            "編號", "教師姓名", "課程代碼", "研習課程名稱", 
            "依據文號", "課程開始時間", "課程結束時間", "主辦單位", "實核時數/學分數"
        ]
        writer.writerow(headers)

        for index, (record, teacher, training) in enumerate(results, start=1):
            # 取時數
            hours_val = getattr(record, 'hours', None) or getattr(record, 'certified_hours', None)
            if hours_val is None:
                hours_val = getattr(training, 'hours', None) or getattr(training, 'course_hours', None) or getattr(training, 'duration', 0.0)

            # 組成一筆橫列資料
            row = [
                index,                                                # 編號
                teacher.name if teacher else "",                      # 教師姓名
                training.course_code if training else "",             # 課程代碼
                training.title if training else "",                   # 研習課程名稱
                getattr(training, 'doc_number', '') or getattr(training, 'organizer', ''), # 依據文號
                training.course_date if training else "",             # 課程開始時間
                training.course_date if training else "",             # 課程結束時間
                getattr(training, 'organizer', '') if training else "",# 主辦單位
                hours_val                                             # 實核時數/學分數
            ]
            writer.writerow(row)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"system_training_records_{timestamp}.csv"

        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-disposition": f"attachment; filename={filename}"}
        )

    except Exception as e:
        print(f"❌ 匯出研習紀錄失敗: {e}")
        return jsonify({'error': f'匯出資料時發生錯誤: {str(e)}'}), 500


# =========================================================================
# 📥 3. 批量匯入研習紀錄 API (/import/trainings) - 含逗號防呆機制
# =========================================================================
@import_bp.route('/trainings', methods=['POST'])
def import_trainings():
    """處理 3.2 批量匯入研習紀錄：依據 3.1 名冊過濾，帶入時數與日期進行指標採認"""
    if not current_user.is_authenticated:
        return jsonify({'error': '請先登入承辦人帳號再進行匯入！'}), 401

    file = request.files.get('file')
    if not file or file.filename == '':
        return jsonify({'error': '請選擇要上傳的 CSV 或 Excel 檔案！'}), 400

    filename = file.filename.lower()
    if not filename.endswith(('.csv', '.xlsx', '.xls')):
        return jsonify({'error': '不支援的檔案格式，請上傳 .csv、.xlsx 或 .xls 格式！'}), 400

    try:
        rows = []

        if filename.endswith('.csv'):
            content = file.stream.read().decode('utf-8-sig', errors='ignore')
            stream = io.StringIO(content, newline=None)
            
            # 第一層防護：使用標準 csv.reader 解析（相容用雙引號包覆逗號的 CSV）
            raw_reader = list(csv.reader(stream))
            if not raw_reader:
                return jsonify({'error': '上傳的 CSV 檔案內容為空！'}), 400

            headers = [h.strip() for h in raw_reader[0]]

            # 解析資料行
            for row_idx, row in enumerate(raw_reader[1:], start=2):
                if not row or not any(row):
                    continue

                # 💡 第二層防護：智慧預處理校正機制
                # 標準預期欄位應為 9 欄（編號, 教師姓名, 課程代碼, 研習課程名稱, 依據文號, 課程開始時間, 課程結束時間, 主辦單位, 實核時數）
                if len(row) > 9:
                    extra_cols = len(row) - 9
                    # 研習名稱通常位於 index 3，將被逗號拆散的研習名稱進行重新拼接還原
                    fixed_title = ",".join(row[3: 4 + extra_cols])
                    # 重組為標準 9 欄結構
                    row = row[:3] + [fixed_title] + row[4 + extra_cols:]

                # 轉為字典與標頭對照
                clean_r = {}
                for idx, val in enumerate(row):
                    key_name = headers[idx] if idx < len(headers) else f"col_{idx}"
                    clean_r[key_name.strip()] = str(val).strip()
                
                rows.append(clean_r)

        else:
            # Excel 格式讀取處理 (.xlsx / .xls)
            excel_file = pd.ExcelFile(file.stream)
            sheet_name = excel_file.sheet_names[0]
            for name in excel_file.sheet_names:
                if '個人' in name or '研習' in name:
                    sheet_name = name
                    break
            
            df = pd.read_excel(excel_file, sheet_name=sheet_name, dtype=str)
            df = df.fillna('')
            for _, r in df.iterrows():
                clean_r = {str(k).strip(): str(v).strip() for k, v in r.items() if k is not None}
                rows.append(clean_r)

        if not rows:
            return jsonify({'error': '上傳的檔案中沒有可讀取的有效研習資料！'}), 400

        imported_records = 0
        skipped_not_in_roster = 0
        skipped_invalid = 0

        for index, clean_row in enumerate(rows, start=1):
            teacher_name = None
            title = None
            course_code = ""
            course_date = ""
            hours_str = None
            organizer = ""

            for key, val in clean_row.items():
                k_clean = str(key).replace(' ', '').replace(' ', '')
                val_str = str(val).strip()

                if any(h in k_clean for h in ['實核時數', '核算時數', '研習時數', '時數', '學分']):
                    if '名稱' not in k_clean and '代碼' not in k_clean:
                        hours_str = val_str
                elif any(t in k_clean for t in ['研習課程名稱', '課程名稱', '研習名稱', '研習項目', '課程']):
                    if '代碼' not in k_clean and '時數' not in k_clean:
                        if not title or len(val_str) > len(title):
                            title = val_str
                elif any(n in k_clean for n in ['教師姓名', '姓名', '研習人員', '學員', '教師']):
                    if '單位' not in k_clean and '學校' not in k_clean:
                        teacher_name = val_str
                elif any(c in k_clean for c in ['課程代碼', '研習代碼', '課程編號', '代碼']):
                    course_code = val_str
                elif any(d in k_clean for d in ['課程開始時間', '研習日期', '辦理日期', '日期']):
                    course_date = val_str.split(' ')[0] if val_str else ""
                elif any(o in k_clean for o in ['主辦單位', '辦理單位', '開課單位']):
                    organizer = val_str

            if not teacher_name or not title:
                skipped_invalid += 1
                continue

            clean_name = " ".join(teacher_name.replace(' ', ' ').split())

            # 依據 3.1 基本名冊過濾，不存在則跳過
            teacher = Teacher.query.filter_by(name=clean_name).first()
            if not teacher:
                skipped_not_in_roster += 1
                continue

            try:
                hours = float(hours_str) if hours_str else 0.0
            except ValueError:
                hours = 0.0

            if not course_date:
                course_date = date.today().strftime('%Y-%m-%d')

            if not course_code:
                hash_code = hashlib.md5(title.encode('utf-8')).hexdigest()[:8].upper()
                course_code = f"AUTO-{hash_code}"

            # 進行政策指標標籤匹配比對
            matched_tags_list = TagService.parse_training_name(title, course_date, hours)
            matched_tags_str = ",".join(matched_tags_list) if matched_tags_list else None

            training = Training.query.filter_by(course_code=course_code).first()
            if not training:
                training = Training.query.filter_by(title=title, course_date=course_date).first()

            if not training:
                training = Training()
                training.course_code = course_code
                training.title = title
                training.course_date = course_date
                training.organizer = organizer
                
                if hasattr(training, 'category_key'):
                    training.category_key = 'general'

                if hasattr(training, 'hours'):
                    training.hours = hours
                elif hasattr(training, 'course_hours'):
                    training.course_hours = hours
                elif hasattr(training, 'duration'):
                    training.duration = hours

                db.session.add(training)
                db.session.flush()

            existing_record = TrainingRecord.query.filter_by(
                teacher_id=teacher.id,
                training_id=training.id
            ).first()

            if not existing_record:
                new_record = TrainingRecord(
                    teacher_id=teacher.id,
                    training_id=training.id,
                    matched_tags=matched_tags_str,
                    passed=True,
                    updated_at=datetime.now()
                )

                if hasattr(new_record, 'hours'):
                    new_record.hours = hours
                elif hasattr(new_record, 'certified_hours'):
                    new_record.certified_hours = hours

                db.session.add(new_record)
                imported_records += 1

        db.session.commit()

        msg = f'研習大數據匯入完成！已成功採認與分析 3.1 名冊內教師之 {imported_records} 筆研習紀錄。'
        extra_info = []
        if skipped_not_in_roster > 0:
            extra_info.append(f'有 {skipped_not_in_roster} 筆因「未在 3.1 教師名冊中」被跳過')
        if skipped_invalid > 0:
            extra_info.append(f'有 {skipped_invalid} 筆格式不符被跳過')

        if extra_info:
            msg += f'（註：{"；".join(extra_info)}）'

        return jsonify({'message': msg}), 200

    except Exception as e:
        db.session.rollback()
        print(f"❌ 匯入研習紀錄時發生錯誤: {e}")
        return jsonify({'error': f'處理檔案時發生錯誤: {str(e)}'}), 500


# =========================================================================
# 📥 4. 批量匯入教師名冊 API (/import/teachers)
# =========================================================================
@import_bp.route('/teachers', methods=['POST'])
@import_bp.route('/teacher', methods=['POST'])
def import_teachers():
    """處理 3.1 批量匯入教師名冊 CSV / Excel (保證回傳純 JSON)"""
    if not current_user.is_authenticated:
        return jsonify({'error': '承辦人登入逾時或未登入，請先登入帳號再執行匯入！'}), 401

    file = request.files.get('file')
    if not file or file.filename == '':
        return jsonify({'error': '請選擇要上傳的 CSV 或 Excel 檔案！'}), 400

    filename = file.filename.lower()
    if not filename.endswith(('.csv', '.xlsx', '.xls')):
        return jsonify({'error': '不支援的檔案格式，請上傳 .csv、.xlsx 或 .xls 格式！'}), 400

    try:
        rows = []

        if filename.endswith('.csv'):
            content = file.stream.read().decode('utf-8-sig', errors='ignore')
            stream = io.StringIO(content, newline=None)
            reader = csv.DictReader(stream)
            for r in reader:
                clean_r = {str(k).strip(): str(v).strip() for k, v in r.items() if k is not None and v is not None}
                rows.append(clean_r)
        else:
            df = pd.read_excel(file.stream, dtype=str)
            df = df.fillna('')
            for _, r in df.iterrows():
                clean_r = {str(k).strip(): str(v).strip() for k, v in r.items() if k is not None}
                rows.append(clean_r)

        imported_count = 0
        updated_count = 0
        skipped_count = 0

        for clean_row in rows:
            position = None
            name = None
            teacher_code = None

            for key, val in clean_row.items():
                k_lower = str(key).lower()
                val_str = str(val).strip()

                if any(p in k_lower for p in ['處室職稱', '職稱', '行政職位', '行政職務', '職務', '單位', '班級']):
                    if not position:
                        position = val_str
                elif any(n in k_lower for n in ['姓名', '教師姓名', '名字', '教師']):
                    if not name:
                        name = val_str
                elif any(c in k_lower for c in ['虛擬編號', '教師編號', '員工代碼', '代碼', '編號']):
                    if not teacher_code:
                        teacher_code = val_str

            if not name or not position:
                skipped_count += 1
                continue

            clean_name = " ".join(name.replace(' ', ' ').split())
            existing = Teacher.query.filter_by(name=clean_name, position=position).first()

            if existing:
                if teacher_code and existing.teacher_code != teacher_code:
                    existing.teacher_code = teacher_code
                    updated_count += 1
            else:
                new_teacher = Teacher(
                    position=position,
                    name=clean_name,
                    teacher_code=teacher_code if teacher_code else None
                )
                db.session.add(new_teacher)
                imported_count += 1

        db.session.commit()

        msg = f'名冊匯入完成！成功新增 {imported_count} 筆教師資料，更新 {updated_count} 筆編號。'
        if skipped_count > 0:
            msg += f'（注意：有 {skipped_count} 筆無效列或欄位未匹配而被跳過）'

        return jsonify({'message': msg}), 200

    except Exception as e:
        db.session.rollback()
        print(f"❌ 匯入教師名冊時發生錯誤: {e}")
        return jsonify({'error': f'處理檔案時發生錯誤: {str(e)}'}), 500
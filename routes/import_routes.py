# routes/import_routes.py
"""
教師研習檢核與統計管理系統 (TTVS) V2 - 名冊匯入/匯出模組
更新重點：
1. 3.2 研習紀錄大數據 CSV / Excel 批次解析 API (含研習名稱逗號防呆修復機制)
   - 同時解析「課程開始時間」與「課程結束時間」，並分別寫入 start_date, end_date 與 course_date
   - 帶入研習名稱、研習結束日期與實核時數（核算時數必須 > 0）
   - 僅採認已登錄於 3.1 名冊內之教師
   - 呼叫 TagService 進行關鍵字與學年度日期起訖採認
2. 3.2 匯出目前系統研習紀錄 CSV API (/import/export-trainings)
3. 3.1 教師名冊 CSV / Excel 批次解析 API
"""
import io
import csv
import hashlib
import re
import pandas as pd
from datetime import datetime, date
from flask import Blueprint, request, jsonify, render_template, Response
from flask_login import login_required, current_user
from models import db, Teacher, Training, TrainingRecord
from services.tag_service import TagService

import_bp = Blueprint('import', __name__, url_prefix='/import')


def clean_date_str(val):
    """將字串清洗為標準 YYYY-MM-DD 格式，若無法辨識則返回乾淨字串"""
    if not val:
        return ""
    val_str = str(val).strip().replace('/', '-')
    # 擷取 YYYY-MM-DD
    match = re.search(r'(\d{4}-\d{1,2}-\d{1,2})', val_str)
    if match:
        parts = match.group(1).split('-')
        return f"{parts[0]}-{int(parts[1]):02d}-{int(parts[2]):02d}"
    return val_str.split(' ')[0]


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
        results = db.session.query(
            TrainingRecord, Teacher, Training
        ).join(
            Teacher, TrainingRecord.teacher_id == Teacher.id
        ).join(
            Training, TrainingRecord.training_id == Training.id
        ).order_by(TrainingRecord.id.asc()).all()

        output = io.StringIO()
        output.write('\ufeff')  # UTF-8-BOM
        writer = csv.writer(output)

        headers = [
            "編號", "教師姓名", "課程代碼", "研習課程名稱", 
            "依據文號", "課程開始時間", "課程結束時間", "主辦單位", "實核時數/學分數"
        ]
        writer.writerow(headers)

        for index, (record, teacher, training) in enumerate(results, start=1):
            hours_val = getattr(record, 'hours', None) or getattr(record, 'certified_hours', None)
            if hours_val is None:
                hours_val = getattr(training, 'hours', None) or getattr(training, 'course_hours', None) or getattr(training, 'duration', 0.0)

            start_date_str = getattr(training, 'start_date', '') or training.course_date or ""
            end_date_str = getattr(training, 'end_date', '') or training.course_date or ""

            row = [
                index,
                teacher.name if teacher else "",
                training.course_code if training else "",
                training.title if training else "",
                getattr(training, 'doc_number', '') or getattr(training, 'organizer', ''),
                start_date_str,
                end_date_str,
                getattr(training, 'organizer', '') if training else "",
                hours_val
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
# 📥 3. 批量匯入研習紀錄 API (/import/trainings)
# =========================================================================
@import_bp.route('/trainings', methods=['POST'])
def import_trainings():
    """處理 3.2 批量匯入研習紀錄：依據 3.1 名冊過濾，帶入時數與真實起訖日期進行指標採認"""
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
            
            raw_reader = list(csv.reader(stream))
            if not raw_reader:
                return jsonify({'error': '上傳的 CSV 檔案內容為空！'}), 400

            headers = [h.strip() for h in raw_reader[0]]

            for row_idx, row in enumerate(raw_reader[1:], start=2):
                if not row or not any(row):
                    continue

                # 智慧欄位融合修復：處理研習名稱內含逗號導致列爆開的問題
                if len(row) > 9:
                    extra_cols = len(row) - 9
                    fixed_title = ",".join(row[3: 4 + extra_cols])
                    row = row[:3] + [fixed_title] + row[4 + extra_cols:]

                clean_r = {}
                # 1. 優先使用既有位置索引填入預設鍵值（對應標準 9 欄順序）
                # [編號, 教師姓名, 課程代碼, 研習課程名稱, 依據文號, 課程開始時間, 課程結束時間, 主辦單位, 實核時數/學分數]
                if len(row) >= 7:
                    clean_r['__std_teacher_name__'] = str(row[1]).strip()
                    clean_r['__std_course_code__'] = str(row[2]).strip()
                    clean_r['__std_title__'] = str(row[3]).strip()
                    clean_r['__std_start_date__'] = str(row[5]).strip()
                    clean_r['__std_end_date__'] = str(row[6]).strip()
                if len(row) >= 9:
                    clean_r['__std_hours__'] = str(row[8]).strip()

                # 2. 標頭鍵值對應
                for idx, val in enumerate(row):
                    key_name = headers[idx] if idx < len(headers) else f"col_{idx}"
                    clean_r[key_name.strip()] = str(val).strip()
                
                rows.append(clean_r)

        else:
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
            teacher_name = clean_row.get('__std_teacher_name__')
            title = clean_row.get('__std_title__')
            course_code = clean_row.get('__std_course_code__', "")
            start_date_val = clean_row.get('__std_start_date__', "")
            end_date_val = clean_row.get('__std_end_date__', "")
            hours_str = clean_row.get('__std_hours__')
            organizer = ""

            # 針對動態標頭逐欄比對校正
            for key, val in clean_row.items():
                if key.startswith('__std_'):
                    continue
                k_clean = str(key).replace(' ', '').replace(' ', '')
                val_str = str(val).strip()

                if any(h in k_clean for h in ['實核時數', '核算時數', '研習時數', '時數', '學分']):
                    if '名稱' not in k_clean and '代碼' not in k_clean:
                        hours_str = val_str
                elif any(t in k_clean for t in ['研習課程名稱', '課程名稱', '研習名稱', '研習項目']):
                    if '代碼' not in k_clean and '時數' not in k_clean:
                        title = val_str
                elif any(n in k_clean for n in ['教師姓名', '姓名', '研習人員', '學員', '教師']):
                    if '單位' not in k_clean and '學校' not in k_clean:
                        teacher_name = val_str
                elif any(c in k_clean for c in ['課程代碼', '研習代碼', '課程編號', '代碼']):
                    course_code = val_str
                # 精確匹配結束時間與開始時間
                elif '結束' in k_clean and any(d in k_clean for d in ['時間', '日期']):
                    end_date_val = val_str
                elif '開始' in k_clean and any(d in k_clean for d in ['時間', '日期']):
                    start_date_val = val_str
                elif any(o in k_clean for o in ['主辦單位', '辦理單位', '開課單位']):
                    organizer = val_str

            if not teacher_name or not title:
                skipped_invalid += 1
                continue

            clean_name = " ".join(teacher_name.replace(' ', ' ').split())

            # 依據 3.1 基本名冊過濾
            teacher = Teacher.query.filter_by(name=clean_name).first()
            if not teacher:
                skipped_not_in_roster += 1
                continue

            try:
                hours = float(hours_str) if hours_str else 0.0
            except ValueError:
                hours = 0.0

            # 清洗起訖日期為 YYYY-MM-DD
            start_date_val = clean_date_str(start_date_val)
            end_date_val = clean_date_str(end_date_val)

            # 防呆：兩者若缺一，則互補；絕不隨意以今天日期覆寫
            if not end_date_val and start_date_val:
                end_date_val = start_date_val
            elif not start_date_val and end_date_val:
                start_date_val = end_date_val

            course_date = end_date_val

            if not course_code:
                hash_code = hashlib.md5(title.encode('utf-8')).hexdigest()[:8].upper()
                course_code = f"AUTO-{hash_code}"

            # 政策指標採認比對（以研習結束日期為基準）
            matched_tags_list = TagService.parse_training_name(title, end_date_val, hours)
            matched_tags_str = ",".join(matched_tags_list) if matched_tags_list else None

            training = Training.query.filter_by(course_code=course_code).first()
            if not training:
                training = Training.query.filter_by(title=title, course_date=course_date).first()

            if not training:
                training = Training()
                training.course_code = course_code
                training.title = title
                training.course_date = course_date
                training.start_date = start_date_val
                training.end_date = end_date_val
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
            else:
                # 💡 強制更新既有主檔的結束時間與開始時間，修復先前誤記為匯入時間的紀錄
                if end_date_val:
                    training.end_date = end_date_val
                    training.course_date = end_date_val
                if start_date_val:
                    training.start_date = start_date_val

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
            else:
                # 重新比對標籤並同步更新
                existing_record.matched_tags = matched_tags_str
                existing_record.updated_at = datetime.now()

        db.session.commit()

        msg = f'研習大數據匯入完成！已成功採認與更新 3.1 名冊內教師之 {imported_records} 筆研習紀錄。'
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
    """處理 3.1 批量匯入教師名冊 CSV / Excel"""
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
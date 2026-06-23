# routes/import_routes.py
from flask import Blueprint, render_template, request, jsonify, current_app
from models import db, Teacher, Training, TrainingRecord
from services.import_service import ImportService
import os

# 建立檔案匯入專屬的藍圖
import_bp = Blueprint('import', __name__)

def allowed_file(filename):
    """檢查上傳檔案的副檔名是否符合 config.py 中的限制"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

@import_bp.route('/import', methods=['GET'])
def import_page():
    """
    3.2 研習資料管理 - 上傳入口網頁
    渲染前端拖曳上傳介面 (import.html)，提供行政人員便利的操作空間。
    """
    return render_template('import.html')


@import_bp.route('/import/training', methods=['POST'])
def import_training_records():
    """
    3.2 研習資料管理 - 核心匯入與逐筆檢核自動化 API
    支援大量 CSV/Excel/Word 研習紀錄匯入，並依據課程代碼與 3.4 節時數規則自動檢核。
    """
    if 'file' not in request.files:
        return jsonify({"error": "未偵測到上傳檔案"}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "未選擇任何檔案"}), 400
        
    if not allowed_file(file.filename):
        return jsonify({"error": f"不支援的檔案格式！僅允許: {', '.join(current_app.config['ALLOWED_EXTENSIONS'])}"}), 400
        
    # 安全地儲存檔案至 uploads 暫存目錄
    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], file.filename)
    file.save(file_path)
    
    try:
        # 1. 調用 ImportService 進行檔案結構解析與資料清洗 (解耦多元格式)
        parsed_records = ImportService.parse_training_file(file_path)
        
        success_count = 0
        skipped_count = 0
        
        # 2. 開始進行大數據逐筆檢核與資料庫對照
        for rec in parsed_records:
            t_name = rec['teacher_name']
            c_code = rec['course_code']
            title = rec['title']
            organizer = rec['organizer']
            c_date = rec['course_date']
            hours = rec['hours']
            
            # 規則 A：比對是否為預設名冊（附件2）中的全校教師，若無則跳過，確保原始名單正確性
            teacher = Teacher.query.filter_by(name=t_name).first()
            if not teacher:
                skipped_count += 1
                continue
                
            # 規則 B：依「課程代碼」辨識是否為同一研習課程，若不存在則動態建立
            training = Training.query.filter_by(course_code=c_code).first()
            if not training:
                training = Training(
                    course_code=c_code,
                    title=title,
                    organizer=organizer,
                    course_date=c_date
                )
                db.session.add(training)
                # 預先 flush 或 commit 以取得關聯 id，並確保課程代碼唯一
                db.session.commit()
            
            # 規則 C：檢查該教師是否已有該研習紀錄。若無則新增；若有則覆蓋更新實核時數
            record = TrainingRecord.query.filter_by(teacher_id=teacher.id, training_id=training.id).first()
            if not record:
                record = TrainingRecord(
                    teacher_id=teacher.id,
                    training_id=training.id,
                    hours=hours
                )
                db.session.add(record)
            else:
                # 3.4 節判定更新：若重複匯入則覆蓋最新時數，系統屬性會自動依據 hours > 0 重新判定通過狀態
                record.hours = hours
                
            success_count += 1
            
        # 批次交易確認
        db.session.commit()
        
        # 3. 刪除處理完畢的暫存檔案，釋放主機空間
        if os.path.exists(file_path):
            os.remove(file_path)
            
        return jsonify({
            "message": "研習紀錄處理完畢！",
            "parsed_total": len(parsed_records),
            "success_inserted": success_count,
            "skipped_unregistered_teachers": skipped_count
        }), 200
        
    except Exception as e:
        db.session.rollback()
        # 發生異常時亦確保暫存檔被清除
        if os.path.exists(file_path):
            os.remove(file_path)
        return jsonify({"error": f"大數據檔案檢核失敗，原因: {str(e)}"}), 500
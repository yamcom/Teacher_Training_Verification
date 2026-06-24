# routes/report_routes.py
from flask import Blueprint, current_app, send_file, render_template, jsonify, make_response
from services.export_service import ExportService
from services.report_service import ReportService
import os

# 建立報表與統計專屬的藍圖
report_bp = Blueprint('report', __name__)

@report_bp.route('/reports')
def report_dashboard():
    """
    3.6 & 3.7 報表與統計分析主頁
    網頁端直接呼叫 ReportService 計算各標籤通過率，並渲染至前端統計頁面。
    """
    try:
        # 動態計算 A1~E 標籤的通過人數與通過率
        df_stats = ReportService.calculate_tag_statistics()
        # 轉換為字典列表供 Jinja2 樣板或前端表格渲染
        stats_list = df_stats.to_dict(orient='records')
        return render_template('statistics.html', stats=stats_list)
    except Exception as e:
        return render_template('statistics.html', error=f"無法載入統計數據: {str(e)}", stats=[])


@report_bp.route('/export/all_school_csv', methods=['GET'])
def download_all_school_csv():
    """
    3.7 & 格式需求：下載符合主管機關審查、可直接貼回 Excel 的雙欄 CSV 報表
    維持附件 2 樣板之教師原始順序，並將通過標籤以「.」串接。
    """
    try:
        # 呼叫服務生成雙欄 CSV 字串
        csv_data = ExportService.export_to_double_column_csv(current_app.config['EXPORT_FOLDER'])
        
        # 建立 Response 物件並強制設定 utf-8-sig (帶 BOM) 確保 Excel 開啟不亂碼
        response = make_response(csv_data)
        response.headers["Content-Disposition"] = "attachment; filename=all_school_report_double_column.csv"
        response.headers["Content-Type"] = "text/csv; charset=utf-8-sig"
        return response
    except Exception as e:
        return jsonify({"error": f"產出雙欄 CSV 失敗: {str(e)}"}), 500


@report_bp.route('/export/all_school_excel', methods=['GET'])
def download_all_school_excel():
    """
    第八章 報表功能：下載全校研習統計 Excel 總表 (.xlsx)
    內含兩個 Sheet：【全校研習統計總表】與【通過研習詳細明細】。
    """
    try:
        # 生成 Excel 實體檔案並獲取路徑
        file_path = ExportService.export_to_excel(current_app.config['EXPORT_FOLDER'])
        
        return send_file(
            file_path,
            as_attachment=True,
            download_name='全校教師研習統計總表.xlsx',
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except Exception as e:
        return jsonify({"error": f"產出 Excel 總表失敗: {str(e)}"}), 500


@report_bp.route('/export/official_word_report', methods=['GET'])
def download_official_word_report():
    """
    第八章 報表功能：匯出正式簽呈公文格式 (Word .docx)
    自動帶入發文資訊、主旨、行政說明及前 10 筆檢核摘要表格。
    """
    try:
        # 生成公文 Word 檔
        file_path = ExportService.export_official_word_report(current_app.config['REPORT_FOLDER'])
        
        return send_file(
            file_path,
            as_attachment=True,
            download_name='教師研習檢核簽呈公文.docx',
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
    except Exception as e:
        return jsonify({"error": f"產出正式公文失敗: {str(e)}"}), 500


@report_bp.route('/export/tag_analysis_report', methods=['GET'])
def download_tag_analysis_report():
    """
    第八章 報表功能：下載美化版「數位學習研習標籤統計分析報告」(Word .docx)
    內含全校通過率公式計算結果、深藍色行政風表格與策進建議。
    """
    try:
        # 生成分析報告 Word 檔
        file_path = ReportService.export_tag_analysis_report(current_app.config['REPORT_FOLDER'])
        
        return send_file(
            file_path,
            as_attachment=True,
            download_name='數位學習研習標籤統計分析報告.docx',
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
    except Exception as e:
        return jsonify({"error": f"產出統計分析報告失敗: {str(e)}"}), 500
        
@report_bp.route('/api/reports/pending_teachers/<string:tag_name>', methods=['GET'])
def get_pending_teachers(tag_name):
    """
    行政優化 API：根據指定的政策指標標籤，撈出全校尚未通過（時數為 0 或無紀錄）的教師名單
    """
    from models import Teacher, TrainingRecord, Training
    from services.tag_service import TagService
    
    try:
        tag_name = tag_name.strip().upper()
        all_teachers = Teacher.query.order_by(Teacher.id).all()
        pending_list = []
        
        for teacher in all_teachers:
            # 撈取該教師針對此標籤是否已有大於 0 的時數紀錄
            is_passed = False
            for record in teacher.records:
                # 解析課程名稱所屬標籤
                course_tags = TagService.parse_training_name(record.training.title)
                if tag_name in course_tags and record.hours > 0:
                    is_passed = True
                    break
            
            # 如果遍歷完發現沒有通過紀錄，就列入尚待補修名單
            if not is_passed:
                pending_list.append({
                    "name": teacher.name,
                    "position": teacher.position,
                    "teacher_code": teacher.teacher_code or "—"
                })
                
        return jsonify({"tag": tag_name, "pending_teachers": pending_list}), 200
    except Exception as e:
        return jsonify({"error": f"無法撈取名單: {str(e)}"}), 500
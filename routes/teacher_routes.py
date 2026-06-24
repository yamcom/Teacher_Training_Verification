# routes/teacher_routes.py
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, current_app
from models import db, Teacher
from services.import_service import ImportService
import os

# 建立教師管理專屬的藍圖
teacher_bp = Blueprint('teacher', __name__)

@teacher_bp.route('/teachers', methods=['GET'])
def list_teachers():
    """
    3.1 教師資料管理主頁
    顯示全校教師基本資料與職位排序，支援依姓名或職位搜尋。
    """
    search_name = request.args.get('name', '').strip()
    search_position = request.args.get('position', '').strip()
    
    query = Teacher.query
    
    if search_name:
        query = query.filter(Teacher.name.like(f"%{search_name}%"))
    if search_position:
        query = query.filter(Teacher.position.like(f"%{search_position}%"))
        
    # 依系統建立或排序流水號排序（維持附件 2 原始行政順序之基礎）
    teachers = query.order_by(Teacher.id).all()
    return render_template('teachers.html', teachers=teachers, search_name=search_name, search_position=search_position)


@teacher_bp.route('/teacher/add', methods=['POST'])
def add_teacher():
    """手動新增單筆教師資料"""
    try:
        position = request.form.get('position', '').strip()
        name = request.form.get('name', '').strip()
        teacher_code = request.form.get('teacher_code', '').strip()
        
        if not name or not position:
            return jsonify({"error": "姓名與行政職位為必填欄位"}), 400
            
        # 檢查是否重複建立
        existing = Teacher.query.filter_by(name=name, position=position).first()
        if existing:
            return jsonify({"error": "該職位的教師姓名已存在系統中"}), 400
            
        new_teacher = Teacher(
            position=position,
            name=name,
            teacher_code=teacher_code if teacher_code else None
        )
        db.session.add(new_teacher)
        db.session.commit()
        return jsonify({"message": f"成功新增教師：{name}"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"手動新增失敗: {str(e)}"}), 500


@teacher_bp.route('/teacher/edit/<int:id>', methods=['POST'])
def edit_teacher(id):
    """修改教師基本資料"""
    try:
        # 修正：將 get_or_400 改為標準的 get_or_404
        teacher = Teacher.query.get_or_404(id)
        teacher.position = request.form.get('position', '').strip()
        teacher.name = request.form.get('name', '').strip()
        teacher.teacher_code = request.form.get('teacher_code', '').strip()
        
        if not teacher.name or not teacher.position:
            return jsonify({"error": "姓名與行政職位不可為空"}), 400
            
        db.session.commit()
        return jsonify({"message": f"教師 {teacher.name} 資料已成功更新"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"修改資料失敗: {str(e)}"}), 500


@teacher_bp.route('/teacher/delete/<int:id>', methods=['POST'])
def delete_teacher(id):
    """刪除教師基本資料與其關聯之研習紀錄"""
    try:
        # 修正：將 get_or_400 改為標準的 get_or_404
        teacher = Teacher.query.get_or_404(id)
        
        # 為了維持資料庫完整性，手動清除該教師的所有研習紀錄關係
        for record in teacher.records:
            db.session.delete(record)
            
        db.session.delete(teacher)
        db.session.commit()
        return jsonify({"message": f"教師 {teacher.name} 及其研習紀錄已成功從系統移除"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"刪除教師失敗: {str(e)}"}), 500


@teacher_bp.route('/import/teachers', methods=['POST'])
def import_teacher_roster():
    """
    3.1 批量匯入教師名冊 (樣板對照基礎)
    """
    if 'file' not in request.files:
        return jsonify({"error": "未提供檔案"}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "檔案名稱為空"}), 400
        
    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], f"roster_{file.filename}")
    file.save(file_path)
    
    try:
        teacher_list = ImportService.parse_teacher_roster(file_path)
        
        success_count = 0
        for t_data in teacher_list:
            existing = Teacher.query.filter_by(name=t_data['name'], position=t_data['position']).first()
            if not existing:
                teacher = Teacher(
                    position=t_data['position'],
                    name=t_data['name'],
                    teacher_code=t_data['teacher_code']
                )
                db.session.add(teacher)
                success_count += 1
                
        db.session.commit()
        return jsonify({"message": f"教師名冊批量匯入成功！共新增 {success_count} 位教師。"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"批量匯入教師名冊失敗: {str(e)}"}), 500
# routes/teacher_routes.py
"""
教師研習檢核與統計管理系統 (TTVS) V2 - 3.1 教師基本名冊管理路由模組
相容 teachers.html 樣板與 AJAX 操作 API
"""
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required
from models import db, Teacher

teacher_bp = Blueprint('teacher', __name__, url_prefix='/teachers')


@teacher_bp.route('/', methods=['GET'])
def list_teachers():
    """3.1 教師基本名冊清單頁面"""
    search_name = request.args.get('name', '').strip()
    search_position = request.args.get('position', '').strip()

    query = Teacher.query

    if search_name:
        query = query.filter(Teacher.name.like(f'%{search_name}%'))
    if search_position:
        query = query.filter(Teacher.position.like(f'%{search_position}%'))

    teachers = query.order_by(Teacher.id.asc()).all()

    # 修正重點：將原本的 teacher_list.html 改為正確的 teachers.html
    return render_template(
        'teachers.html',
        teachers=teachers,
        search_name=search_name,
        search_position=search_position
    )


@teacher_bp.route('/add', methods=['POST'])
@login_required
def add_teacher():
    """手動新增單筆教師 (支援 Form / AJAX)"""
    position = request.form.get('position', '').strip()
    name = request.form.get('name', '').strip()
    teacher_code = request.form.get('teacher_code', '').strip()

    if not position or not name:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'json' in request.headers.get('Accept', ''):
            return jsonify({'error': '職稱與姓名為必填欄位！'}), 400
        flash('職稱與姓名為必填欄位！', 'warning')
        return redirect(url_for('teacher.list_teachers'))

    clean_name = " ".join(name.replace(' ', ' ').split())
    new_teacher = Teacher(position=position, name=clean_name, teacher_code=teacher_code if teacher_code else None)
    
    try:
        db.session.add(new_teacher)
        db.session.commit()
        
        # 配合 teachers.html AJAX 呼叫
        return jsonify({'message': f'成功建立教師：{clean_name}'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'新增失敗: {str(e)}'}), 500


@teacher_bp.route('/edit/<int:teacher_id>', methods=['POST'])
@login_required
def edit_teacher(teacher_id):
    """修改單筆教師資料 (配合 teachers.html openEditModal 呼叫)"""
    teacher = Teacher.query.get_or_404(teacher_id)
    position = request.form.get('position', '').strip()
    name = request.form.get('name', '').strip()
    teacher_code = request.form.get('teacher_code', '').strip()

    if not position or not name:
        return jsonify({'error': '職稱與姓名不可空白！'}), 400

    try:
        teacher.position = position
        teacher.name = " ".join(name.replace(' ', ' ').split())
        teacher.teacher_code = teacher_code if teacher_code else None
        db.session.commit()
        
        return jsonify({'message': f'成功更新教師：{teacher.name}'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'修改失敗: {str(e)}'}), 500


@teacher_bp.route('/delete/<int:teacher_id>', methods=['POST'])
@login_required
def delete_teacher(teacher_id):
    """刪除指定教師 (配合 teachers.html deleteTeacher 呼叫)"""
    teacher = Teacher.query.get_or_404(teacher_id)
    try:
        name = teacher.name
        db.session.delete(teacher)
        db.session.commit()
        return jsonify({'message': f'已刪除教師：{name}'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'刪除失敗: {str(e)}'}), 500
# routes/auth_routes.py
"""
教師研習檢核與統計管理系統 (TTVS) V2 - 承辦人身份驗證與帳號權限管理模組
包含：登入/登出、個人修改密碼、管理員新增/刪除帳號與密碼重置 API
"""
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from models import db, User

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


# =========================================================================
# 🔐 1. 登入與登出機制
# =========================================================================
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """承辦人/管理員登入頁面"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            if not user.is_active:
                flash('此帳號已被停用，請聯繫系統管理員！', 'danger')
                return redirect(url_for('auth.login'))

            login_user(user)
            user.last_login = datetime.now()
            db.session.commit()
            
            flash(f'歡迎回來，{user.real_name} ({user.department or "處室承辦人"})！', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard'))
        else:
            flash('帳號或密碼輸入錯誤，請重新確認！', 'danger')

    return render_template('login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    """登出目前帳號"""
    logout_user()
    flash('您已成功安全登出系統。', 'info')
    return redirect(url_for('dashboard'))


# =========================================================================
# 👤 2. 個人修改密碼 (所有人皆可操作)
# =========================================================================
@auth_bp.route('/change-password', methods=['POST'])
@login_required
def change_password():
    """使用者修改自己目前的密碼"""
    old_password = request.form.get('old_password', '').strip()
    new_password = request.form.get('new_password', '').strip()
    confirm_password = request.form.get('confirm_password', '').strip()

    if not current_user.check_password(old_password):
        flash('舊密碼輸入不正確，請重新嘗試！', 'danger')
        return redirect(request.referrer or url_for('dashboard'))

    if new_password != confirm_password:
        flash('兩次輸入的新密碼不一致！', 'warning')
        return redirect(request.referrer or url_for('dashboard'))

    if len(new_password) < 6:
        flash('為確保安全性，新密碼長度至少需為 6 個字元！', 'warning')
        return redirect(request.referrer or url_for('dashboard'))

    current_user.set_password(new_password)
    db.session.commit()
    flash('密碼已成功修改！下次登入請使用新密碼。', 'success')
    return redirect(request.referrer or url_for('dashboard'))


# =========================================================================
# 👑 3. 管理員專屬：帳號與權限管理主頁面
# =========================================================================
@auth_bp.route('/users', methods=['GET'])
@login_required
def user_management():
    """帳號清單與權限管理列表 (僅 Admin 可存取)"""
    if current_user.role != 'admin':
        flash('權限不足！只有系統管理員才能存取帳號管理頁面。', 'danger')
        return redirect(url_for('dashboard'))

    users = User.query.order_by(User.id.asc()).all()
    return render_template('user_management.html', users=users)


@auth_bp.route('/users/add', methods=['POST'])
@login_required
def add_user():
    """管理員手動新增管理員/處室承辦人帳號"""
    if current_user.role != 'admin':
        flash('權限不足！', 'danger')
        return redirect(url_for('dashboard'))

    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()
    real_name = request.form.get('real_name', '').strip()
    role = request.form.get('role', 'reviewer').strip()
    department = request.form.get('department', '').strip()

    if not username or not password or not real_name:
        flash('帳號、密碼與使用者真實姓名為必填欄位！', 'warning')
        return redirect(url_for('auth.user_management'))

    # 檢查帳號是否重複
    existing = User.query.filter_by(username=username).first()
    if existing:
        flash(f'帳號「{username}」已存在，請使用其他帳號名稱！', 'info')
        return redirect(url_for('auth.user_management'))

    new_user = User(
        username=username,
        real_name=real_name,
        role=role,
        department=department if department else None
    )
    new_user.set_password(password)

    db.session.add(new_user)
    db.session.commit()

    flash(f'成功新增帳號：{username} ({real_name})！', 'success')
    return redirect(url_for('auth.user_management'))


@auth_bp.route('/users/reset-password/<int:user_id>', methods=['POST'])
@login_required
def admin_reset_password(user_id):
    """管理員重置指定使用者的密碼"""
    if current_user.role != 'admin':
        flash('權限不足！', 'danger')
        return redirect(url_for('dashboard'))

    target_user = User.query.get_or_404(user_id)
    new_password = request.form.get('new_password', '').strip()

    if not new_password or len(new_password) < 6:
        flash('重置的密碼長度至少需為 6 個字元！', 'warning')
        return redirect(url_for('auth.user_management'))

    target_user.set_password(new_password)
    db.session.commit()

    flash(f'已成功重置帳號「{target_user.username}」的密碼！', 'success')
    return redirect(url_for('auth.user_management'))


@auth_bp.route('/users/delete/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    """管理員刪除指定的帳號"""
    if current_user.role != 'admin':
        flash('權限不足！', 'danger')
        return redirect(url_for('dashboard'))

    # 安全防禦 1：禁止刪除自己目前的登入帳號
    if target_user_id := user_id == current_user.id:
        flash('安全防禦：您無法刪除目前正在使用的管理員帳號！', 'danger')
        return redirect(url_for('auth.user_management'))

    target_user = User.query.get_or_404(user_id)
    username = target_user.username

    # 安全防禦 2：若全站只剩最後一個 Admin，禁止刪除
    admin_count = User.query.filter_by(role='admin').count()
    if target_user.role == 'admin' and admin_count <= 1:
        flash('安全防禦：系統必須保留至少一位管理員 (Admin) 帳號，無法刪除！', 'warning')
        return redirect(url_for('auth.user_management'))

    try:
        db.session.delete(target_user)
        db.session.commit()
        flash(f'已成功刪除帳號「{username}」！', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'刪除帳號時發生錯誤: {e}', 'danger')

    return redirect(url_for('auth.user_management'))
# routes/tag_routes.py
from flask import Blueprint, render_template, request, jsonify
from services.tag_service import TagService

tag_bp = Blueprint('tag_admin', __name__)

@tag_bp.route('/tags/settings', methods=['GET'])
def tag_settings_page():
    """顯示關鍵字指標自訂管理頁面"""
    # 確保規則已載入
    if not TagService.TAG_RULES:
        TagService.init_rules()
        
    return render_template('tag_settings.html', tag_rules=TagService.TAG_RULES)

@tag_bp.route('/api/tags/save', methods=['POST'])
def save_tag_rule():
    """API：儲存或更新自訂關鍵字規則"""
    try:
        tag_name = request.form.get('tag_name', '').strip().upper()
        # 接收多個關鍵字/正則表達式
        patterns = request.form.getlist('patterns[]')
        
        if not tag_name or not patterns:
            return jsonify({"error": "指標名稱與關鍵字不可為空"}), 400
            
        success = TagService.register_or_update_tag(tag_name, patterns)
        if success:
            return jsonify({"message": f"指標【{tag_name}】關鍵字設定儲存成功！"}), 200
        return jsonify({"error": "儲存失敗"}), 500
    except Exception as e:
        return jsonify({"error": f"系統異常: {str(e)}"}), 500

@tag_bp.route('/api/tags/delete/<string:tag_name>', methods=['POST'])
def delete_tag_rule(tag_name):
    """API：刪除特定指標規則"""
    try:
        TagService.delete_tag_rule(tag_name)
        return jsonify({"message": f"指標【{tag_name}】已成功移除！"}), 200
    except Exception as e:
        return jsonify({"error": f"刪除失敗: {str(e)}"}), 500
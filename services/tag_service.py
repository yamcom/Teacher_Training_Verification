# services/tag_service.py
import re
import json
import os

class TagService:
    # 預設行政順序
    PRESET_TAGS = ['A1', 'A2', 'A3', 'B1', 'B5-1', 'B5-2', 'C', 'D', 'E']
    
    # 預設規則庫
    DEFAULT_RULES = {
        'A1': [r'A1', r'數位學習工作坊[（(]一[）)]', r'數位學習工作坊.*一'],
        'A2': [r'A2', r'數位學習工作坊[（(]二[）)]', r'數位學習工作坊.*二'],
        'A3': [r'A3', r'數位素養進階'],
        'B1': [r'B1', r'智慧學習課堂', r'課堂教學應用'],
        'B5-1': [r'B5-1', r'生成式AI.*教育應用', r'生成式AI與教育應用'],
        'B5-2': [r'B5-2', r'生成式AI融入', r'AI融入學科'],
        'C': [r'C[  ]', r'[^a-zA-Z0-9]C$', r'跨領域前瞻', r'數位增能指標'],
        'D': [r'D[  ]', r'[^a-zA-Z0-9]D$'],
        'E': [r'E[  ]', r'[^a-zA-Z0-9]E$']
    }
    
    TAG_RULES = {}

    @classmethod
    def init_rules(cls, config_folder='instance'):
        """初始化規則：嘗試從本地 JSON 讀取自訂規則，若無則載入預設值"""
        os.makedirs(config_folder, exist_ok=True)
        cls.config_path = os.path.join(config_folder, 'dynamic_tag_rules.json')
        
        if os.path.exists(cls.config_path):
            try:
                with open(cls.config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    cls.TAG_RULES = data.get('rules', cls.DEFAULT_RULES.copy())
                    cls.PRESET_TAGS = data.get('order', cls.PRESET_TAGS.copy())
                    return
            except:
                pass
        
        cls.TAG_RULES = cls.DEFAULT_RULES.copy()
        cls.save_rules()

    @classmethod
    def save_rules(cls):
        """將動態規則持久化儲存至 JSON 檔案中"""
        if hasattr(cls, 'config_path'):
            with open(cls.config_path, 'w', encoding='utf-8') as f:
                json.dump({'rules': cls.TAG_RULES, 'order': cls.PRESET_TAGS}, f, ensure_ascii=False, indent=4)

    @classmethod
    def parse_training_name(cls, training_title: str) -> list:
        if not cls.TAG_RULES:
            cls.init_rules()
            
        if not training_title:
            return []
            
        matched_tags = []
        for tag, patterns in cls.TAG_RULES.items():
            for pattern in patterns:
                if re.search(pattern, training_title, re.IGNORECASE):
                    matched_tags.append(tag)
                    break
                    
        matched_tags.sort(key=lambda x: cls.PRESET_TAGS.index(x) if x in cls.PRESET_TAGS else 99)
        return matched_tags

    @classmethod
    def register_or_update_tag(cls, tag_name: str, regex_patterns: list):
        """新增或更新標籤與關鍵字正則"""
        tag_name = tag_name.strip().upper()
        if not tag_name:
            return False
            
        if tag_name not in cls.PRESET_TAGS:
            cls.PRESET_TAGS.append(tag_name)
            
        cls.TAG_RULES[tag_name] = [p.strip() for p in regex_patterns if p.strip()]
        cls.save_rules()
        return True

    @classmethod
    def delete_tag_rule(cls, tag_name: str):
        """刪除特定指標標籤規則"""
        tag_name = tag_name.strip().upper()
        if tag_name in cls.TAG_RULES:
            del cls.TAG_RULES[tag_name]
        if tag_name in cls.PRESET_TAGS:
            cls.PRESET_TAGS.remove(tag_name)
        cls.save_rules()
        return True
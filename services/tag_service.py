# services/tag_service.py
"""
教育部與各處室政策研習指標關鍵字、日期區間與核算時數檢核服務
支援：
1. 關鍵字標籤比對
2. 「研習過即可」選項自動將日期涵蓋範圍設為 1900-01-01 至 [當前系統日期]
3. 認證時數必須 > 0 才計入採認人數
4. 指標架構：
- 教務處 (AA) : 數位學習基礎、數位學習進階、數位學習講師、資訊安全
- 輔導室 (SP) : 特殊教育、生命教育、輔導知能、學生輔導、家庭教育 (SP+流水號)
- 學務處 (SA) : 安全教育、交通安全、防災、性平教育、性別平等、環境教育 (SA+流水號)
- 總務處 (GA) : 採購法、總務知能 (GA+流水號)

修正重點：
1. 比對機制改為 any(...)：研習標題只要包含關鍵字串或匹配 Regex 即可通過採認
2. 提供 get_display_name(tag) 方法，呈現 pattern 列表中第二個元素名稱 (Index 1)
"""
import json
import os
import re
from datetime import datetime, date

class TagService:
    PRESET_TAGS = [
        # 教務處 (AA)
        'A1', 'A2', 'A3', 'B3', 'B5-1', 'B1', 'B2', 'B4', 'B5-2', 
        'C', 'D', 'E', 'F1', 'F2', 'AA01',
        # 輔導室 (SP)
        'SP1', 'SP2', 'SP3', 'SP4', 'SP5', 'SP6',
        # 學務處 (SA)
        'SA1', 'SA2', 'SA3', 'SA4', 'SA5', 'SA6',
        # 總務處 (GA)
        'GA1', 'GA2'
    ]

    DEPARTMENT_GROUPS = {
        '教務處': ['A1', 'A2', 'A3', 'B3', 'B5-1', 'B1', 'B2', 'B4', 'B5-2', 'C', 'D', 'E', 'F1', 'F2', 'AA01'],
        '輔導室': ['SP1', 'SP2', 'SP3', 'SP4', 'SP5', 'SP6'],
        '學務處': ['SA1', 'SA2', 'SA3', 'SA4', 'SA5', 'SA6'],
        '總務處': ['GA1', 'GA2']
    }

    _rules = {}

    @classmethod
    def init_rules(cls, rules_path):
        if os.path.exists(rules_path):
            try:
                with open(rules_path, 'r', encoding='utf-8') as f:
                    cls._rules = json.load(f)
            except Exception as e:
                print(f"⚠️ 載入標籤規則 JSON 失敗: {e}")
                cls._rules = cls._get_default_rules()
        else:
            cls._rules = cls._get_default_rules()

    @classmethod
    def get_rules(cls):
        if not cls._rules:
            cls._rules = cls._get_default_rules()
        return cls._rules

    @classmethod
    def get_display_name(cls, tag):
        """
        取得指標名稱呈現：優先以 pattern 列表中的第二個元素 (Index 1) 作為顯示名稱
        若列表長度不足 2，則降級回傳第一個元素或指標代碼本身
        """
        rules = cls.get_rules()
        config = rules.get(tag)
        if not config:
            return tag

        keywords = config.get('keywords', []) if isinstance(config, dict) else config
        if isinstance(keywords, list) and len(keywords) > 0:
            if len(keywords) >= 2 and keywords[1]:
                return str(keywords[1]).strip()
            return str(keywords[0]).strip()
        
        return tag

    @classmethod
    def update_rules(cls, new_rules, rules_path):
        try:
            current_today = date.today().strftime('%Y-%m-%d')
            normalized_rules = {}

            for tag, config in new_rules.items():
                if isinstance(config, list):
                    normalized_rules[tag] = {
                        'keywords': config,
                        'is_ever_trained': True,
                        'start_date': '1900-01-01',
                        'end_date': current_today
                    }
                elif isinstance(config, dict):
                    kw_list = config.get('keywords', [])
                    if isinstance(kw_list, str):
                        kw_list = [kw_list]
                    
                    normalized_rules[tag] = {
                        'keywords': kw_list,
                        'is_ever_trained': config.get('is_ever_trained', True),
                        'start_date': config.get('start_date', '1900-01-01'),
                        'end_date': config.get('end_date', current_today)
                    }

            cls._rules = normalized_rules
            os.makedirs(os.path.dirname(rules_path), exist_ok=True)
            with open(rules_path, 'w', encoding='utf-8') as f:
                json.dump(cls._rules, f, ensure_ascii=False, indent=2)

            return True
        except Exception as e:
            print(f"❌ 寫入規則設定檔失敗: {e}")
            return False

    @classmethod
    def _get_default_rules(cls):
        current_today = date.today().strftime('%Y-%m-%d')
        rules = {}

        aa_base = [
            ('A1', ['A1數位學習工作坊', 'A1', '數位學習工作坊[（(]一[）)]']),
            ('A2', ['A2數位學習工作坊', 'A2', '數位學習工作坊[（(]二[）)]', '因材網']),
            ('A3', ['A3數位素養', 'A3', '數位素養增能']),
            ('B3', ['B3數位教學指引', 'B3']),
            ('B5-1', ['B5-1生成式', 'B5-1']),
        ]
        aa_advanced = [
            ('B1', ['B1科技輔助自主學習', 'B1']),
            ('B2', ['B2', 'B2 PBL']),
            ('B4', ['B4', '各學科工作坊']),
            ('B5-2', ['B5-2生成式', 'B5-2']),
        ]
        aa_lecturer = [
            ('C', ['數位學習講師.*C', '講師.*C']),
            ('D', ['數位學習講師.*D', '講師.*D']),
            ('E', ['數位學習講師.*E', '講師.*E']),
            ('F1', ['數位學習講師.*F1', '講師.*F1']),
            ('F2', ['數位學習講師.*F2', '講師.*F2']),
        ]
        aa_sec = [('AA01', ['資訊安全', '資安通識', '資通安全'])]

        sp_items = [
            ('SP1', ['特殊教育', '特殊教育']),
            ('SP2', ['特教知能', '特教知能', '身心障礙']),
            ('SP3', ['生命教育', '生命教育']),
            ('SP4', ['輔導知能', '輔導知能']),
            ('SP5', ['學生輔導', '學生輔導', '霸凌']),
            ('SP6', ['家庭教育', '家庭教育']),
        ]
        sa_items = [
            ('SA1', ['安全教育', '校園安全']),
            ('SA2', ['交通安全', '交通安全']),
            ('SA3', ['防災', '防災']),
            ('SA4', ['性平教育', '兒童權利公約']),
            ('SA5', ['性別平等', '性別平等']),
            ('SA6', ['環境教育', '環境教育']),
        ]
        ga_items = [
            ('GA1', ['採購法', '採購法']),
            ('GA2', ['總務知能', '總務知能'])
        ]

        for tag, kws in aa_base + aa_advanced + aa_lecturer + aa_sec + sp_items + sa_items + ga_items:
            rules[tag] = {
                'keywords': kws,
                'is_ever_trained': True,
                'start_date': '1900-01-01',
                'end_date': current_today
            }

        return rules

    @classmethod
    def parse_training_name(cls, title, course_date_str=None, hours=0.0):
        matched_tags = []
        if not title:
            return matched_tags

        try:
            h_val = float(hours)
            if h_val <= 0:
                return matched_tags
        except (ValueError, TypeError):
            return matched_tags

        title_clean = str(title).strip()
        rules = cls.get_rules()

        c_date = date.today()
        if course_date_str:
            try:
                clean_d_str = str(course_date_str).strip().replace('/', '-').split(' ')[0]
                c_date = datetime.strptime(clean_d_str, '%Y-%m-%d').date()
            except Exception:
                c_date = date.today()

        current_today_str = date.today().strftime('%Y-%m-%d')

        for tag_key, config in rules.items():
            if isinstance(config, dict):
                keywords = config.get('keywords', [])
                is_ever_trained = config.get('is_ever_trained', True)
                s_date_str_raw = config.get('start_date', '1900-01-01')
                e_date_str_raw = config.get('end_date', current_today_str)
            elif isinstance(config, list):
                keywords = config
                is_ever_trained = True
                s_date_str_raw = '1900-01-01'
                e_date_str_raw = current_today_str
            else:
                continue

            if not keywords:
                continue

            is_keyword_matched = False
            for kw in keywords:
                if not kw:
                    continue
                try:
                    if re.search(kw, title_clean, re.IGNORECASE):
                        is_keyword_matched = True
                        break
                except Exception:
                    if kw.lower() in title_clean.lower():
                        is_keyword_matched = True
                        break

            if is_keyword_matched:
                if is_ever_trained:
                    s_date_str = "1900-01-01"
                    e_date_str = current_today_str
                else:
                    s_date_str = str(s_date_str_raw).strip() if s_date_str_raw else "1900-01-01"
                    e_date_str = str(e_date_str_raw).strip() if e_date_str_raw else current_today_str

                try:
                    s_date = datetime.strptime(s_date_str, '%Y-%m-%d').date()
                except Exception:
                    s_date = date(1900, 1, 1)

                try:
                    e_date = datetime.strptime(e_date_str, '%Y-%m-%d').date()
                except Exception:
                    e_date = date.today()

                if s_date <= c_date <= e_date:
                    matched_tags.append(tag_key)

        return matched_tags
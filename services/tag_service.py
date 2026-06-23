# services/tag_service.py
import re

class TagService:
    # 規劃書預設支援的 A1 ~ E 系列子標籤 
    PRESET_TAGS = ['A1', 'A2', 'A3', 'B1', 'B2', 'B3', 'B4', 'B5-1', 'B5-2', 'C', 'D', 'E']
    
    @classmethod
    def parse_training_name(cls, name: str) -> list:
        """
        自動解析研習名稱中的標籤資訊 [cite: 52]。
        認定標準：
        1. 研習名稱必須含有「精進數位」或「數位學習工作坊」關鍵字。
        2. 若符合上述條件，則尋找並提取屬於 ['A1'...'E'] 系列的哪一種 。
        """
        if not name:
            return []
            
        found_tags = []
        
        # 1. 核心條件檢查：判定是否含有「精進數位」或「數位學習工作坊」
        if "精進數位" in name or "數位學習工作坊" in name:
            
            # 2. 若符合核心條件，則巡檢是否包含 A1~E 系列的子標籤 
            for tag in cls.PRESET_TAGS:
                # 使用正規表示式進行精準比對 (使用 re.escape 確保如 B5-1 的連字號能被正確處理)
                pattern = re.compile(rf'{re.escape(tag)}', re.IGNORECASE)
                if pattern.search(name):
                    found_tags.append(tag)
                    
        return found_tags
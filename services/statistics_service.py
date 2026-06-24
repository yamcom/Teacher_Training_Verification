# services/statistics_service.py
import pandas as pd
from models import Teacher

class StatisticsService:
    @classmethod
    def generate_all_school_report(cls) -> pd.DataFrame:
        """
        3.6 & 3.7 節：產生全校研習統計基礎報表，格式符合：序號, 職位, 姓名, 通過研習
        """
        from services.tag_service import TagService
        
        # 修正：將原本誤植的 order_on 改為標準的 order_by
        teachers = Teacher.query.order_by(Teacher.id).all()
        report_data = []
        
        for idx, teacher in enumerate(teachers, 1):
            passed_tags = []
            # 撈取該教師所有「實核時數 > 0 (通過)」的研習紀錄
            records = [r for r in teacher.records if r.hours > 0]
            
            for r in records:
                # 智慧解析研習名稱中是否含有 A1~E 政策指標標籤
                tags = TagService.parse_training_name(r.training.title)
                passed_tags.extend(tags)
            
            # 去除重複的標籤（例如聽了兩場 A1，僅採計一次）
            passed_tags = list(set(passed_tags))
            
            # 依據行政規劃書定義的 A1 -> E 順序進行精準排序
            passed_tags.sort(key=lambda x: TagService.PRESET_TAGS.index(x) if x in TagService.PRESET_TAGS else 99)
            
            # 以「.`」符號串接標籤 (例如: A1.B5-1)
            passed_str = ".".join(passed_tags)
            
            report_data.append({
                "序號": idx,
                "職位": teacher.position,
                "姓名": teacher.name,
                "通過研習": passed_str
            })
            
        return pd.DataFrame(report_data)
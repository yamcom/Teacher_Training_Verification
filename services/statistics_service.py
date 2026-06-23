# services/statistics_service.py
import pandas as pd
from models import Teacher, TrainingRecord, Training

class StatisticsService:
    @classmethod
    def generate_all_school_report(cls) -> pd.DataFrame:
        """
        產生全校研習統計報表，格式符合：序號, 職位, 姓名, 通過研習
        """
        from services.tag_service import TagService
        
        # 取得所有教師，依原始行政排序 (或資料庫建立順序)
        teachers = Teacher.query.order_on(Teacher.id).all()
        
        report_data = []
        
        for idx, teacher in enumerate(teachers, 1):
            passed_tags = []
            
            # 撈取該教師所有「通過(時數>0)」的紀錄
            records = [r for r in teacher.records if r.hours > 0]
            
            for r in records:
                # 解析該研習名稱對應的標籤
                tags = TagService.parse_training_name(r.training.title)
                passed_tags.extend(tags)
            
            # 去除重複標籤並依預設 A1->E 順序排序
            passed_tags = list(set(passed_tags))
            passed_tags.sort(key=lambda x: TagService.PRESET_TAGS.index(x) if x in TagService.PRESET_TAGS else 99)
            
            # 依顯示規則以「.」串接，例如：A1.B1.B5-1
            passed_str = ".".join(passed_tags)
            
            report_data.append({
                "序號": idx,
                "職位": teacher.position,
                "姓名": teacher.name,
                "通過研習": passed_str
            })
            
        return pd.DataFrame(report_data)
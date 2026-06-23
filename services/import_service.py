# services/import_service.py
import os
import pandas as pd
from docx import Document

class ImportService:
    """研習資料與教師名冊匯入服務，負責檔案解析與資料清洗"""

    @classmethod
    def parse_training_file(cls, file_path: str) -> list:
        """
        根據檔案副檔名自動辨識並解析教師研習紀錄。
        支援格式：.csv, .xlsx, .xls, .docx
        回傳：標準化的字典列表 (List of Dict)，包含教師姓名、課程代碼、研習名稱等欄位。
        """
        ext = os.path.splitext(file_path)[1].lower()
        
        if ext == '.csv':
            return cls._parse_csv(file_path)
        elif ext in ['.xlsx', '.xls']:
            return cls._parse_excel(file_path)
        elif ext == '.docx':
            return cls._parse_docx(file_path)
        else:
            raise ValueError(f"不支援的檔案格式: {ext}")

    @classmethod
    def _parse_csv(cls, file_path: str) -> list:
        """解析 CSV 檔案並標準化欄位"""
        try:
            # 優先嘗試 utf-8-sig 以處理 Excel 匯出的 CSV，若失敗則嘗試 cp950 (大五碼)
            try:
                df = pd.read_csv(file_path, encoding='utf-8-sig')
            except UnicodeDecodeError:
                df = pd.read_csv(file_path, encoding='cp950')
                
            return cls._clean_training_dataframe(df)
        except Exception as e:
            raise RuntimeError(f"CSV 解析失敗: {str(e)}")

    @classmethod
    def _parse_excel(cls, file_path: str) -> list:
        """解析 Excel (.xlsx, .xls) 檔案並標準化欄位"""
        try:
            # 預設讀取第一個工作表 (Sheet)
            df = pd.read_excel(file_path, engine='openpyxl' if file_path.endswith('.xlsx') else None)
            return cls._clean_training_dataframe(df)
        except Exception as e:
            raise RuntimeError(f"Excel 解析失敗: {str(e)}")

    @classmethod
    def _parse_docx(cls, file_path: str) -> list:
        """
        解析 Word (.docx) 檔案中的表格。
        假設研習紀錄以表格形式存在，且第一列為標題列。
        """
        try:
            doc = Document(file_path)
            all_records = []
            
            # 遍歷 Word 文件中的所有表格
            for table in doc.tables:
                if len(table.rows) <= 1:
                    continue
                
                # 提取標題列
                headers = [cell.text.strip() for cell in table.rows[0].cells]
                
                # 逐列提取資料
                for row in table.rows[1:]:
                    row_data = {}
                    for i, cell in enumerate(row.cells):
                        if i < len(headers):
                            row_data[headers[i]] = cell.text.strip()
                    all_records.append(row_data)
            
            # 將 Word 表格資料轉為 DataFrame 進行統一清洗
            df = pd.DataFrame(all_records)
            return cls._clean_training_dataframe(df)
        except Exception as e:
            raise RuntimeError(f"Word (.docx) 表格解析失敗: {str(e)}")

    @classmethod
    def _clean_training_dataframe(cls, df: pd.DataFrame) -> list:
        """
        資料清洗與對照核心邏輯。
        將外部不同的對照欄位名稱（如附件1的名稱）對齊為系統標準欄位。
        """
        if df.empty:
            return []

        # 去除所有欄位名稱的前後空白
        df.columns = df.columns.str.strip()

        # 欄位映射對照表 (左邊為系統標準欄位，右邊為可能出現的外部欄位名稱)
        mapping = {
            'teacher_name': ['教師姓名', '姓名', '教師'],
            'course_code': ['課程代碼', '課程代號', '研習代碼', '研習代號'],
            'title': ['研習課程名稱', '研習名稱', '課程名稱', '研習主題'],
            'organizer': ['主辦單位', '承辦單位', '辦理單位'],
            'course_date': ['課程結束時間', '課程日期', '研習日期', '辦理日期'],
            'hours': ['實核時數/學分數', '實核時數', '核給時數', '時數']
        }

        cleaned_data = []

        for _, row in df.iterrows():
            record = {}
            
            # 根據對照表動態抓取欄位值
            for std_key, alias_list in mapping.items():
                value = None
                for alias in alias_list:
                    if alias in df.columns:
                        value = row[alias]
                        break
                record[std_key] = value

            # 資料基本清洗與防呆
            if not record['teacher_name'] or pd.isna(record['teacher_name']):
                continue  # 沒有教師姓名則視為無效列
                
            record['teacher_name'] = str(record['teacher_name']).strip()
            record['course_code'] = str(record['course_code']).split('.')[0].strip() if not pd.isna(record['course_code']) else ''
            record['title'] = str(record['title']).strip() if not pd.isna(record['title']) else ''
            record['organizer'] = str(record['organizer']).strip() if not pd.isna(record['organizer']) else ''
            record['course_date'] = str(record['course_date']).strip() if not pd.isna(record['course_date']) else ''
            
            # 時數轉換與防呆 (確保為浮點數或 0.0)
            try:
                record['hours'] = float(record['hours']) if not pd.isna(record['hours']) else 0.0
            except (ValueError, TypeError):
                record['hours'] = 0.0

            cleaned_data.append(record)

        return cleaned_data

    @classmethod
    def parse_teacher_roster(cls, file_path: str) -> list:
        """
        3.1 節名冊功能：解析行政預設的「教師基本名冊」檔案 (支援 CSV/Excel)。
        欄位包含：職位、姓名、教師編號。
        """
        ext = os.path.splitext(file_path)[1].lower()
        if ext == '.csv':
            df = pd.read_csv(file_path, encoding='utf-8-sig')
        elif ext in ['.xlsx', '.xls']:
            df = pd.read_excel(file_path)
        else:
            raise ValueError("教師名冊僅支援 CSV 或 Excel 格式")

        df.columns = df.columns.str.strip()
        teacher_list = []

        for _, row in df.iterrows():
            name = row.get('姓名', row.get('教師姓名'))
            position = row.get('職位', row.get('職稱', '教師'))
            code = row.get('教師編號', row.get('員工編號', ''))

            if pd.isna(name) or not str(name).strip():
                continue

            teacher_list.append({
                'name': str(name).strip(),
                'position': str(position).strip(),
                'teacher_code': str(code).split('.')[0].strip() if not pd.isna(code) else ''
            })

        return teacher_list
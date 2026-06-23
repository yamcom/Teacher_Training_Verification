# 教師研習檢核與統計管理系統 (TTVS)
> **Teacher Training Verification System**

本系統是一套以 Python 3.12 + Flask + SQLite 為核心的教師研習管理與行政檢核系統。旨在協助學校行政人員高效匯入海量教師研習紀錄（如單次上萬筆的 CSV 檔案），自動過濾特定政策指標（如「精進數位學習」與「數位學習工作坊」），並依據預設名冊的原始行政順序，快速產出符合主管機關送件審查用的統計報表，預期可降低 80% 以上的人工整理工作量。

---

## 📌 核心功能
- **教師資料管理**：支援全校教師基本資料與行政職位排序的管理。
- **研習資料匯入**：支援大量研習 CSV/Excel 檔案非同步或批量匯入。
- **自動標籤檢核**：精準識別「精進數位」或「數位學習工作坊」相關課程，並自動歸類至 `A1`、`A2`、`A3`、`B1`~`B5-2`、`C`、`D`、`E` 等政策指標。
- **時數狀態判定**：依「課程代碼」辨識唯一課程，若實核時數大於 0 則判定為「通過」，時數為 0 則判定為「未通過」。
- **統計分析與報表**：自動計算各指標通過率，並可一鍵導出符合雙欄 Excel 樣板的 CSV 行政審查報表與正式公文明細。

---

## 🛠️ 技術架構
- **前端 (Frontend)**：HTML5 / CSS3 / Bootstrap 5 / JavaScript / Jinja2 樣板引擎
- **後端 (Backend)**：Python 3.12 / Flask 網頁微框架
- **資料庫 (Database)**：SQLite (搭配 SQLAlchemy ORM)
- **資料處理與報表**：Pandas (大數據高效清洗) / openpyxl / python-docx

---

## 📂 專案目錄結構

teacher_training_system/
│
├─ main.py                      # 系統主程式進入點與 Flask 路由（整合研習匯入、檢核、報表下載）
├─ config.py                    # 系統全域設定檔（資料庫路徑、上傳目錄、金鑰等）
├─ models.py                    # 資料庫模型定義（教師、研習課程、研習紀錄、標籤等資料表）
├─ database.db                  # SQLite 資料庫檔案（由系統自動生成）
├─ requirements.txt             # 專案套件相依清單（Flask, SQLAlchemy, Pandas, openpyxl 等）
│
├─ uploads/                     # 研習紀錄原始檔案（Excel/CSV）上傳暫存目錄
├─ exports/                     # 系統導出的 Excel/CSV 暫存目錄
├─ reports/                     # 產出的正式公文、Word、PDF 報表目錄
├─ backups/                     # 資料庫定期備份目錄
│
├─ services/                    # 核心業務邏輯處理層（Services）
│   ├─ import_service.py        # 處理 Excel / CSV / Word 資料解析與清洗
│   ├─ export_service.py        # 處理各式資料與統計表的匯出作業
│   ├─ statistics_service.py    # 負責計算全校人數、通過率與完成率之統計邏輯
│   ├─ tag_service.py           # 負責解析「精進數位」或「數位學習工作坊」與 A1~E 標籤
│   └─ report_service.py        # 負責將數據帶入 Word/PDF 樣板的報表生成服務
│
├─ routes/                      # 模組化路由控制層（Blueprints，供 main.py 引用）
│   ├─ teacher_routes.py        # 教師名冊增刪查改（CRUD）之網頁路由
│   ├─ training_routes.py       # 研習課程與查詢頁面之網頁路由
│   ├─ import_routes.py         # 處理檔案上傳與非同步檢核之網頁路由
│   └─ report_routes.py         # 統計分析圖表與報表下載之網頁路由
│
├─ templates/                   # 前端 Jinja2 網頁樣板（HTML）
│   ├─ base.html                # 全站通用導覽列與側邊欄基礎樣板
│   ├─ dashboard.html           # 系統首頁儀表板（顯示全校教師總數、完成率與統計圖表）
│   ├─ teachers.html            # 教師管理與名冊匯入/修改頁面
│   ├─ trainings.html           # 研習課程列表與個別教師查詢頁面
│   ├─ import.html              # 研習資料拖曳上傳與即時檢核狀態頁面
│   ├─ statistics.html          # 標籤通過人數、未通過人數與通過率分析頁面
│   └─ reports.html             # 全校研習統計表（雙欄格式）匯出與公文下載頁面
│
├─ static/                      # 前端靜態資源檔案
│   ├─ css/                     # 自訂樣式與 Bootstrap 5 樣式表
│   ├─ js/                      # 前端互動邏輯（如上傳進度條、圖表渲染）
│   └─ images/                  # 系統標誌與圖示資源
│
└─ migrations/                  # 資料庫版控目錄（選用）


🚀 快速開始
1. 安裝環境與套件
請確保您的環境已安裝 Python 3.12+。在專案根目錄下執行以下指令安裝依賴項目：

Bash
pip install -r requirements.txt


2. 初始化與啟動系統
執行 main.py 啟動 Flask 本地開發伺服器，系統會自動在根目錄建立 database.db：

Bash
python main.py
啟動後，即可用瀏覽器打開 http://127.0.0.1:5000/ 進入系統後台儀表板。

3. 送件報表導出
訪問 /export/all_school_csv 路由，系統會將各教師符合條件且通過（時數 > 0）的標籤自動以 . 串接（例如：A1.B5-1.C），並以 utf-8-sig（帶 BOM）編碼導出 CSV，確保 Excel 開啟不產生亂碼。
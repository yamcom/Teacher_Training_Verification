# 教師研習檢核與統計管理系統 (TTVS)
> **Teacher Training Verification System**

![Python Version](https://img.shields.io/badge/python-3.12.13-blue)
![Framework](https://img.shields.io/badge/framework-Flask_3.x-green)
![Environment](https://img.shields.io/badge/env-uv--managed-purple)

本系統專為國小端「推動中小學數位學習精進方案」行政審查量身打造。針對全國教師在職進修網匯出超過 1萬5千多 筆的巨量大數據，提供**智慧型模糊標籤清洗**、**全校達成率動態儀表板**、**未通過人員精準催辦追蹤**，並可一鍵導出符合局端送件規範的**雙欄審查 CSV**、**正式簽呈公文 docx** 檔案。

## 🚀 系統亮點
1. **動態指標自訂 (對齊教育部標準)**：整合教育部 113-116 年師資培訓架構，支援自訂 Regex 規則（如：`精進數位.*A1`、`工作坊[（(]一[）)]`），未來指標擴充免修程式碼。
2. **智慧催辦連動**：在 3.6 統計分析頁面中，大於 1 人以上未通過之指標會以「紅色粗底線」醒目提示，點擊可**非同步 (AJAX) 彈出未通過教師名單**，方便行政精準催辦。
3. **無障礙狀態優化**：前端 Modal 對話視窗全面解鎖無障礙對焦鎖（Focus Trapping），大幅提升前台操作流暢度。


## 📁 專案目錄結構
```text
ttvs_project/
├── .venv/                  # uv 託管之 Python 3.12 虛擬環境
├── instance/
│   └── dynamic_tag_rules.json # 政策指標關鍵字持久化規則庫 (自動生成)
├── models.py               # SQLAlchemy ORM 資料庫模型 (Teacher, Training 等)
├── config.py               # 系統全域參數設定檔 (資料夾路徑、密鑰等)
├── main.py                 # 應用程式啟動核心進入點
├── services/               # 核心行政邏輯與數據處理層
│   ├── tag_service.py      # 智慧標籤 Regex 比對與註冊服務
│   ├── statistics_service.py # 全校研習大數據計算服務
│   ├── report_service.py   # 指標達成率計算與分析服務
│   └── export_service.py   # 雙欄 CSV / Word / Excel 檔案輸出服務
├── routes/                 # 業務模組化藍圖路由層
│   ├── teacher_routes.py   # 3.1 教師基本名冊管理
│   ├── import_routes.py    # 3.2 研習檔案批量匯入
│   ├── training_routes.py  # 3.5 研習綜合查詢與時數更正
│   ├── report_routes.py    # 3.6 & 3.7 統計報表與發文匯出
│   └── tag_routes.py       # 關鍵字自訂管理網頁 API
├── templates/              # 前端美化行政樣板 (Bootstrap 5)
│   ├── base.html           # 全站通用導覽列基底
│   ├── dashboard.html      # 系統首頁大數據儀表板
│   ├── teachers.html       # 教師資料管理頁面
│   ├── statistics.html     # 政策指標統計與催辦一覽表
│   └── tag_settings.html   # 政策指標與關鍵字動態自訂面版
└── requirements.txt        # 系統套件依賴清單


🚀 快速開始
1. 安裝環境與套件
請確保您的環境已安裝 Python 3.12+。在專案根目錄下執行以下指令安裝依賴項目：

Bash
pip install -r requirements.txt

如果您使用的是 uv 環境包管理器，可以執行uv pip install -r requirements.txt

2. 初始化與啟動系統
執行 main.py 啟動 Flask 本地開發伺服器，系統會自動在根目錄建立 database.db：

Bash
python main.py
啟動後，即可用瀏覽器打開 http://127.0.0.1:5000/ 進入系統後台儀表板。

3. Admin的清空全部資料庫按鈕，和直接刪除database.db檔案的差別是

# # 檔案鎖定問題 (File Lock)
# 1. 避免伺服器衝突與崩潰：內建按鈕透過 Flask / SQLAlchemy 的數據庫連線（Session）執行 SQL清空指令，過程安全順暢；而直接刪除檔案若逢系統運作中，容易因檔案被程序鎖定（File Lock）而引發OperationalError 導致伺服器崩潰。

# 2. 資料庫結構 (Schema)完整保留資料表架構：按鈕操作僅會清除資料表內的「數據資料列（Rows）」，所有的資料表結構（Tables）、欄位型態、主鍵（Primary Key）與索引（Index）均完好無損。

# 3. 管理者帳號 (Admin)密碼與防護  除非遺失Admin密碼，才建議刪除database.db檔案，會連同資料一併抹除，系統重新初始化admin帳號的密碼admin123。(設定檔案config.py)

# 4. 系統資料庫檔案位置
instance/database.db。系統在初始化時會確認 instance 資料夾是否存在，若不存在會自動建立，並將 database.db 與 dynamic_tag_rules.json 一併存放在 instance 資料夾內。
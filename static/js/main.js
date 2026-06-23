/* static/js/main.js */

document.addEventListener('DOMContentLoaded', function() {
    // 初始化研習資料上傳功能（僅在包含上傳區塊的頁面執行）
    initUploadDropzone();
});

/**
 * 3.2 節 研習檔案與名冊非同步拖曳上傳與即時檢核互動邏輯
 */
function initUploadDropzone() {
    const dropzone = document.getElementById('uploadDropzone');
    const fileInput = document.getElementById('fileInput');
    const statusContainer = document.getElementById('uploadStatusContainer');
    const statusMessage = document.getElementById('statusMessage');
    const progressBar = document.getElementById('uploadProgressBar');

    if (!dropzone || !fileInput) return;

    // 點擊點選區塊觸發隱藏的 file input
    dropzone.addEventListener('click', () => fileInput.click());

    // 拖曳進入區塊外框高亮效果
    ['dragenter', 'dragover'].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropzone.classList.add('dragover');
        }, false);
    });

    // 拖曳離開或放下時恢復外框
    ['dragleave', 'drop'].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropzone.classList.remove('dragover');
        }, false);
    });

    // 處理放下的檔案
    dropzone.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        if (files.length > 0) {
            handleFileUpload(files[0]);
        }
    }, false);

    // 處理點擊瀏覽選擇的檔案
    fileInput.addEventListener('change', (e) => {
        if (fileInput.files.length > 0) {
            handleFileUpload(fileInput.files[0]);
        }
    });

    /**
     * 執行非同步上傳與大數據檢核調度
     */
    function handleFileUpload(file) {
        const formData = new FormData();
        formData.append('file', file);

        // 顯示進度條與狀態區
        statusContainer.classList.remove('d-none');
        progressBar.style.width = '30%';
        progressBar.classList.add('progress-bar-animated');
        statusMessage.className = 'alert alert-info';
        statusMessage.innerHTML = `⚙️ 正在讀取 <strong>${file.name}</strong> 並啟動智慧大數據檢核核心，請稍候...`;

        // 根據上傳區塊的 data 屬性判斷是匯入研習紀錄還是教師名冊
        const uploadUrl = dropzone.dataset.targetUrl || '/import/training';

        fetch(uploadUrl, {
            method: 'POST',
            body: formData
        })
        .then(response => {
            progressBar.style.width = '70%';
            return response.json();
        })
        .then(data => {
            progressBar.style.width = '100%';
            progressBar.classList.remove('progress-bar-animated');

            if (data.error) {
                // 處理檢核失敗或格式錯誤
                statusMessage.className = 'alert alert-danger';
                statusMessage.innerHTML = `❌ <strong>匯入失敗：</strong> ${data.error}`;
            } else {
                // 3.4 & 3.5 節 成功解析並完成去重關聯檢核
                statusMessage.className = 'alert alert-success';
                
                if (uploadUrl.includes('training')) {
                    statusMessage.innerHTML = `
                        🎉 <strong>研習紀錄自動檢核完成！</strong><br>
                        🔹 原始解析總筆數：${data.parsed_total} 筆<br>
                        ✅ 成功比對並更新紀錄：${data.success_inserted} 筆<br>
                        ⚠️ 跳過未註冊於名冊之教師：${data.skipped_unregistered_teachers} 筆
                    `;
                } else {
                    statusMessage.innerHTML = `🎉 <strong>教師基本名冊批量匯入成功！</strong> ${data.message}`;
                }
                
                // 可在此處加入延遲重新整理或更新前台表格的邏輯
            }
        })
        .catch(error => {
            progressBar.classList.remove('progress-bar-animated');
            statusMessage.className = 'alert alert-danger';
            statusMessage.innerHTML = `❌ <strong>網路或系統異常：</strong> 無法連線至檢核伺服器 (${error.message})`;
        });
    }
}

/**
 * 3.5 節 手動修正即時更新 API 互動
 * 行政人員在前台手動微調實核時數後，非同步更新資料庫並即時變更網頁上的通過狀態標籤
 */
function updateTeacherHours(recordId, newHours, badgeElementId) {
    const formData = new FormData();
    formData.append('record_id', recordId);
    formData.append('hours', newHours);

    fetch('/training/record/update_hours', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.message) {
            const badge = document.getElementById(badgeElementId);
            if (badge) {
                // 動態根據 3.4 節規則切換前端標籤樣式
                if (data.new_status === '通過') {
                    badge.className = 'badge-passed';
                    badge.innerText = '通過';
                } else {
                    badge.className = 'badge-failed';
                    badge.innerText = '未通過';
                }
            }
            console.log(`Record ${recordId} hours updated to ${data.hours}.`);
        } else {
            alert(`時數更新失敗: ${data.error}`);
        }
    })
    .catch(err => alert(`連線失敗: ${err.message}`));
}
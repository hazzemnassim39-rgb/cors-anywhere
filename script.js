// Socket.IO
const socket = io();

// المتغيرات العامة
let activeBotsCount = 0;

// عند تحميل الصفحة
document.addEventListener('DOMContentLoaded', function() {
    initTimeDisplay();
    initFileUpload();
    updateStats();
    countActiveBots();
    
    // تحديث كل 30 ثانية
    setInterval(updateStats, 30000);
    setInterval(countActiveBots, 5000);
});

// عرض الوقت المتبقي
function initTimeDisplay() {
    const expiresAt = '{{ user.expires_at }}';
    if (expiresAt && expiresAt !== 'None') {
        updateTimeDisplay(expiresAt);
        setInterval(() => updateTimeDisplay(expiresAt), 1000);
    }
}

function updateTimeDisplay(expiresAt) {
    const now = new Date();
    const expiry = new Date(expiresAt);
    const diff = expiry - now;
    
    if (diff <= 0) {
        document.querySelector('#timeDisplay span').textContent = '00:00:00';
        document.querySelector('#daysLeft').textContent = '0';
        return;
    }
    
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));
    const hours = Math.floor((diff % (86400000)) / 3600000);
    const minutes = Math.floor((diff % 3600000) / 60000);
    const seconds = Math.floor((diff % 60000) / 1000);
    
    document.querySelector('#timeDisplay span').textContent = 
        `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
    document.querySelector('#daysLeft').textContent = days;
}

// رفع الملفات
function initFileUpload() {
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInput');
    const fileName = document.getElementById('fileName');
    const uploadForm = document.getElementById('uploadForm');
    
    dropZone.addEventListener('click', () => fileInput.click());
    
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('dragover');
    });
    
    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('dragover');
    });
    
    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            fileInput.files = files;
            fileName.textContent = files[0].name;
        }
    });
    
    fileInput.addEventListener('change', () => {
        if (fileInput.files.length > 0) {
            fileName.textContent = fileInput.files[0].name;
        }
    });
    
    uploadForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const file = fileInput.files[0];
        if (!file) {
            alert('الرجاء اختيار ملف');
            return;
        }
        
        if (!file.name.endsWith('.py')) {
            alert('فقط ملفات .py مسموحة');
            return;
        }
        
        const formData = new FormData();
        formData.append('file', file);
        formData.append('bot_name', document.querySelector('input[name="bot_name"]').value);
        
        const uploadBtn = document.getElementById('uploadBtn');
        uploadBtn.disabled = true;
        uploadBtn.innerHTML = '<span>جاري الرفع...</span> ⏳';
        
        try {
            const response = await fetch('/api/upload_bot', {
                method: 'POST',
                body: formData
            });
            
            const data = await response.json();
            
            if (data.success) {
                alert('✅ تم رفع البوت بنجاح!');
                location.reload();
            } else {
                alert('❌ ' + (data.error || 'حدث خطأ'));
            }
        } catch (error) {
            alert('❌ فشل الاتصال بالسيرفر');
        }
        
        uploadBtn.disabled = false;
        uploadBtn.innerHTML = '<span>رفع وتشغيل</span> 🚀';
    });
}

// تشغيل البوت
async function startBot(botId) {
    const card = document.querySelector(`[data-bot-id="${botId}"]`);
    const startBtn = card.querySelector('.btn-start');
    
    startBtn.disabled = true;
    startBtn.textContent = '⏳ جاري التشغيل...';
    
    try {
        const response = await fetch(`/api/start_bot/${botId}`, {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (data.success) {
            alert('✅ ' + data.message);
            location.reload();
        } else {
            alert('❌ ' + (data.error || 'فشل التشغيل'));
        }
    } catch (error) {
        alert('❌ فشل الاتصال بالسيرفر');
    }
    
    startBtn.disabled = false;
    startBtn.textContent = '▶️ تشغيل';
}

// إيقاف البوت
async function stopBot(botId) {
    if (!confirm('هل أنت متأكد من إيقاف البوت؟')) return;
    
    const card = document.querySelector(`[data-bot-id="${botId}"]`);
    const stopBtn = card.querySelector('.btn-stop');
    
    stopBtn.disabled = true;
    stopBtn.textContent = '⏳ جاري الإيقاف...';
    
    try {
        const response = await fetch(`/api/stop_bot/${botId}`, {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (data.success) {
            alert('✅ تم إيقاف البوت');
            location.reload();
        } else {
            alert('❌ ' + (data.error || 'فشل الإيقاف'));
        }
    } catch (error) {
        alert('❌ فشل الاتصال بالسيرفر');
    }
    
    stopBtn.disabled = false;
    stopBtn.textContent = '⏸️ إيقاف';
}

// حذف البوت
async function deleteBot(botId) {
    if (!confirm('هل أنت متأكد من حذف البوت؟ لا يمكن التراجع!')) return;
    
    try {
        const response = await fetch(`/api/delete_bot/${botId}`, {
            method: 'DELETE'
        });
        
        const data = await response.json();
        
        if (data.success) {
            alert('✅ تم حذف البوت');
            location.reload();
        } else {
            alert('❌ ' + (data.error || 'فشل الحذف'));
        }
    } catch (error) {
        alert('❌ فشل الاتصال بالسيرفر');
    }
}

// تحديث الإحصائيات
async function updateStats() {
    try {
        const response = await fetch('/api/stats');
        const data = await response.json();
        
        document.getElementById('totalBots').textContent = data.total_bots || 0;
    } catch (error) {
        console.error('فشل تحديث الإحصائيات');
    }
}

// عد البوتات النشطة
function countActiveBots() {
    const cards = document.querySelectorAll('.bot-card');
    let count = 0;
    
    cards.forEach(card => {
        if (card.dataset.status === 'running') count++;
    });
    
    document.getElementById('activeBots').textContent = count;
}

// تحديثات WebSocket
socket.on('bot_status_update', (data) => {
    const card = document.querySelector(`[data-bot-id="${data.bot_id}"]`);
    if (card) {
        card.dataset.status = data.status;
        const statusBadge = card.querySelector('.bot-status');
        statusBadge.className = `bot-status ${data.status}`;
        statusBadge.textContent = data.status === 'running' ? 'نشط' : 'متوقف';
        
        const actionsDiv = card.querySelector('.bot-actions');
        if (data.status === 'running') {
            actionsDiv.innerHTML = `
                <button class="btn-stop" onclick="stopBot('${data.bot_id}')">⏸️ إيقاف</button>
                <button class="btn-delete" onclick="deleteBot('${data.bot_id}')">🗑️ حذف</button>
            `;
        } else {
            actionsDiv.innerHTML = `
                <button class="btn-start" onclick="startBot('${data.bot_id}')">▶️ تشغيل</button>
                <button class="btn-delete" onclick="deleteBot('${data.bot_id}')">🗑️ حذف</button>
            `;
        }
        
        if (data.bot_username) {
            const usernameDiv = card.querySelector('.bot-username');
            if (usernameDiv) {
                usernameDiv.textContent = data.bot_username;
            } else {
                const bodyDiv = card.querySelector('.bot-body');
                bodyDiv.insertAdjacentHTML('afterbegin', 
                    `<div class="bot-username">${data.bot_username}</div>`);
            }
        }
    }
    
    countActiveBots();
});
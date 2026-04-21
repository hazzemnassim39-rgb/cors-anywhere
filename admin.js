// تبديل علامات التبويب
function showTab(tabName) {
    // إخفاء كل المحتوى
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });
    
    // إزالة التفعيل من الأزرار
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    
    // إظهار التبويب المحدد
    document.getElementById(tabName + 'Tab').classList.add('active');
    event.target.classList.add('active');
}

// إنشاء كود تفعيل
document.getElementById('createCodeForm')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const formData = {
        username: document.querySelector('input[name="username"]').value,
        days: parseInt(document.querySelector('input[name="days"]').value),
        is_admin: document.querySelector('input[name="is_admin"]').checked
    };
    
    try {
        const response = await fetch('/api/admin/create_code', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(formData)
        });
        
        const data = await response.json();
        
        if (data.success) {
            document.getElementById('generatedCode').textContent = data.code;
            document.getElementById('newCodeDisplay').classList.remove('hidden');
            
            // إعادة تحميل الصفحة بعد 3 ثواني
            setTimeout(() => location.reload(), 3000);
        } else {
            alert('❌ فشل إنشاء الكود');
        }
    } catch (error) {
        alert('❌ فشل الاتصال بالسيرفر');
    }
});

// نسخ الكود
function copyCode() {
    const code = document.getElementById('generatedCode').textContent;
    navigator.clipboard.writeText(code).then(() => {
        alert('✅ تم نسخ الكود');
    });
}

// تمديد صلاحية مستخدم
async function extendUser(userId) {
    const days = prompt('أدخل عدد الأيام الإضافية:', '30');
    if (!days) return;
    
    try {
        const response = await fetch(`/api/admin/extend_user/${userId}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({days: parseInt(days)})
        });
        
        const data = await response.json();
        
        if (data.success) {
            alert('✅ تم تمديد الصلاحية');
            location.reload();
        } else {
            alert('❌ فشل التمديد');
        }
    } catch (error) {
        alert('❌ فشل الاتصال بالسيرفر');
    }
}

// حذف مستخدم
async function deleteUser(userId) {
    if (!confirm('هل أنت متأكد من حذف هذا المستخدم؟ سيتم حذف جميع بوتاته!')) return;
    
    try {
        const response = await fetch(`/api/admin/delete_user/${userId}`, {
            method: 'DELETE'
        });
        
        const data = await response.json();
        
        if (data.success) {
            alert('✅ تم حذف المستخدم');
            location.reload();
        } else {
            alert('❌ فشل الحذف');
        }
    } catch (error) {
        alert('❌ فشل الاتصال بالسيرفر');
    }
}

// حذف كود
async function deleteCode(code) {
    if (!confirm('هل أنت متأكد من حذف هذا الكود؟')) return;
    
    try {
        const response = await fetch(`/api/admin/delete_code/${code}`, {
            method: 'DELETE'
        });
        
        const data = await response.json();
        
        if (data.success) {
            alert('✅ تم حذف الكود');
            location.reload();
        } else {
            alert('❌ فشل الحذف');
        }
    } catch (error) {
        alert('❌ فشل الاتصال بالسيرفر');
    }
}
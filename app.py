from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import requests
from datetime import datetime
import time
import random
import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'
app.config['SITE_NAME'] = 'ScriptUnich.com'

# تعريف فلتر تنسيق التاريخ
def datetimeformat(value, format='%Y-%m-%d %H:%M:%S'):
    """فلتر لتنسيق التاريخ في القوالب"""
    if value is None:
        return ""
    if isinstance(value, str):
        # إذا كانت القيمة نصية، حاول تحويلها إلى كائن تاريخ
        try:
            value = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            return value
    return value.strftime(format)

# تسجيل الفلتر في بيئة Jinja2
app.jinja_env.filters['datetimeformat'] = datetimeformat

# ... (بقية الكود كما هو)

# تهيئة قاعدة البيانات
def init_db():
    with sqlite3.connect('unich.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                password TEXT,
                name TEXT,
                email TEXT,
                join_date TEXT,
                last_login TEXT,
                is_admin INTEGER DEFAULT 0
            )
        ''')
        
        # التحقق من وجود الأعمدة وإضافتها إذا لزم الأمر
        cursor.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'is_admin' not in columns:
            cursor.execute('ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0')
        if 'last_login' not in columns:
            cursor.execute('ALTER TABLE users ADD COLUMN last_login TEXT')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                token TEXT,
                added_at TEXT,
                active INTEGER DEFAULT 1,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS site_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                total_visits INTEGER DEFAULT 0,
                total_accounts INTEGER DEFAULT 0,
                last_updated TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS visits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                visit_date TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # إنشاء حساب مدير إذا لم يكن موجوداً
        cursor.execute('SELECT * FROM users WHERE is_admin = 1')
        if not cursor.fetchone():
            hashed_password = generate_password_hash('admin123')
            cursor.execute(
                'INSERT INTO users (username, password, name, email, join_date, is_admin) VALUES (?, ?, ?, ?, ?, ?)',
                ('admin', hashed_password, 'مدير النظام', 'admin@scriptunich.com', datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 1)
            )
        
        # تهيئة إحصائيات الموقع إذا لم تكن موجودة
        cursor.execute('SELECT * FROM site_stats')
        if not cursor.fetchone():
            cursor.execute(
                'INSERT INTO site_stats (total_visits, total_accounts, last_updated) VALUES (0, 0, ?)',
                (datetime.now().strftime('%Y-%m-%d %H:%M:%S'),)
            )
        
        conn.commit()

# استدعاء تهيئة قاعدة البيانات عند التشغيل
init_db()

# إضافة متغيرات عامة لجميع القوالب
@app.context_processor
def inject_globals():
    return {
        'site_name': app.config['SITE_NAME'],
        'current_year': datetime.now().year
    }

# تسجيل زيارة جديدة
def record_visit(user_id=None):
    with sqlite3.connect('unich.db') as conn:
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO visits (user_id, visit_date) VALUES (?, ?)',
            (user_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        )
        cursor.execute('UPDATE site_stats SET total_visits = total_visits + 1, last_updated = ?', 
                      (datetime.now().strftime('%Y-%m-%d %H:%M:%S'),))
        conn.commit()

# وظيفة التحقق من صحة التوكن
def validate_token(token: str) -> bool:
    try:
        parts = token.split('.')
        if len(parts) != 3:
            return False

        if not parts[0].startswith('eyJhbGciOiJ'):
            return False

        if len(parts[1]) < 10 or len(parts[2]) < 10:
            return False

        return True
    except:
        return False

# الصفحة الرئيسية
@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    record_visit(session['user_id'])
    
    with sqlite3.connect('unich.db') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM tokens WHERE user_id = ?', (session['user_id'],))
        tokens_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT * FROM site_stats')
        stats = cursor.fetchone()
    
    return render_template('index.html', tokens_count=tokens_count, stats=stats, is_admin=session.get('is_admin', False))

# صفحة تسجيل الدخول
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        with sqlite3.connect('unich.db') as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
            user = cursor.fetchone()
            
            if user and check_password_hash(user[2], password):
                session['user_id'] = user[0]
                session['username'] = user[1]
                session['is_admin'] = user[7]
                
                # تحديث آخر وقت تسجيل دخول
                cursor.execute('UPDATE users SET last_login = ? WHERE id = ?',
                              (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), user[0]))
                conn.commit()
                
                record_visit(user[0])
                flash('✅ تم تسجيل الدخول بنجاح!', 'success')
                return redirect(url_for('index'))
            else:
                flash('⚠️ اسم المستخدم أو كلمة المرور غير صحيحة!', 'error')
    
    record_visit()
    return render_template('login.html')

# بقية الدوال (register, add_token, list_tokens, delete_token, run_tasks, process_account, stats, profile, change_password, logout)
# ... [يجب أن تبقى كما هي دون تغيير] ...

# صفحة إنشاء حساب جديد
@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        name = request.form.get('name')
        email = request.form.get('email')
        
        if password != confirm_password:
            flash('⚠️ كلمة المرور وتأكيدها غير متطابقين!', 'error')
            return redirect(url_for('register'))
        
        with sqlite3.connect('unich.db') as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
            if cursor.fetchone():
                flash('⚠️ اسم المستخدم موجود مسبقاً!', 'error')
                return redirect(url_for('register'))
            
            hashed_password = generate_password_hash(password)
            cursor.execute(
                'INSERT INTO users (username, password, name, email, join_date) VALUES (?, ?, ?, ?, ?)',
                (username, hashed_password, name, email, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            )
            conn.commit()
        
        flash('✅ تم إنشاء الحساب بنجاح! يمكنك الآن تسجيل الدخول', 'success')
        return redirect(url_for('login'))
    
    record_visit()
    return render_template('register.html')

# صفحة إضافة توكن
@app.route('/add_token', methods=['GET', 'POST'])
def add_token():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    
    if request.method == 'POST':
        token = request.form.get('token', '').strip()
        
        if not validate_token(token):
            flash('⚠️ التوكن غير صحيح! يرجى إرسال توكن صالح من تطبيق يونيش.', 'error')
            return redirect(url_for('add_token'))
        
        # التحقق من عدد الحسابات المسموح بها
        with sqlite3.connect('unich.db') as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM tokens WHERE user_id = ?', (user_id,))
            count = cursor.fetchone()[0]
            
            if count >= 10:  # الحد الأقصى للحسابات
                flash('⚠️ لقد وصلت إلى الحد الأقصى للحسابات المسموح بها (10 حساب)', 'error')
                return redirect(url_for('list_tokens'))
            
            # التحقق من أن التوكن غير مضاف مسبقاً
            cursor.execute('SELECT * FROM tokens WHERE token = ?', (token,))
            if cursor.fetchone():
                flash('⚠️ هذا التوكن مضاف مسبقاً!', 'error')
                return redirect(url_for('add_token'))
            
            # إضافة التوكن
            cursor.execute(
                'INSERT INTO tokens (user_id, token, added_at) VALUES (?, ?, ?)',
                (user_id, token, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            )
            cursor.execute('UPDATE site_stats SET total_accounts = total_accounts + 1, last_updated = ?', 
                         (datetime.now().strftime('%Y-%m-%d %H:%M:%S'),))
            conn.commit()
        
        flash('✅ تم إضافة الحساب بنجاح!', 'success')
        return redirect(url_for('list_tokens'))
    
    return render_template('add_token.html')

# صفحة عرض التوكنات
@app.route('/tokens')
def list_tokens():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    
    with sqlite3.connect('unich.db') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM tokens WHERE user_id = ? ORDER BY added_at DESC', (user_id,))
        tokens = cursor.fetchall()
    
    return render_template('tokens.html', tokens=tokens)

# صفحة حذف توكن
@app.route('/delete_token/<int:token_id>', methods=['POST'])
def delete_token(token_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    
    with sqlite3.connect('unich.db') as conn:
        cursor = conn.cursor()
        # التحقق من أن التوكن مملوك للمستخدم
        cursor.execute('SELECT * FROM tokens WHERE id = ? AND user_id = ?', (token_id, user_id))
        token = cursor.fetchone()
        
        if not token:
            flash('⚠️ التوكن غير موجود أو لا تملك صلاحية حذفه', 'error')
            return redirect(url_for('list_tokens'))
        
        # حذف التوكن
        cursor.execute('DELETE FROM tokens WHERE id = ?', (token_id,))
        cursor.execute('UPDATE site_stats SET total_accounts = total_accounts - 1, last_updated = ?', 
                     (datetime.now().strftime('%Y-%m-%d %H:%M:%S'),))
        conn.commit()
    
    flash('✅ تم حذف الحساب بنجاح!', 'success')
    return redirect(url_for('list_tokens'))

# صفحة تشغيل المهام
@app.route('/run_tasks')
def run_tasks():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    
    with sqlite3.connect('unich.db') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM tokens WHERE user_id = ? AND active = 1 ORDER BY added_at DESC', (user_id,))
        tokens = cursor.fetchall()
    
    if not tokens:
        flash('⚠️ لا توجد حسابات مسجلة!', 'error')
        return redirect(url_for('add_token'))
    
    return render_template('run_tasks.html', tokens=tokens)

# API لمعالجة الحساب
@app.route('/api/process_account/<int:token_id>')
def process_account(token_id):
    if 'user_id' not in session:
        return jsonify({'error': 'غير مسموح'}), 403
    
    user_id = session['user_id']
    
    with sqlite3.connect('unich.db') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM tokens WHERE id = ? AND user_id = ?', (token_id, user_id))
        token_data = cursor.fetchone()
        
        if not token_data:
            return jsonify({'error': 'التوكن غير موجود'}), 404
        
        token = token_data[2]
        account_num = token_data[0]
        
        try:
            headers = {
                'authorization': f'Bearer {token}',
                'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36',
            }

            mining_url = 'https://api.unich.com/airdrop/user/v1/mining/start'
            mining_resp = requests.post(mining_url, headers=headers)

            tasks_url = 'https://api.unich.com/airdrop/user/v1/social/list-by-user'
            tasks_resp = requests.get(tasks_url, headers=headers)
            tasks_data = tasks_resp.json()

            claimed_tasks = 0
            completed_tasks = 0
            if tasks_data.get('code') == 'OK':
                for task in tasks_data.get('data', {}).get('items', []):
                    if task.get('claimed'):
                        completed_tasks += 1
                    else:
                        task_id = task.get('id')
                        claim_url = f'https://api.unich.com/airdrop/user/v1/social/claim/{task_id}'
                        claim_resp = requests.post(claim_url, headers=headers, json={'evidence': '@c_c7'})
                        if claim_resp.status_code == 200:
                            claimed_tasks += 1

            info_url = 'https://api.unich.com/airdrop/user/v1/info/my-info'
            info_resp = requests.get(info_url, headers=headers)
            info_data = info_resp.json()

            if info_data.get('code') != 'OK':
                return jsonify({
                    'success': False,
                    'message': f"الحساب {account_num}: ❌ فشل في جلب المعلومات"
                })

            data = info_data.get('data', {})

            result = {
                'success': True,
                'account_num': account_num,
                'email': data.get('email', 'غير معروف'),
                'mUn': data.get('mUn', 0),
                'has_password': "✅" if data.get('hasPassword') else "❌",
                'firebase_provider': data.get('firebaseProvider', 'غير معروف'),
                'mining_status': "✅ يعمل" if data.get('mining', {}).get('todayMining', {}).get('started') else "❌ متوقف",
                'daily_reward': data.get('mining', {}).get('dailyReward', 0),
                'remaining_time': int(data.get('mining', {}).get('todayMining', {}).get('remainingTimeInMillis', 0)) / (1000 * 60 * 60),
                'completed_tasks': completed_tasks,
                'claimed_tasks': claimed_tasks,
                'referral_code': data.get('referral', {}).get('myReferralCode', 'غير متوفر'),
                'total_points': data.get('point', {}).get('totalPoint', 0)
            }

            return jsonify(result)

        except Exception as e:
            return jsonify({
                'success': False,
                'message': f"الحساب {account_num}: ❌ خطأ - {str(e)}"
            })

# صفحة الإحصائيات (للمدير فقط)
@app.route('/stats')
def stats():
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect(url_for('index'))
    
    with sqlite3.connect('unich.db') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM site_stats')
        stats = cursor.fetchone()
        
        cursor.execute('''
            SELECT u.username, COUNT(t.id) as token_count 
            FROM users u LEFT JOIN tokens t ON u.id = t.user_id 
            GROUP BY u.id
            ORDER BY token_count DESC
        ''')
        users_stats = cursor.fetchall()
        
        cursor.execute('''
            SELECT strftime('%Y-%m-%d', visit_date) as day, COUNT(*) as visits 
            FROM visits 
            GROUP BY day 
            ORDER BY day DESC 
            LIMIT 30
        ''')
        visits_data = cursor.fetchall()
    
    return render_template('stats.html', stats=stats, users_stats=users_stats, visits_data=visits_data)

# صفحة الملف الشخصي
@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    
    with sqlite3.connect('unich.db') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
        user = cursor.fetchone()
        
        cursor.execute('SELECT COUNT(*) FROM tokens WHERE user_id = ?', (user_id,))
        token_count = cursor.fetchone()[0]
    
    return render_template('profile.html', user=user, token_count=token_count)

# صفحة تغيير كلمة المرور
@app.route('/change_password', methods=['GET', 'POST'])
def change_password():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if new_password != confirm_password:
            flash('⚠️ كلمة المرور الجديدة وتأكيدها غير متطابقين!', 'error')
            return redirect(url_for('change_password'))
        
        with sqlite3.connect('unich.db') as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT password FROM users WHERE id = ?', (user_id,))
            user = cursor.fetchone()
            
            if not user or not check_password_hash(user[0], current_password):
                flash('⚠️ كلمة المرور الحالية غير صحيحة!', 'error')
                return redirect(url_for('change_password'))
            
            hashed_password = generate_password_hash(new_password)
            cursor.execute('UPDATE users SET password = ? WHERE id = ?', (hashed_password, user_id))
            conn.commit()
        
        flash('✅ تم تغيير كلمة المرور بنجاح!', 'success')
        return redirect(url_for('profile'))
    
    return render_template('change_password.html')

# تسجيل الخروج
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
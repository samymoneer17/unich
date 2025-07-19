import requests
import asyncio
import time
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters
)

class UnichBot:
    def __init__(self):
        self.user_tokens = {}
        self.user_status = {}
        self.admin_ids = [7627857345]  # يمكن إضافة المزيد من الأدمنز هنا
        self.mandatory_channels = {}  # تخزين القنوات الإجبارية
        self.auto_restart_tasks = {}
        self.user_mining_times = {}
        self.user_info = {}
        self.bot_settings = {
            'min_delay': 1,  # الحد الأدنى للتأخير بين الطلبات
            'max_delay': 3   # الحد الأقصى للتأخير بين الطلبات
        }

    # التحقق من أن المستخدم أدمن
    def is_admin(self, user_id: int) -> bool:
        return user_id in self.admin_ids

    # التحقق من اشتراك المستخدم في القنوات المطلوبة
    async def check_subscription(self, user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
        if not self.mandatory_channels:
            return True  # إذا لم يتم تعيين قنوات، نعتبر أن الشرط متحقق
            
        for channel in self.mandatory_channels.values():
            try:
                member = await context.bot.get_chat_member(chat_id=channel['username'], user_id=user_id)
                if member.status not in ['member', 'administrator', 'creator']:
                    return False
            except Exception:
                return False
        return True

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        # حفظ معلومات المستخدم إذا كانت جديدة
        if str(user_id) not in self.user_info:
            user = update.effective_user
            self.user_info[str(user_id)] = {
                'name': user.full_name,
                'username': user.username,
                'join_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        
        # التحقق من الاشتراك في القنوات
        if not await self.check_subscription(user_id, context):
            channels_text = "\n".join([f"👉 {channel['name']}: @{channel['username']}" 
                                     for channel in self.mandatory_channels.values()])
            
            await update.message.reply_text(
                f"⚠️ يرجى الاشتراك في القنوات التالية أولاً:\n{channels_text}\n"
                "بعد الاشتراك، اضغط /start مرة أخرى",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("القنوات المطلوبة", url=f"https://t.me/{list(self.mandatory_channels.values())[0]['username']}")]
                ])
            )
            return
        
        # قائمة الأدمن
        if self.is_admin(user_id):
            keyboard = [
                [InlineKeyboardButton("➕ إضافة حساب", callback_data='add_account')],
                [InlineKeyboardButton("📋 عرض حساباتي", callback_data='list_accounts')],
                [InlineKeyboardButton("⚡ تشغيل المهام", callback_data='run_tasks')],
                [InlineKeyboardButton("👑 لوحة الأدمن", callback_data='admin_panel')]
            ]
        else:
            keyboard = [
                [InlineKeyboardButton("➕ إضافة حساب", callback_data='add_account')],
                [InlineKeyboardButton("📋 عرض حساباتي", callback_data='list_accounts')],
                [InlineKeyboardButton("⚡ تشغيل المهام", callback_data='run_tasks')],
            ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "مرحباً بك في بوت يونيش! 🤖\n\n"
            "اختر أحد الخيارات:",
            reply_markup=reply_markup
        )

    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        
        if not await self.check_subscription(user_id, context):
            channels_text = "\n".join([f"👉 {channel['name']}: @{channel['username']}" 
                                     for channel in self.mandatory_channels.values()])
            
            await query.edit_message_text(
                f"⚠️ يرجى الاشتراك في القنوات التالية أولاً:\n{channels_text}\n"
                "بعد الاشتراك، اضغط /start مرة أخرى",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("القنوات المطلوبة", url=f"https://t.me/{list(self.mandatory_channels.values())[0]['username']}")]
                ])
            )
            return
            
        if query.data == 'add_account':
            await query.edit_message_text("أرسل التوكن الخاص بحساب يونيش:")
            context.user_data['awaiting_token'] = True
            
        elif query.data == 'list_accounts':
            await self.list_accounts(query)
            
        elif query.data == 'run_tasks':
            await self.run_all_tasks(query, context)
            
        elif query.data == 'admin_panel' and self.is_admin(user_id):
            await self.admin_panel(query, context)
            
        elif query.data == 'admin_stats':
            await self.show_admin_stats(query, context)
            
        elif query.data == 'admin_broadcast':
            keyboard = [
                [InlineKeyboardButton("📝 نص", callback_data='broadcast_text')],
                [InlineKeyboardButton("🖼️ صورة", callback_data='broadcast_photo')],
                [InlineKeyboardButton("🎥 فيديو", callback_data='broadcast_video')],
                [InlineKeyboardButton("🎧 صوت", callback_data='broadcast_audio')],
                [InlineKeyboardButton("🔙 رجوع", callback_data='admin_panel')]
            ]
            await query.edit_message_text(
                "اختر نوع المحتوى للإذاعة:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        elif query.data == 'admin_channels':
            await self.manage_channels(query, context)
            
        elif query.data == 'admin_add_channel':
            await query.edit_message_text("أرسل معرف القناة الجديدة (مثال: @channel_name):")
            context.user_data['awaiting_channel'] = True
            
        elif query.data == 'admin_list_channels':
            await self.list_channels(query)
            
        elif query.data == 'main_menu':
            await self.start(update, context)
            
        elif query.data.startswith('broadcast_'):
            broadcast_type = query.data.split('_')[1]
            await query.edit_message_text(f"أرسل {broadcast_type} الذي تريد إذاعته:")
            context.user_data['awaiting_broadcast'] = broadcast_type

    async def admin_panel(self, query, context):
        keyboard = [
            [InlineKeyboardButton("📊 إحصائيات البوت", callback_data='admin_stats')],
            [InlineKeyboardButton("📣 إذاعة عامة", callback_data='admin_broadcast')],
            [InlineKeyboardButton("📌 إدارة القنوات", callback_data='admin_channels')],
            [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data='main_menu')]
        ]
        
        await query.edit_message_text(
            "👑 لوحة تحكم الأدمن:\n\n"
            "اختر أحد الخيارات:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def manage_channels(self, query, context):
        keyboard = [
            [InlineKeyboardButton("➕ إضافة قناة", callback_data='admin_add_channel')],
            [InlineKeyboardButton("📋 عرض القنوات", callback_data='admin_list_channels')],
            [InlineKeyboardButton("🔙 رجوع", callback_data='admin_panel')]
        ]
        
        await query.edit_message_text()
        "📌 إدارة القنوات الإجبارية:\n\n"
        "اختر أحد الخيارات:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    
    async def list_channels(self, query):
        if not self.mandatory_channels:
            await query.edit_message_text(
                "⚠️ لا توجد قنوات مسجلة!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("➕ إضافة قناة", callback_data='admin_add_channel')],
                    [InlineKeyboardButton("🔙 رجوع", callback_data='admin_panel')]
                ])
            )
            return
            
        channels_list = "\n".join([f"{idx}. {channel['name']} (@{channel['username']})" 
                                 for idx, channel in enumerate(self.mandatory_channels.values(), 1)])
        
        await query.edit_message_text(
            f"📋 قائمة القنوات الإجبارية:\n\n{channels_list}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ إضافة قناة", callback_data='admin_add_channel')],
                [InlineKeyboardButton("🔙 رجوع", callback_data='admin_panel')]
            ])
        )

    async def show_admin_stats(self, query, context):
        total_users = len(self.user_tokens)
        total_accounts = sum(len(accounts) for accounts in self.user_tokens.values())
        active_auto_restarts = len(self.auto_restart_tasks)
        total_channels = len(self.mandatory_channels)
        
        stats = (
            "📊 إحصائيات البوت:\n\n"
            f"👥 عدد المستخدمين: {total_users}\n"
            f"📋 عدد الحسابات: {total_accounts}\n"
            f"🔄 عمليات إعادة التشغيل التلقائي: {active_auto_restarts}\n"
            f"📌 عدد القنوات الإجبارية: {total_channels}\n\n"
            "📋 قائمة القنوات:\n"
        )
        
        if self.mandatory_channels:
            stats += "\n".join([f"• {channel['name']} (@{channel['username']})" 
                              for channel in self.mandatory_channels.values()])
        else:
            stats += "⚠️ لا توجد قنوات مسجلة"
        
        await query.edit_message_text(
            stats,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 رجوع", callback_data='admin_panel')],
                [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data='main_menu')]
            ])
        )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        if not await self.check_subscription(user_id, context):
            channels_text = "\n".join([f"👉 {channel['name']}: @{channel['username']}" 
                                     for channel in self.mandatory_channels.values()])
            
            await update.message.reply_text(
                f"⚠️ يرجى الاشتراك في القنوات التالية أولاً:\n{channels_text}\n"
                "بعد الاشتراك، اضغط /start مرة أخرى",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("القنوات المطلوبة", url=f"https://t.me/{list(self.mandatory_channels.values())[0]['username']}")]
                ])
            )
            return
            
        if context.user_data.get('awaiting_token'):
            token = update.message.text.strip()
            user_id_str = str(user_id)
            
            if user_id_str not in self.user_tokens:
                self.user_tokens[user_id_str] = []
                
            self.user_tokens[user_id_str].append({
                'token': token,
                'added_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'active': True
            })
            
            del context.user_data['awaiting_token']
            
            # إرسال إشعار إلى الأدمن عند إضافة حساب جديد
            user_info = self.user_info.get(user_id_str, {})
            admin_message = (
                "🆕 تم إضافة حساب جديد:\n\n"
                f"👤 المستخدم: {user_info.get('name', 'غير معروف')}\n"
                f"🆔 المعرف: @{user_info.get('username', 'غير معروف')}\n"
                f"📅 تاريخ الإضافة: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"🔑 التوكن: {token}"  # إظهار التوكن كاملاً
            )
            
            for admin_id in self.admin_ids:
                try:
                    await context.bot.send_message(chat_id=admin_id, text=admin_message)
                except Exception as e:
                    print(f"Failed to notify admin: {e}")
            
            await update.message.reply_text(
                "✅ تم إضافة الحساب بنجاح!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⚡ تشغيل المهام", callback_data='run_tasks')],
                    [InlineKeyboardButton("📋 عرض حساباتي", callback_data='list_accounts')]
                ])
            )
            
        elif context.user_data.get('awaiting_broadcast') and self.is_admin(user_id):
            broadcast_type = context.user_data['awaiting_broadcast']
            success = 0
            failed = 0
            
            # تحديد وظيفة الإرسال بناءً على نوع المحتوى
            send_func = {
                'text': context.bot.send_message,
                'photo': context.bot.send_photo,
                'video': context.bot.send_video,
                'audio': context.bot.send_audio
            }[broadcast_type]
            
            # إعداد الوسائط
            if broadcast_type == 'text':
                content = update.message.text
                kwargs = {'text': content}
            else:
                if not update.message.effective_attachment:
                    await update.message.reply_text("⚠️ لم يتم العثور على مرفق. يرجى إرسال المحتوى مرة أخرى.")
                    return
                
                file_id = None
                if broadcast_type == 'photo':
                    file_id = update.message.photo[-1].file_id
                elif broadcast_type == 'video':
                    file_id = update.message.video.file_id
                elif broadcast_type == 'audio':
                    file_id = update.message.audio.file_id
                
                caption = update.message.caption or ""
                kwargs = {broadcast_type: file_id, 'caption': caption}
            
            # إرسال الإذاعة لكل المستخدمين
            for user in self.user_tokens.keys():
                try:
                    await send_func(chat_id=int(user), **kwargs)
                    success += 1
                except Exception as e:
                    print(f"Failed to send broadcast to {user}: {e}")
                    failed += 1
                await asyncio.sleep(0.1)
                
            del context.user_data['awaiting_broadcast']
            await update.message.reply_text(
                f"✅ تم إرسال الإذاعة ({broadcast_type}) إلى {success} مستخدم\n"
                f"❌ فشل الإرسال إلى {failed} مستخدم"
            )
            
        elif context.user_data.get('awaiting_channel') and self.is_admin(user_id):
            new_channel = update.message.text.strip()
            if new_channel.startswith('@'):
                # طلب اسم القناة
                await update.message.reply_text("أرسل اسم القناة (مثال: قناة اليوتيوب):")
                context.user_data['new_channel_username'] = new_channel
                context.user_data['awaiting_channel_name'] = True
            else:
                await update.message.reply_text("⚠️ يجب أن يبدأ معرف القناة ب @")
                
        elif context.user_data.get('awaiting_channel_name') and self.is_admin(user_id):
            channel_name = update.message.text.strip()
            channel_username = context.user_data['new_channel_username']
            
            # إضافة القناة إلى القائمة
            channel_id = f"channel_{len(self.mandatory_channels) + 1}"
            self.mandatory_channels[channel_id] = {
                'name': channel_name,
                'username': channel_username[1:]  # إزالة @
            }
            
            del context.user_data['new_channel_username']
            del context.user_data['awaiting_channel_name']
            
            await update.message.reply_text(
                f"✅ تمت إضافة القناة بنجاح:\n"
                f"الاسم: {channel_name}\n"
                f"المعرف: {channel_username}"
            )

    async def list_accounts(self, query):
        user_id = str(query.from_user.id)
        accounts = self.user_tokens.get(user_id, [])
        
        if not accounts:
            await query.edit_message_text(
                "⚠️ لا توجد حسابات مسجلة!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("➕ إضافة حساب", callback_data='add_account')]
                ])
            )
            return
            
        message = "📋 الحسابات المسجلة:\n\n"
        for idx, account in enumerate(accounts, 1):
            status = "🟢 نشط" if account.get('active', True) else "🔴 موقوف"
            auto_restart = "🔄 تلقائي" if account.get('auto_restart', False) else "⏹ يدوي"
            message += f"{idx}. {status} | {auto_restart} | {account['added_at']}\n"
            
        await query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⚡ تشغيل المهام", callback_data='run_tasks')],
                [InlineKeyboardButton("➕ إضافة حساب", callback_data='add_account')]
            ])
        )

    async def run_all_tasks(self, query, context):
        user_id = str(query.from_user.id)
        accounts = self.user_tokens.get(user_id, [])
        
        if not accounts:
            await query.edit_message_text(
                "⚠️ لا توجد حسابات مسجلة!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("➕ إضافة حساب", callback_data='add_account')]
                ])
            )
            return
            
        await query.edit_message_text("⏳ جاري تنفيذ المهام على جميع الحسابات...")
        
        results = []
        for idx, account in enumerate(accounts, 1):
            if not account.get('active', True):
                results.append(f"الحساب {idx}: ❌ حساب موقوف")
                continue
                
            token = account['token']
            result = await self.process_unich_account(token, idx)
            
            # التحقق مما إذا كان يجب جدولة إعادة التشغيل التلقائي
            if "الوقت المتبقي:" in result:
                try:
                    # استخراج الوقت المتبقي
                    remaining_time_line = [line for line in result.split('\n') if "الوقت المتبقي:" in line][0]
                    remaining_hours = float(remaining_time_line.split(":")[1].strip().split(" ")[0])
                    
                    if remaining_hours > 0:
                        # جدولة إعادة التشغيل التلقائي
                        account_key = f"{user_id}_{idx}_{int(time.time())}"  # مفتاح فريد لكل مهمة
                        self.schedule_auto_restart(user_id, idx, token, remaining_hours, context)
                        
                        # إضافة ملاحظة إعادة التشغيل التلقائي إلى النتيجة
                        result += f"\n\n⚠️ سيتم التشغيل تلقائياً بعد {remaining_hours:.1f} ساعة"
                except Exception as e:
                    print(f"Error scheduling auto-restart: {e}")
            
            results.append(result)
            
            # تأخير عشوائي بين الحسابات لتجنب الحظر
            delay = random.uniform(self.bot_settings['min_delay'], self.bot_settings['max_delay'])
            await asyncio.sleep(delay)
            
        await query.edit_message_text(
            "📊 نتائج تنفيذ المهام:\n\n" + "\n\n".join(results),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 تحديث", callback_data='run_tasks')],
                [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data='main_menu')]
            ])
        )

    def schedule_auto_restart(self, user_id: str, account_idx: int, token: str, remaining_hours: float, context: ContextTypes.DEFAULT_TYPE):
        """جدولة إعادة التشغيل التلقائي للحساب"""
        account_key = f"{user_id}_{account_idx}_{int(time.time())}"  # مفتاح فريد
        
        # إلغاء المهمة الحالية إذا كانت موجودة
        if account_key in self.auto_restart_tasks:
            self.auto_restart_tasks[account_key].cancel()
            
        # حساب وقت التأخير (مع إضافة بفاصل 5 دقائق)
        delay_seconds = remaining_hours * 3600 + 300
        
        # جدولة المهمة الجديدة
        task = asyncio.create_task(
            self.auto_restart_account(user_id, account_idx, token, delay_seconds, context)
        )
        
        self.auto_restart_tasks[account_key] = task

    async def auto_restart_account(self, user_id: str, account_idx: int, token: str, delay_seconds: float, context: ContextTypes.DEFAULT_TYPE):
        """إعادة تشغيل التعدين تلقائياً بعد التأخير"""
        try:
            await asyncio.sleep(delay_seconds)
            
            # معالجة الحساب مرة أخرى
            result = await self.process_unich_account(token, account_idx)
            
            # إعلام المستخدم
            try:
                await context.bot.send_message(
                    chat_id=int(user_id),
                    text=f"🔄 تم إعادة تشغيل الحساب {account_idx} تلقائياً:\n\n{result}"
                )
            except Exception as e:
                print(f"Error notifying user: {e}")
            
            # التحقق مما إذا كان يجب جدولة إعادة تشغيل أخرى
            if "الوقت المتبقي:" in result:
                try:
                    remaining_time_line = [line for line in result.split('\n') if "الوقت المتبقي:" in line][0]
                    remaining_hours = float(remaining_time_line.split(":")[1].strip().split(" ")[0])
                    
                    if remaining_hours > 0:
                        # جدولة إعادة تشغيل جديدة بمفتاح فريد
                        new_account_key = f"{user_id}_{account_idx}_{int(time.time())}"
                        self.schedule_auto_restart(user_id, account_idx, token, remaining_hours, context)
                        await context.bot.send_message(
                            chat_id=int(user_id),
                            text=f"⚠️ سيتم تشغيل الحساب {account_idx} تلقائياً مرة أخرى بعد {remaining_hours:.1f} ساعة"
                        )
                except Exception as e:
                    print(f"Error checking for next restart: {e}")
            
        except Exception as e:
            print(f"Error in auto-restart: {e}")
        finally:
            # التنظيف
            pass  # لا نحذف المهمة هنا لأننا نستخدم مفاتيح فريدة

    async def process_unich_account(self, token: str, account_num: int) -> str:
        try:
            headers = {
                'authorization': f'Bearer {token}',
                'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36',
            }
            
            # 1. بدء عملية التعدين
            mining_url = 'https://api.unich.com/airdrop/user/v1/mining/start'
            mining_resp = requests.post(mining_url, headers=headers)
            
            # 2. المطالبة بالمهام الاجتماعية
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
            
            # 3. جلب معلومات الحساب الكاملة
            info_url = 'https://api.unich.com/airdrop/user/v1/info/my-info'
            info_resp = requests.get(info_url, headers=headers)
            info_data = info_resp.json()
            
            if info_data.get('code') != 'OK':
                return f"الحساب {account_num}: ❌ فشل في جلب المعلومات"
            
            data = info_data.get('data', {})
            
            # معلومات الحساب الأساسية
            email = data.get('email', 'غير معروف')
            mUn = data.get('mUn', 0)
            has_password = "✅" if data.get('hasPassword') else "❌"
            firebase_provider = data.get('firebaseProvider', 'غير معروف')
            
            # معلومات التعدين
            mining_data = data.get('mining', {})
            daily_reward = mining_data.get('dailyReward', 0)
            
            penalty_data = mining_data.get('penalty', {})
            penalty_decrease = penalty_data.get('dailyDecrease', 0)
            missing_days = penalty_data.get('missingDays', 0)
            
            today_mining = mining_data.get('todayMining', {})
            mining_status = "✅ يعمل" if today_mining.get('started') else "❌ متوقف"
            mining_start_time = datetime.fromtimestamp(today_mining.get('startedAt', 0)/1000).strftime('%Y-%m-%d %H:%M:%S') if today_mining.get('startedAt') else 'غير متاح'
            remaining_time = int(today_mining.get('remainingTimeInMillis', 0)) / (1000 * 60 * 60)  # تحويل إلى ساعات
            next_mining = today_mining.get('nextMiningAt', 'غير متاح')
            
            # معلومات الإحالة
            referral_data = data.get('referral', {})
            referral_code = referral_data.get('myReferralCode', 'غير متوفر')
            referral_link = referral_data.get('myReferralLink', '')
            referral_points = referral_data.get('myPoint', 0)
            referral_reward = referral_data.get('reward', 0)
            
            # مكافآت الإحالة
            bonus_info = ""
            bonuses = referral_data.get('bonus', [])
            if bonuses:
                bonus_info = "\n🎁 مكافآت الإحالة:\n"
                for bonus in bonuses:
                    milestone = bonus.get('milestone', 0)
                    reward = bonus.get('reward', 0)
                    bonus_info += f"• عند {milestone} إحالة: {reward} نقطة\n"
            
            # النقاط الإجمالية
            total_points = data.get('point', {}).get('totalPoint', 0)
            
            return (
                f"🔹 الحساب {account_num}:\n"
                f"📧 {email} | 🆔 mUn: {mUn}\n"
                f"🔐 لديه كلمة مرور: {has_password} | 🔥 Firebase: {firebase_provider}\n\n"
                f"⛏️ معلومات التعدين:\n"
                f"• الحالة: {mining_status}\n"
                f"• بدء التعدين: {mining_start_time}\n"
                f"• المكافأة اليومية: {daily_reward} نقطة\n"
                f"• العقوبة اليومية: -{penalty_decrease} نقطة\n"
                f"• أيام الغياب: {missing_days} يوم\n"
                f"• الوقت المتبقي: {remaining_time:.1f} ساعة\n"
                f"• التعدين القادم: {next_mining}\n\n"
                f"📌 المهام الاجتماعية:\n"
                f"• المنجزة مسبقاً: {completed_tasks}\n"
                f"• المطالبة بها الآن: {claimed_tasks}\n\n"
                f"📣 معلومات الإحالة:\n"
                f"• الكود: {referral_code}\n"
                f"• الرابط: {referral_link}\n"
                f"• النقاط الحالية: {referral_points}\n"
                f"• مكافأة الإحالة: {referral_reward} نقطة\n"
                f"• النقاط الإجمالية: {total_points} نقطة"
                f"{bonus_info}"
            )
            
        except Exception as e:
            return f"الحساب {account_num}: ❌ خطأ - {str(e)}"

def main():
    application = Application.builder().token("7875029526:AAGKBUErOXqs4xb_6XnR1whkpegGt6kGKaQ").build()
    
    bot = UnichBot()
    
    # إضافة المعالجات
    application.add_handler(CommandHandler('start', bot.start))
    application.add_handler(CallbackQueryHandler(bot.button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message))
    application.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO | filters.AUDIO, bot.handle_message))
    
    application.run_polling()

if __name__ == '__main__':
    main()
import os
import json
import asyncio
import csv
from datetime import datetime, timedelta
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Загружаем токен из .env
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Папки и файлы данных
DATA_DIR = "data"
CONTACTS_FILE = os.path.join(DATA_DIR, "contacts.json")
REMINDERS_FILE = os.path.join(DATA_DIR, "reminders.json")
EMPLOYEES_CSV = "employees.csv"

os.makedirs(DATA_DIR, exist_ok=True)

# ---------- Работа с JSON (контакты, напоминания) ----------
def load_contacts():
    if os.path.exists(CONTACTS_FILE):
        with open(CONTACTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_contacts(contacts):
    with open(CONTACTS_FILE, "w", encoding="utf-8") as f:
        json.dump(contacts, f, ensure_ascii=False, indent=2)

def load_reminders():
    if os.path.exists(REMINDERS_FILE):
        with open(REMINDERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_reminders(reminders):
    with open(REMINDERS_FILE, "w", encoding="utf-8") as f:
        json.dump(reminders, f, ensure_ascii=False, indent=2)

# ---------- Работа с CSV (сотрудники) ----------
def load_employees():
    employees = []
    if not os.path.exists(EMPLOYEES_CSV):
        return employees
    with open(EMPLOYEES_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            employees.append(row)
    return employees

def search_employee_by_name(name_part):
    employees = load_employees()
    name_part_lower = name_part.lower()
    return [e for e in employees if name_part_lower in e['name'].lower()]

def get_employees_by_department(dept):
    employees = load_employees()
    dept_lower = dept.lower()
    return [e for e in employees if e['department'].lower() == dept_lower]

# ---------- Команды бота ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привет! Я бот-помощник для команды.\n\n"
        "Доступные команды:\n"
        "/help - список всех команд\n"
        "/add_contact - добавить контакт коллеги\n"
        "/contacts - показать все контакты\n"
        "/remind - установить напоминание\n"
        "/daily - ежедневный дайджест\n\n"
        "🆕 Новые команды с данными:\n"
        "/employees - показать всех сотрудников из CSV\n"
        "/searchemployee <имя> - поиск сотрудника\n"
        "/department <отдел> - сотрудники отдела"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📋 *Список команд:*\n\n"
        "/start - приветствие\n"
        "/help - эта справка\n"
        "/add_contact - добавить контакт\n"
        "/contacts - список контактов\n"
        "/remind <минуты> <текст> - напоминание\n"
        "/daily - дайджест\n"
        "/employees - показать всех сотрудников\n"
        "/searchemployee <имя> - поиск по имени\n"
        "/department <отдел> - сотрудники отдела (IT, HR, Sales, Marketing)"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

async def add_contact_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['add_contact_step'] = 'name'
    await update.message.reply_text("Введите имя коллеги:")

async def handle_add_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    step = context.user_data.get('add_contact_step')
    if step == 'name':
        context.user_data['new_contact'] = {'name': update.message.text}
        context.user_data['add_contact_step'] = 'position'
        await update.message.reply_text("Введите должность:")
    elif step == 'position':
        context.user_data['new_contact']['position'] = update.message.text
        context.user_data['add_contact_step'] = 'phone'
        await update.message.reply_text("Введите номер телефона:")
    elif step == 'phone':
        context.user_data['new_contact']['phone'] = update.message.text
        context.user_data['add_contact_step'] = 'email'
        await update.message.reply_text("Введите email:")
    elif step == 'email':
        context.user_data['new_contact']['email'] = update.message.text
        contacts = load_contacts()
        contacts.append(context.user_data['new_contact'])
        save_contacts(contacts)
        context.user_data.pop('add_contact_step')
        context.user_data.pop('new_contact')
        await update.message.reply_text("✅ Контакт добавлен!")

async def show_contacts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contacts = load_contacts()
    if not contacts:
        await update.message.reply_text("📭 Список контактов пуст.")
        return
    text = "📋 *Список контактов:*\n\n"
    for idx, c in enumerate(contacts, 1):
        text += f"{idx}. *{c['name']}*\n   {c['position']}\n   📞 {c['phone']}\n   ✉️ {c['email']}\n\n"
    await update.message.reply_text(text, parse_mode="Markdown")

async def remind(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("❌ Использование: /remind <минуты> <текст>\nПример: /remind 5 Позвонить Ивану")
        return
    try:
        minutes = int(context.args[0])
        if minutes <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Укажите положительное число минут.")
        return
    reminder_text = " ".join(context.args[1:])
    remind_at = datetime.now() + timedelta(minutes=minutes)
    reminder = {
        "user_id": update.effective_user.id,
        "chat_id": update.effective_chat.id,
        "text": reminder_text,
        "remind_at": remind_at.isoformat(),
        "created_at": datetime.now().isoformat()
    }
    reminders = load_reminders()
    reminders.append(reminder)
    save_reminders(reminders)
    await update.message.reply_text(f"⏰ Напоминание установлено на {remind_at.strftime('%H:%M:%S')} (через {minutes} мин).")

async def daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contacts = load_contacts()
    reminders = load_reminders()
    today = datetime.now().date()
    today_reminders = [r for r in reminders if datetime.fromisoformat(r['remind_at']).date() == today]
    msg = f"📅 *Дайджест на {today.strftime('%d.%m.%Y')}*\n\n"
    msg += f"👥 Контактов в базе: {len(contacts)}\n"
    msg += f"⏰ Напоминаний на сегодня: {len(today_reminders)}\n"
    if today_reminders:
        msg += "\n*Ближайшие напоминания:*\n"
        for r in today_reminders[:5]:
            msg += f"• {r['text']} в {datetime.fromisoformat(r['remind_at']).strftime('%H:%M')}\n"
    await update.message.reply_text(msg, parse_mode="Markdown")

async def show_employees(update: Update, context: ContextTypes.DEFAULT_TYPE):
    employees = load_employees()
    if not employees:
        await update.message.reply_text("❌ Файл employees.csv не найден или пуст. Добавьте данные.")
        return
    text = "👥 *Список сотрудников компании:*\n\n"
    for emp in employees:
        text += f"• *{emp['name']}*\n  Отдел: {emp['department']}\n  Должность: {emp['role']}\n  Email: {emp['email']}\n\n"
    await update.message.reply_text(text, parse_mode="Markdown")

async def searchemployee(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Укажите имя для поиска.\nПример: /searchemployee Иван")
        return
    query = " ".join(context.args)
    results = search_employee_by_name(query)
    if not results:
        await update.message.reply_text(f"🔍 Сотрудник с именем «{query}» не найден.")
        return
    text = f"🔎 *Результаты поиска по запросу «{query}»:*\n\n"
    for emp in results:
        text += f"• *{emp['name']}*\n  Отдел: {emp['department']}\n  Должность: {emp['role']}\n  Email: {emp['email']}\n\n"
    await update.message.reply_text(text, parse_mode="Markdown")

async def department_employees(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Укажите название отдела.\nПример: /department IT")
        return
    dept = " ".join(context.args)
    results = get_employees_by_department(dept)
    if not results:
        await update.message.reply_text(f"🔍 Отдел «{dept}» не найден или в нём нет сотрудников.")
        return
    text = f"🏢 *Сотрудники отдела {dept.capitalize()}:*\n\n"
    for emp in results:
        text += f"• *{emp['name']}*\n  Должность: {emp['role']}\n  Email: {emp['email']}\n\n"
    await update.message.reply_text(text, parse_mode="Markdown")

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤔 Неизвестная команда. Введите /help для списка команд.")

# ---------- Фоновая задача для напоминаний ----------
async def check_reminders(app: Application):
    while True:
        reminders = load_reminders()
        now = datetime.now()
        changed = False
        for r in reminders[:]:
            remind_at = datetime.fromisoformat(r['remind_at'])
            if remind_at <= now:
                try:
                    await app.bot.send_message(chat_id=r['chat_id'], text=f"🔔 *Напоминание:* {r['text']}", parse_mode="Markdown")
                except Exception as e:
                    print(f"Ошибка отправки: {e}")
                reminders.remove(r)
                changed = True
        if changed:
            save_reminders(reminders)
        await asyncio.sleep(30)

# ---------- Запуск бота ----------
def main():
    if not BOT_TOKEN:
        raise ValueError("Токен не найден. Создайте файл .env с BOT_TOKEN=ваш_токен")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("add_contact", add_contact_start))
    app.add_handler(CommandHandler("contacts", show_contacts))
    app.add_handler(CommandHandler("remind", remind))
    app.add_handler(CommandHandler("daily", daily))
    app.add_handler(CommandHandler("employees", show_employees))
    app.add_handler(CommandHandler("searchemployee", searchemployee))
    app.add_handler(CommandHandler("department", department_employees))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_add_contact))
    app.add_handler(MessageHandler(filters.COMMAND, unknown))
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.create_task(check_reminders(app))
    print("✅ Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()
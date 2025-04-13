import os
import psycopg2
import openai
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler

CREATE TABLE users (
  chat_id BIGINT PRIMARY KEY,
  name TEXT,
  emoji TEXT,
  karma INT,
  muting BOOLEAN,
  role TEXT
);

# ENV
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

# Роли и уровни
roles = [
    ("Halcón", 0, 800, ""),
    ("Soldado", 800, 1250, "может использовать /all"),
    ("Cobrador", 1250, 2000, "может призывать"),
    ("Reclutador", 2000, 3000, "может призывать и приглашать"),
    ("Sicario", 3000, 4250, "может выдавать мут"),
    ("Químico", 4250, 5600, "может выдавать мут"),
    ("Contador", 5600, 6666, "может выдавать мут"),
    ("Narcobaron", 6666, 999999, "может кикать"),
]

# Подключение к базе
def db():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASS")
    )

# Получить роль по карме
def get_role(karma):
    for name, low, high, _ in roles:
        if low <= karma < high:
            return name
    return "Halcón"

# Регистрация пользователя
def ensure_user(chat_id):
    with db() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM users WHERE chat_id=%s", (chat_id,))
        if not cur.fetchone():
            cur.execute("INSERT INTO users (chat_id, karma, emoji, muting, role) VALUES (%s, 0, '🧨', false, 'Halcón')", (chat_id,))

# Обновить роль и прислать поздравление
async def update_user_role(chat_id, karma, context):
    new_role = get_role(karma)
    with db() as conn, conn.cursor() as cur:
        cur.execute("SELECT role FROM users WHERE chat_id=%s", (chat_id,))
        result = cur.fetchone()
        if result and result[0] != new_role:
            cur.execute("UPDATE users SET role=%s WHERE chat_id=%s", (new_role, chat_id))
            for role in roles:
                if role[0] == new_role:
                    rights = role[3]
                    break
            await context.bot.send_message(chat_id, f"🎉 Поздравляем, вы теперь {new_role}!\nУ вас появились новые возможности: {rights}")
def ensure_user(chat_id):
    with db() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM users WHERE chat_id=%s", (chat_id,))
        if not cur.fetchone():
            cur.execute("INSERT INTO users (chat_id, karma, emoji, muting, role) VALUES (%s, 0, '🧨', false, 'Halcón')", (chat_id,))

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    ensure_user(chat_id)
    await update.message.reply_text("Hola! Я CartelBot! 💼")

# /setname
async def setname(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    name = " ".join(context.args)
    if name:
        with db() as conn, conn.cursor() as cur:
            cur.execute("UPDATE users SET name=%s WHERE chat_id=%s", (name, chat_id))
        await update.message.reply_text(f"Позывной обновлён: {name}")

# /setemoji
async def setemoji(update: Update, context: ContextTypes.DEFAULT_TYPE):
    emoji = " ".join(context.args)
    chat_id = update.message.chat_id
    if emoji:
        with db() as conn, conn.cursor() as cur:
            cur.execute("UPDATE users SET emoji=%s WHERE chat_id=%s", (emoji, chat_id))
        await update.message.reply_text(f"Эмоджи обновлён: {emoji}")

# /whoami
async def whoami(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    target_id = int(context.args[0]) if context.args else chat_id
    with db() as conn, conn.cursor() as cur:
        cur.execute("SELECT name, emoji, karma, role FROM users WHERE chat_id=%s", (target_id,))
        res = cur.fetchone()
    if res:
        name, emoji, karma, role = res
        await update.message.reply_text(f"👤 Информация:\nИмя: {name}\nСмайлик: {emoji}\nКарма: {karma}\nРоль: {role}")
    else:
        await update.message.reply_text("Пользователь не найден.")

# /settings
async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("""
🛠 Настройки:
/setname <имя> — сменить позывной
/setemoji <emoji> — сменить смайлик призыва
/whoami [id] — информация о пользователе
/muteping — выйти из призыва
""")

# /muteping
async def muteping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    with db() as conn, conn.cursor() as cur:
        cur.execute("UPDATE users SET muting = true WHERE chat_id=%s", (chat_id,))
    await update.message.reply_text("Вы больше не будете получать призывы.")

# /famili
async def famili(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with db() as conn, conn.cursor() as cur:
        cur.execute("SELECT name, role FROM users WHERE karma > 2000")
        users = cur.fetchall()
    if users:
        text = "\n".join([f"• {u[0]} — {u[1]}" for u in users])
    else:
        text = "Никого нет выше уровня 4."
    await update.message.reply_text("👥 Familia:\n" + text)

# /all
async def all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with db() as conn, conn.cursor() as cur:
        cur.execute("SELECT name, emoji FROM users WHERE muting = false")
        users = cur.fetchall()
    mentions = " ".join([f"{emoji} {name}" for name, emoji in users])
    await update.message.reply_text("📢 Призыв: " + mentions)

# /gpt
async def gpt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = " ".join(context.args)
    if not prompt:
        return await update.message.reply_text("Укажи запрос.")
    response = openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=[{"role": "user", "content": prompt}])
    await update.message.reply_text(response["choices"][0]["message"]["content"])

# /image
async def image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = " ".join(context.args)
    if not prompt:
        return await update.message.reply_text("Укажи описание изображения.")
    image = openai.Image.create(prompt=prompt, n=1, size="512x512")
    await update.message.reply_photo(photo=image['data'][0]['url'])

# /rep
async def rep(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if context.args and context.args[0].startswith('+'):
        target = int(context.args[0][1:])
        change = 50
    elif context.args and context.args[0].startswith('-'):
        target = int(context.args[0][1:])
        change = -50
    else:
        return await update.message.reply_text("Формат: /rep +id или /rep -id")
    with db() as conn, conn.cursor() as cur:
        cur.execute("UPDATE users SET karma = karma + %s WHERE chat_id=%s", (change, target))
    await update.message.reply_text("Рейтинг обновлён.")
    await update_user_role(target, change, context)

# Автокарма в 00:00 МСК
def daily_karma():
    with db() as conn, conn.cursor() as cur:
        cur.execute("UPDATE users SET karma = karma + 10")

# Расписание
scheduler = BackgroundScheduler(timezone="Europe/Moscow")
scheduler.add_job(daily_karma, "cron", hour=0, minute=0)
scheduler.start()

# Запуск
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("setname", setname))
app.add_handler(CommandHandler("setemoji", setemoji))
app.add_handler(CommandHandler("whoami", whoami))
app.add_handler(CommandHandler("settings", settings))
app.add_handler(CommandHandler("muteping", muteping))
app.add_handler(CommandHandler("famili", famili))
app.add_handler(CommandHandler("all", all))
app.add_handler(CommandHandler("gpt", gpt))
app.add_handler(CommandHandler("image", image))
app.add_handler(CommandHandler("rep", rep))

app.run_polling()

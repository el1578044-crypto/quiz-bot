import logging
import os
from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

import quiz_data as qd

logging.basicConfig(
    format="%(asctime)s %(name)s %(levelname)s %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)  # не светить токен в логах
log = logging.getLogger("quiz_bot")


def load_env(path=".env"):
    """Минимальный загрузчик .env (без внешних зависимостей)."""
    p = Path(__file__).with_name(path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


# ---------- клавиатуры ----------
def start_keyboard():
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(qd.START_BUTTON, callback_data="start_quiz")]]
    )


def question_keyboard(q_index):
    rows = [
        [InlineKeyboardButton(opt, callback_data=f"a:{q_index}:{i}")]
        for i, opt in enumerate(qd.QUESTIONS[q_index]["options"])
    ]
    return InlineKeyboardMarkup(rows)


def result_keyboard():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(qd.CTA_BUTTON, url=qd.CTA_URL)],
            [InlineKeyboardButton(qd.RESTART_BUTTON, callback_data="start_quiz")],
        ]
    )


def question_text(q_index):
    total = len(qd.QUESTIONS)
    return f"Вопрос {q_index + 1} из {total}\n\n{qd.QUESTIONS[q_index]['text']}"


# ---------- обработчики ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(qd.GREETING, reply_markup=start_keyboard())


async def start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["answers"] = []
    await query.message.reply_text(question_text(0), reply_markup=question_keyboard(0))


async def answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, q_str, o_str = query.data.split(":")
    q_index, o_index = int(q_str), int(o_str)

    answers = context.user_data.get("answers")
    # Защита от повторных/устаревших нажатий: принимаем только ответ на текущий вопрос
    if answers is None or q_index != len(answers):
        return
    if o_index >= len(qd.QUESTIONS[q_index]["options"]):
        return

    answers.append(o_index)
    chosen = qd.QUESTIONS[q_index]["options"][o_index]
    # Убираем кнопки у отвеченного вопроса и показываем выбранный ответ
    await query.edit_message_text(f"{question_text(q_index)}\n\n✅ {chosen}")

    next_index = q_index + 1
    if next_index < len(qd.QUESTIONS):
        await query.message.reply_text(
            question_text(next_index), reply_markup=question_keyboard(next_index)
        )
    else:
        await query.message.reply_text(
            qd.result_message(answers), reply_markup=result_keyboard()
        )
        context.user_data.pop("answers", None)


def main():
    load_env()
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise SystemExit("Не найден BOT_TOKEN. Укажите его в файле .env")

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(start_quiz, pattern=r"^start_quiz$"))
    app.add_handler(CallbackQueryHandler(answer, pattern=r"^a:\d+:\d+$"))
    log.info("Бот запущен")
    app.run_polling()


if __name__ == "__main__":
    main()

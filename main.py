from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
import asyncio, json, os

TOKEN = "TOKEN"
DATA_FILE = "users.json"

bot = Bot(token=TOKEN)
dp = Dispatcher()
# ====== FSM для подписки ======
class SubscribeForm(StatesGroup):
    waiting_for_count = State()


# ====== Вспомогательные функции ======
def load_data():
    if not os.path.exists(DATA_FILE):
        return {"admins": [], "subscribers": [], "settings": {"price": 0, "link": ""}}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ====== Проверка прав ======
def is_admin(user_id):
    data = load_data()
    return user_id in data["admins"]

# ====== /start ======
@dp.message(Command("start"))
async def start(msg: types.Message):
    user = msg.from_user
    data = load_data()

    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Подписаться")]],
        resize_keyboard=True
    )

    if user.id in [s["id"] for s in data["subscribers"]]:
        await msg.answer("Ты уже в списке подписчиков ✅", reply_markup=kb)
    else:
        await msg.answer("Привет! Нажми «Подписаться», чтобы указать количество своих подписок 👇", reply_markup=kb)

# ====== Подписка ======
@dp.message(F.text.lower() == "подписаться")
async def subscribe(msg: types.Message, state: FSMContext):
    await msg.answer("Введите количество своих подписок (числом):")
    await state.set_state(SubscribeForm.waiting_for_count)

@dp.message(SubscribeForm.waiting_for_count, F.text.regexp(r"^\d+$"))
async def save_subs(msg: types.Message, state: FSMContext):
    count = int(msg.text)
    user = msg.from_user
    data = load_data()

    existing = next((s for s in data["subscribers"] if s["id"] == user.id), None)
    if existing:
        existing["subs"] = count
        text = f"✅ Обновлено количество подписок: {count}"
    else:
        data["subscribers"].append({"id": user.id, "name": user.full_name, "subs": count})
        text = f"🎉 Ты добавлен как подписчик с {count} подписками!"

    save_data(data)
    await msg.answer(text)
    await state.clear()

@dp.message(SubscribeForm.waiting_for_count)
async def invalid_number(msg: types.Message):
    await msg.answer("Пожалуйста, введи число.")

# ====== Админские команды ======
@dp.message(Command("add_sub"))
async def add_subscriber(msg: types.Message):
    if not is_admin(msg.from_user.id):
        return await msg.answer("Нет прав.")
    try:
        _, user_id, name, subs = msg.text.split(" ", 3)
        user_id, subs = int(user_id), int(subs)
    except:
        return await msg.answer("Используй формат: /add_sub <id> <имя> <кол-во подписок>")
    data = load_data()
    data["subscribers"].append({"id": user_id, "name": name, "subs": subs})
    save_data(data)
    await msg.answer(f"✅ Добавлен {name} (ID: {user_id}, подписок: {subs})")

@dp.message(Command("del_sub"))
async def del_subscriber(msg: types.Message):
    if not is_admin(msg.from_user.id):
        return await msg.answer("Нет прав.")
    try:
        _, user_id = msg.text.split(" ", 1)
        user_id = int(user_id)
    except:
        return await msg.answer("Используй формат: /del_sub <id>")
    data = load_data()
    data["subscribers"] = [s for s in data["subscribers"] if s["id"] != user_id]
    save_data(data)
    await msg.answer(f"❌ Подписчик {user_id} удалён")

@dp.message(Command("set_price"))
async def set_price(msg: types.Message):
    if not is_admin(msg.from_user.id):
        return await msg.answer("Нет прав.")
    try:
        _, price = msg.text.split(" ", 1)
        price = int(price)
    except:
        return await msg.answer("Используй формат: /set_price <цена>")
    data = load_data()
    data["settings"]["price"] = price
    save_data(data)
    await msg.answer(f"💰 Установлена цена {price}₽ за подписку")

@dp.message(Command("set_link"))
async def set_link(msg: types.Message):
    if not is_admin(msg.from_user.id):
        return await msg.answer("Нет прав.")
    try:
        _, link = msg.text.split(" ", 1)
    except:
        return await msg.answer("Используй формат: /set_link <ссылка>")
    data = load_data()
    data["settings"]["link"] = link
    save_data(data)
    await msg.answer(f"🔗 Установлена ссылка: {link}")

@dp.message(Command("send_pay"))
async def send_pay(msg: types.Message):
    if not is_admin(msg.from_user.id):
        return await msg.answer("Нет прав.")
    data = load_data()
    total_sum, link = data["settings"]["price"], data["settings"]["link"]
    if total_sum == 0 or not link:
        return await msg.answer("Сначала установи /set_price (общая сумма) и /set_link")

    subscribers = data["subscribers"]
    if not subscribers:
        return await msg.answer("Список подписчиков пуст.")

    # 1️⃣ Считаем общее количество подписок
    total_subs = sum(s["subs"] for s in subscribers)
    if total_subs == 0:
        return await msg.answer("Общее количество подписок = 0. Проверь данные.")

    # 2️⃣ Считаем стоимость одной подписки
    price_per_sub = total_sum / total_subs

    # 3️⃣ Рассылаем каждому
    sent = 0
    for sub in subscribers:
        user_total = round(price_per_sub * sub["subs"], 2)
        text = (
            f"💸 Привет, {sub['name']}!\n\n"
            f"Общая сумма сервера в этом месяце: {total_sum}₽\n"
            f"Твоя доля ({sub['subs']} подписок): <b>{user_total}₽</b>\n"
            f"Ссылка на оплату: {link}"
        )
        try:
            await bot.send_message(sub["id"], text, parse_mode="HTML")
            sent += 1
        except Exception:
            pass

    await msg.answer(
        f"✅ Сообщения отправлены {sent} подписчикам\n\n"
        f"Всего подписок: {total_subs}\n"
        f"Цена одной подписки: {round(price_per_sub, 2)}₽"
    )

@dp.message(Command("list"))
async def list_subs(msg: types.Message):
    if not is_admin(msg.from_user.id):
        return await msg.answer("Нет прав.")
    data = load_data()
    text = "📋 Подписчики:\n"
    for s in data["subscribers"]:
        text += f"{s['name']} — {s['subs']} подписок (ID {s['id']})\n"
    await msg.answer(text or "Список пуст.")

# ====== Запуск ======
async def main():
    print("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

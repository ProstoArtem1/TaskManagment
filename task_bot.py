import asyncio
import json
import os
from datetime import datetime

import aiosqlite
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BufferedInputFile, Document, KeyboardButton, Message, ReplyKeyboardMarkup
from dotenv import load_dotenv

load_dotenv()


class Task:
    def __init__(self, title, priority, due_date):
        self.title = title
        self.priority = priority
        self.due_date = due_date

    def to_dict(self):
        return {
            'title': self.title,
            'priority': self.priority,
            'due_date': self.due_date
        }

    def __str__(self):
        return f'[{self.priority}] {self.title} (до {self.due_date})'


class TaskManager:
    def __init__(self, db_name='tasks.db'):
        self.db_name = db_name

    async def init_db(self):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    priority INTEGER NOT NULL,
                    due_date TEXT NOT NULL
                )
            ''')
            await db.commit()

    async def add_task(self, user_id, title, priority, due_date):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute('''
                INSERT INTO tasks (user_id, title, priority, due_date) VALUES (?, ?, ?, ?)
            ''', (user_id, title, priority, due_date))
            await db.commit()

    async def get_tasks(self, user_id):
        async with aiosqlite.connect(self.db_name) as db:
            async with db.execute(
                'SELECT title, priority, due_date FROM tasks WHERE user_id = ?', (user_id,)
            ) as cursor:
                rows = await cursor.fetchall()
        return [Task(title, priority, due_date) for title, priority, due_date in rows]

    async def delete_task(self, user_id, task):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute('''
                DELETE FROM tasks WHERE user_id = ? AND title = ? AND priority = ? AND due_date = ?
            ''', (user_id, task.title, task.priority, task.due_date))
            await db.commit()

    async def sort_by_priority(self, user_id):
        tasks = await self.get_tasks(user_id)
        return sorted(tasks, key=lambda t: t.priority)

    async def search_by_keyword(self, user_id, keyword):
        tasks = await self.get_tasks(user_id)
        return [t for t in tasks if keyword.lower() in t.title.lower()]

    def is_overdue(self, task):
        try:
            due_date = datetime.strptime(task.due_date, "%Y-%m-%d")
        except ValueError:
            return False
        return datetime.now() > due_date

    async def get_overdue_tasks(self, user_id):
        tasks = await self.get_tasks(user_id)
        return [t for t in tasks if self.is_overdue(t)]

    async def clear_tasks(self, user_id):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute('DELETE FROM tasks WHERE user_id = ?', (user_id,))
            await db.commit()


task_manager = TaskManager()
router = Router()


class AddTaskForm(StatesGroup):
    title = State()
    priority = State()
    due_date = State()


class SearchForm(StatesGroup):
    keyword = State()


class ImportForm(StatesGroup):
    file = State()


def main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Добавить задачу"), KeyboardButton(text="Показать все задачи")],
            [KeyboardButton(text="Поиск по ключевому слову"), KeyboardButton(text="Просроченные задачи")],
            [KeyboardButton(text="Сохранить в файл"), KeyboardButton(text="Загрузить из файла")],
            [KeyboardButton(text="Очистить всё")]
        ],
        resize_keyboard=True
    )


def format_task(task_manager_instance, task):
    line = str(task)
    if task_manager_instance.is_overdue(task):
        line += " — просрочена"
    return line


@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "Привет! Я бот для управления задачами.\nВыберите действие на клавиатуре ниже:",
        reply_markup=main_keyboard()
    )


@router.message(Command("add"))
@router.message(F.text == "Добавить задачу")
async def start_add_task(message: Message, state: FSMContext):
    await state.set_state(AddTaskForm.title)
    await message.answer("Введите название задачи:")


@router.message(AddTaskForm.title)
async def process_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text)
    await state.set_state(AddTaskForm.priority)
    await message.answer("Введите приоритет задачи (1-5):")


@router.message(AddTaskForm.priority)
async def process_priority(message: Message, state: FSMContext):
    if not message.text.isdigit() or not (1 <= int(message.text) <= 5):
        await message.answer("Приоритет должен быть числом от 1 до 5. Попробуйте снова:")
        return
    await state.update_data(priority=int(message.text))
    await state.set_state(AddTaskForm.due_date)
    await message.answer("Введите срок выполнения в формате ГГГГ-ММ-ДД:")


@router.message(AddTaskForm.due_date)
async def process_due_date(message: Message, state: FSMContext):
    try:
        datetime.strptime(message.text, "%Y-%m-%d")
    except ValueError:
        await message.answer("Неверный формат даты. Введите в формате ГГГГ-ММ-ДД:")
        return
    data = await state.get_data()
    await task_manager.add_task(message.from_user.id, data["title"], data["priority"], message.text)
    await state.clear()
    await message.answer(f"Задача '{data['title']}' успешно добавлена.", reply_markup=main_keyboard())


@router.message(Command("list"))
@router.message(F.text == "Показать все задачи")
async def list_tasks(message: Message):
    tasks = await task_manager.get_tasks(message.from_user.id)
    if not tasks:
        await message.answer("У вас нет задач.")
        return
    lines = [format_task(task_manager, t) for t in tasks]
    await message.answer("\n".join(lines))


@router.message(Command("search"))
@router.message(F.text == "Поиск по ключевому слову")
async def start_search(message: Message, state: FSMContext):
    await state.set_state(SearchForm.keyword)
    await message.answer("Введите ключевое слово для поиска:")


@router.message(SearchForm.keyword)
async def process_search(message: Message, state: FSMContext):
    keyword = message.text
    tasks = await task_manager.search_by_keyword(message.from_user.id, keyword)
    await state.clear()
    if not tasks:
        await message.answer(f"Задачи с ключевым словом '{keyword}' не найдены.", reply_markup=main_keyboard())
        return
    lines = [format_task(task_manager, t) for t in tasks]
    await message.answer("\n".join(lines), reply_markup=main_keyboard())


@router.message(Command("overdue"))
@router.message(F.text == "Просроченные задачи")
async def overdue_tasks(message: Message):
    tasks = await task_manager.get_overdue_tasks(message.from_user.id)
    if not tasks:
        await message.answer("Просроченных задач нет.")
        return
    lines = [f"Просроченная задача: {t}" for t in tasks]
    await message.answer("\n".join(lines))


@router.message(Command("export"))
@router.message(F.text == "Сохранить в файл")
async def export_tasks(message: Message):
    tasks = await task_manager.get_tasks(message.from_user.id)
    if not tasks:
        await message.answer("Нет задач для сохранения.")
        return
    data = json.dumps([t.to_dict() for t in tasks], ensure_ascii=False, indent=4)
    file = BufferedInputFile(data.encode("utf-8"), filename="tasks.json")
    await message.answer_document(file)


@router.message(Command("import"))
@router.message(F.text == "Загрузить из файла")
async def start_import(message: Message, state: FSMContext):
    await state.set_state(ImportForm.file)
    await message.answer("Отправьте файл tasks.json с задачами.")


@router.message(ImportForm.file, F.document)
async def process_import(message: Message, state: FSMContext, bot: Bot):
    document: Document = message.document
    file_info = await bot.get_file(document.file_id)
    file_bytes = await bot.download_file(file_info.file_path)
    await state.clear()
    try:
        tasks_list = json.loads(file_bytes.read().decode("utf-8"))
    except Exception as e:
        await message.answer(f"Ошибка чтения файла: {e}", reply_markup=main_keyboard())
        return
    added = 0
    overdue_count = 0
    for task_dict in tasks_list:
        new_task = Task(task_dict['title'], task_dict['priority'], task_dict['due_date'])
        await task_manager.add_task(message.from_user.id, new_task.title, new_task.priority, new_task.due_date)
        if task_manager.is_overdue(new_task):
            overdue_count += 1
        added += 1
    await message.answer(
        f"Загружено задач: {added}. Из них просрочено: {overdue_count}.",
        reply_markup=main_keyboard()
    )


@router.message(ImportForm.file)
async def process_import_wrong_type(message: Message):
    await message.answer("Пожалуйста, отправьте файл с задачами в формате JSON.")


@router.message(Command("clear"))
@router.message(F.text == "Очистить всё")
async def clear_tasks(message: Message):
    await task_manager.clear_tasks(message.from_user.id)
    await message.answer("Все ваши задачи очищены.", reply_markup=main_keyboard())


async def main():
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("Не задан токен бота. Установите переменную окружения BOT_TOKEN.")
    bot = Bot(token=token)
    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher.include_router(router)
    await task_manager.init_db()
    await dispatcher.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
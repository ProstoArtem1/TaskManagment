from datetime import datetime

from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from database import (
    add_task,
    clear_history,
    complete_task,
    delete_task,
    get_completed_tasks,
    get_user_tasks,
    restore_task,
)
from keyboards import get_history_keyboard, get_main_keyboard

router = Router()


class AddTask(StatesGroup):
    title = State()
    priority = State()
    deadline = State()


async def get_tasks_keyboard(tasks):
    inline_keyboard = []
    for task in tasks:
        task_id, title, priority, deadline, _ = task
        button_done = InlineKeyboardButton(
            text=f" {title} (Приоритет: {priority}, Срок: {deadline})",
            callback_data=f"done:{task_id}",
        )
        button_delete = InlineKeyboardButton(
            text=" Удалить", callback_data=f"delete:{task_id}"
        )
        inline_keyboard.append([button_done, button_delete])
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


@router.message(Command("start"))
async def start_cmd(message: types.Message):
    await message.answer(
        "Привет! Я твой менеджер задач. Используй кнопки меню ниже для навигации:",
        reply_markup=get_main_keyboard(),
    )


@router.message(F.text == "Добавить задачу")
@router.message(Command("add"))
async def add_task_start(message: types.Message, state: FSMContext):
    await message.answer("Введите название задачи:")
    await state.set_state(AddTask.title)


@router.message(AddTask.title)
async def add_task_title(message: types.Message, state: FSMContext):
    await state.update_data(title=message.text)
    await message.answer("Введите приоритет задачи (1-5):")
    await state.set_state(AddTask.priority)


@router.message(AddTask.priority)
async def add_task_priority(message: types.Message, state: FSMContext):
    try:
        priority = int(message.text)
        if priority < 1 or priority > 5:
            raise ValueError
    except ValueError:
        await message.answer(
            "Приоритет должен быть числом от 1 до 5. Попробуйте снова:"
        )
        return

    await state.update_data(priority=priority)
    # Запрашиваем дату И время
    await message.answer(
        "Введите срок выполнения задачи в формате **ГГГГ-ММ-ДД ЧЧ:ММ** (например, `2026-09-25 18:30`):",
        parse_mode="Markdown",
    )
    await state.set_state(AddTask.deadline)


@router.message(AddTask.deadline)
async def add_task_deadline(message: types.Message, state: FSMContext):
    user_input = message.text.strip()

    try:
        deadline_dt = datetime.strptime(user_input, "%Y-%m-%d %H:%M")
        deadline_iso = deadline_dt.isoformat()
    except ValueError:
        await message.answer(
            " Неверный формат! Введите дату и время в формате **ГГГГ-ММ-ДД ЧЧ:ММ** (например, `2026-09-25 18:30`):",
            parse_mode="Markdown",
        )
        return

    data = await state.get_data()
    title = data["title"]
    priority = data["priority"]
    user_id = message.from_user.id

    await add_task(user_id, title, priority, deadline_iso)
    await message.answer(
        f"Задача '{title}' с приоритетом {priority} и сроком {user_input} успешно добавлена!",
        reply_markup=get_main_keyboard(),
    )
    await state.clear()


@router.message(F.text == "Мои задачи")
@router.message(Command("tasks"))
async def show_tasks(message: types.Message):
    tasks = await get_user_tasks(message.from_user.id)
    if not tasks:
        await message.answer("У вас нет активных задач.")
        return
    keyboard = await get_tasks_keyboard(tasks)
    await message.answer(
        "Ваши активные задачи (отсортированы по приоритету):",
        reply_markup=keyboard,
    )


@router.callback_query(F.data.startswith("done:"))
async def complete_task_callback(callback: CallbackQuery):
    task_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id

    if await complete_task(task_id, user_id):
        await callback.answer("Задача перенесена в архив!")
        tasks = await get_user_tasks(user_id)
        if tasks:
            new_keyboard = await get_tasks_keyboard(tasks)
            await callback.message.edit_reply_markup(reply_markup=new_keyboard)
        else:
            await callback.message.edit_text("Все задачи выполнены!")
    else:
        await callback.answer("Не удалось завершить задачу.")


@router.callback_query(F.data.startswith("delete:"))
async def delete_task_callback(callback: CallbackQuery):
    task_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id

    await delete_task(task_id, user_id)
    await callback.answer("Задача удалена.")

    tasks = await get_user_tasks(user_id)
    if tasks:
        new_keyboard = await get_tasks_keyboard(tasks)
        await callback.message.edit_reply_markup(reply_markup=new_keyboard)
    else:
        await callback.message.edit_text("Все задачи удалены или выполнены.")


@router.message(F.text == "История")
@router.message(Command("history"))
async def show_history(message: types.Message):
    tasks = await get_completed_tasks(message.from_user.id)
    if not tasks:
        await message.answer("У вас нет выполненных задач в архиве.")
        return

    keyboard = get_history_keyboard(tasks)
    await message.answer("Архив выполненных задач:", reply_markup=keyboard)


@router.callback_query(F.data.startswith("restore:"))
async def function_restore(callback: CallbackQuery):
    task_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id

    await restore_task(task_id, user_id)
    await callback.answer("Задача восстановлена!")

    tasks = await get_completed_tasks(user_id)
    if tasks:
        new_keyboard = get_history_keyboard(tasks)
        await callback.message.edit_reply_markup(reply_markup=new_keyboard)
    else:
        await callback.message.edit_text("Архив задач пуст.")


@router.callback_query(F.data == "clear_history")
async def clear_history_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    deleted_count = await clear_history(user_id)

    if deleted_count > 0:
        await callback.answer(f"Удалено задач: {deleted_count}")
        await callback.message.edit_text("Архив выполненных задач очищен.")
    else:
        await callback.answer("Архив уже пуст.")
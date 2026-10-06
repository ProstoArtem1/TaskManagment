from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

#  основная функция меню
def get_main_keyboard():
  keyboard = [
      [
          KeyboardButton(text="Добавить задачу"),
          KeyboardButton(text="Мои задачи"),
      ],
      [KeyboardButton(text="История")],
  ]
  return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def get_history_keyboard(tasks):
  inline_keyboard = []
  for task in tasks:
    task_id, title, priority, deadline, _ = task
    button = InlineKeyboardButton(
        text=f" {title}", callback_data=f"restore:{task_id}"
    )
    inline_keyboard.append([button])

  clear_button = InlineKeyboardButton(
      text="Очистить архив", callback_data="clear_history"
  )
  inline_keyboard.append([clear_button])

  return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)
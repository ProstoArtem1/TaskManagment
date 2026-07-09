Task Manager Bot

Telegram-бот для управления задачами: добавление, поиск по ключевому слову, просмотр просроченных задач, экспорт и импорт задач в формате JSON.

Возможности


Добавление задачи (название, приоритет 1-5, срок выполнения)
Просмотр всех задач
Поиск задач по ключевому слову
Просмотр просроченных задач
Сохранение задач в файл и загрузка из файла
Очистка всех задач
Данные каждого пользователя хранятся отдельно


Установка

git clone https://github.com/ProstoArtem1/TaskManagment.git
cd TaskManagment
pip install -r requirements.txt

Настройка

Скопируйте .env.example в .env и впишите токен бота, полученный у @BotFather:

cp .env.example .env

Запуск

python task_bot.py

Стек


Python 3.12
aiogram 3
aiosqlite
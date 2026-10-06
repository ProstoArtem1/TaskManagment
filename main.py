import asyncio
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher
from config import BOT_TOKEN
from database import init_db, get_tasks_for_reminder, mark_reminder_sent
from handlers import router

REMINDER_MINUTES = 10  

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


async def reminder_loop(bot: Bot):
    while True:
        try:
            tasks = await get_tasks_for_reminder(REMINDER_MINUTES)
            now = datetime.now()
            for task_id, user_id, title, deadline_str in tasks:
                try:
                    deadline = datetime.fromisoformat(deadline_str)
                except (ValueError, TypeError):
                    continue

                if (
                    timedelta(0)
                    <= deadline - now
                    <= timedelta(minutes=REMINDER_MINUTES)
                ):
                    try:
                        await bot.send_message(
                            user_id, f" Напоминаю: '{title}' скоро дедлайн!"
                        )
                        await mark_reminder_sent(task_id)
                    except Exception as e:
                        print(f"Ошибка при отправке напоминания: {e}")
        except Exception as e:
            print(f"Ошибка в цикле напоминаний: {e}")

        await asyncio.sleep(60)


async def main():
    await init_db()
    dp.include_router(router)
    await bot.delete_webhook(drop_pending_updates=True)
    asyncio.create_task(reminder_loop(bot))
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
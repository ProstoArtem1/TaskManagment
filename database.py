import aiosqlite

DB_NAME = "tasks.db"


async def init_db():
  async with aiosqlite.connect(DB_NAME) as db:
    await db.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                priority INTEGER NOT NULL,
                deadline TEXT NOT NULL,
                is_completed INTEGER DEFAULT 0
            )
        """)

    cursor = await db.execute("PRAGMA table_info(tasks)")
    columns = [row[1] for row in await cursor.fetchall()]

    if "is_completed" not in columns:
      await db.execute(
          "ALTER TABLE tasks ADD COLUMN is_completed INTEGER DEFAULT 0"
      )

    cursor = await db.execute("PRAGMA table_info(tasks)")
    columns = [row[1] for row in await cursor.fetchall()]
    if "reminder_sent" not in columns:
        await db.execute(
        "ALTER TABLE tasks ADD COLUMN reminder_sent INTEGER DEFAULT 0"
    )
    await db.commit()


async def get_tasks_for_reminder(minutes: int):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT id, user_id, title, deadline FROM tasks WHERE is_completed = 0 AND (reminder_sent IS NULL OR reminder_sent = 0)"
        ) as cursor:
            return await cursor.fetchall()

async def mark_reminder_sent(task_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "UPDATE tasks SET reminder_sent = 1 WHERE id = ?", (task_id,)
        )
        await db.commit()


async def add_task(
    user_id: int, title: str, priority: int, deadline: str
) -> None:
  async with aiosqlite.connect(DB_NAME) as db:
    await db.execute(
        "INSERT INTO tasks (user_id, title, priority, deadline) VALUES (?, ?,"
        " ?, ?)",
        (user_id, title, priority, deadline),
    )
    await db.commit()


async def get_user_tasks(user_id):
  async with aiosqlite.connect(DB_NAME) as db:
    cursor = await db.execute(
        """
            SELECT id, title, priority, deadline, is_completed 
            FROM tasks 
            WHERE user_id = ? AND is_completed = 0
            ORDER BY priority DESC
        """,
        (user_id,),
    )
    return await cursor.fetchall()


async def complete_task(task_id: int, user_id: int) -> bool:
  async with aiosqlite.connect(DB_NAME) as db:
    cursor = await db.execute(
        "UPDATE tasks SET is_completed = 1 WHERE id = ? AND user_id = ?",
        (task_id, user_id),
    )
    await db.commit()
    return cursor.rowcount > 0


async def delete_task(task_id: int, user_id: int) -> bool:
  async with aiosqlite.connect(DB_NAME) as db:
    cursor = await db.execute(
        "DELETE FROM tasks WHERE id = ? AND user_id = ?", (task_id, user_id)
    )
    await db.commit()
    return cursor.rowcount > 0

async def get_completed_tasks(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
          "SELECT id, title, priority, deadline, is_completed FROM tasks WHERE user_id = ? AND is_completed = 1 ORDER BY id DESC", 
          (user_id,),
        ) as cursor:
          return await cursor.fetchall()

async def restore_task(task_id: int, user_id: int) -> bool:
  async with aiosqlite.connect(DB_NAME) as db:
    cursor = await db.execute(
      "UPDATE tasks SET is_completed = 0 WHERE id = ? AND user_id = ?", (task_id, user_id),
    )
    await db.commit()
    return cursor.rowcount > 0

async def clear_history(user_id: int) -> int:
  async with aiosqlite.connect(DB_NAME) as db:
    cursor = await db.execute(
      "DELETE FROM tasks WHERE user_id = ? and is_completed = 1",
      (user_id,),
    )
    await db.commit()
    return cursor.rowcount 
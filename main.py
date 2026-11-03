import os
from contextlib import closing
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import psycopg2
from psycopg2.extras import RealDictCursor

BASE_DIR = Path(__file__).parent

app = FastAPI(title="To-Do List")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

# Функция для получения соединения с БД
def get_conn():
    # Vercel автоматически предоставляет переменную POSTGRES_URL при создании БД в панели
    connection_string = os.environ.get("POSTGRES_URL")
    if not connection_string:
        raise RuntimeError("Переменная окружения POSTGRES_URL не установлена")
    
    # Используем RealDictCursor, чтобы строки возвращались как словари (аналог sqlite3.Row)
    conn = psycopg2.connect(connection_string, cursor_factory=RealDictCursor)
    return conn

# Инициализация таблицы при запуске
@app.on_event("startup")
def init_db() -> None:
    with closing(get_conn()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id SERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    done BOOLEAN NOT NULL DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.commit()

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    with closing(get_conn()) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, title, done FROM tasks ORDER BY done ASC, id DESC")
            tasks = cur.fetchall()
    return templates.TemplateResponse(
        "index.html", {"request": request, "tasks": tasks}
    )

@app.post("/add")
def add_task(title: str = Form(...)):
    title = title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="Пустая задача")
    with closing(get_conn()) as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO tasks (title) VALUES (%s)", (title,))
            conn.commit()
    return RedirectResponse(url="/", status_code=303)

@app.post("/toggle/{task_id}")
def toggle_task(task_id: int):
    with closing(get_conn()) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT done FROM tasks WHERE id = %s", (task_id,))
            row = cur.fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="Задача не найдена")
            
            new_done = not row["done"]
            cur.execute("UPDATE tasks SET done = %s WHERE id = %s", (new_done, task_id))
            conn.commit()
    return RedirectResponse(url="/", status_code=303)

@app.post("/delete/{task_id}")
def delete_task(task_id: int):
    with closing(get_conn()) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM tasks WHERE id = %s", (task_id,))
            conn.commit()
    return RedirectResponse(url="/", status_code=303)

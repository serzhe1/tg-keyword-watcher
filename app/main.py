from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import db
from app.routes import router

app = FastAPI(title="TG Monitor Admin")

app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(router)


@app.on_event("startup")
def on_startup():
    db.init_pool()
    # гарантируем, что базовые строки есть
    _ = db.get_bot_state()
    _ = db.get_app_status()


@app.on_event("shutdown")
def on_shutdown():
    db.close_pool()
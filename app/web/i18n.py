from __future__ import annotations

from urllib.parse import urlencode

from fastapi import Request

SUPPORTED_LANGS = {"ru", "en"}
DEFAULT_LANG = "ru"

TRANSLATIONS: dict[str, dict[str, str]] = {
    "nav.dashboard": {"ru": "Панель", "en": "Dashboard"},
    "nav.keywords": {"ru": "Ключевые слова", "en": "Keywords"},
    "nav.logs": {"ru": "Логи", "en": "Logs"},
    "nav.docs": {"ru": "Инструкция", "en": "Docs"},
    "nav.logout": {"ru": "Выйти", "en": "Logout"},
    "lang.ru": {"ru": "RU", "en": "RU"},
    "lang.en": {"ru": "EN", "en": "EN"},
    "common.yes": {"ru": "ДА", "en": "YES"},
    "common.no": {"ru": "НЕТ", "en": "NO"},
    "dashboard.title": {"ru": "Панель", "en": "Dashboard"},
    "dashboard.status": {"ru": "Статус", "en": "Status"},
    "dashboard.connected": {"ru": "Подключение", "en": "Connected"},
    "dashboard.bot_enabled": {"ru": "Статус бота", "en": "Bot enabled"},
    "dashboard.target": {"ru": "Канал мониторинга", "en": "TARGET_CHANNEL"},
    "dashboard.session": {"ru": "SESSION_NAME", "en": "SESSION_NAME"},
    "dashboard.server_time": {"ru": "Время сервера (UTC)", "en": "Server time (UTC)"},
    "dashboard.controls": {"ru": "Управление", "en": "Controls"},
    "dashboard.enable": {"ru": "Включить", "en": "Enable"},
    "dashboard.disable": {"ru": "Выключить", "en": "Disable"},
    "dashboard.restart": {"ru": "Перезапуск", "en": "Restart"},
    "dashboard.cleanup": {"ru": "Очистка", "en": "Cleanup"},
    "dashboard.restart_hint": {
        "ru": "Restart — мягкий сигнал. Переподключение выполняется в фоне.",
        "en": "Restart is a soft signal. Reconnect happens in the background.",
    },
    "dashboard.last_error": {"ru": "Последняя ошибка", "en": "Last error"},
    "dashboard.last_event": {"ru": "Последнее событие", "en": "Last event"},
    "dashboard.no_errors": {"ru": "Ошибок нет", "en": "No errors"},
    "dashboard.no_events": {"ru": "Событий нет", "en": "No events"},
    "dashboard.target_manage": {"ru": "Канал мониторинга", "en": "Target channel"},
    "dashboard.target_hint": {
        "ru": "Можно указать название канала, @username или invite‑link.",
        "en": "You can use a channel title, @username, or invite link.",
    },
    "dashboard.target_save": {"ru": "Сохранить", "en": "Save"},
    "dashboard.target_error_empty": {"ru": "Канал мониторинга не может быть пустым", "en": "Target channel is empty"},
    "keywords.title": {"ru": "Ключевые слова", "en": "Keywords"},
    "keywords.manage": {"ru": "Управление ключевыми словами", "en": "Manage keywords"},
    "keywords.search": {"ru": "Поиск", "en": "Search"},
    "keywords.add": {"ru": "Добавить слово", "en": "Add keyword"},
    "keywords.search_placeholder": {"ru": "Поиск", "en": "Search"},
    "keywords.add_placeholder": {"ru": "Добавить слово", "en": "Add keyword"},
    "keywords.error_empty": {"ru": "Слово не может быть пустым", "en": "Keyword is empty"},
    "keywords.total": {"ru": "Всего", "en": "Total"},
    "keywords.table.id": {"ru": "№", "en": "#"},
    "keywords.table.word": {"ru": "Слово", "en": "Keyword"},
    "keywords.table.actions": {"ru": "Действия", "en": "Actions"},
    "keywords.empty": {"ru": "Список пуст", "en": "No keywords yet"},
    "keywords.page": {"ru": "Страница", "en": "Page"},
    "keywords.of": {"ru": "из", "en": "of"},
    "logs.title": {"ru": "Логи", "en": "Logs"},
    "logs.latest": {"ru": "Последние ошибки", "en": "Latest errors"},
    "logs.note": {"ru": "Показываются по 20 записей на странице. Сообщения укорочены.", "en": "20 records per page. Messages are truncated."},
    "logs.page": {"ru": "Страница", "en": "Page"},
    "logs.of": {"ru": "из", "en": "of"},
    "logs.empty": {"ru": "Ошибок нет", "en": "No errors yet"},
    "logs.table.id": {"ru": "ID", "en": "ID"},
    "logs.table.time": {"ru": "Время (UTC)", "en": "Time (UTC)"},
    "logs.table.message": {"ru": "Сообщение", "en": "Message"},
    "login.title": {"ru": "Вход", "en": "Login"},
    "login.login": {"ru": "Логин", "en": "Login"},
    "login.password": {"ru": "Пароль", "en": "Password"},
    "login.submit": {"ru": "Войти", "en": "Sign in"},
    "login.error": {"ru": "Неверный логин или пароль", "en": "Invalid login or password"},
    "login.hint": {
        "ru": "Данные для входа задаются в переменных окружения.",
        "en": "Credentials are configured via environment variables.",
    },
}


def t(key: str, lang: str) -> str:
    data = TRANSLATIONS.get(key)
    if not data:
        return key
    return data.get(lang, data.get(DEFAULT_LANG, key))


def resolve_lang(request: Request) -> tuple[str, bool]:
    query_lang = (request.query_params.get("lang") or "").lower().strip()
    if query_lang in SUPPORTED_LANGS:
        return query_lang, True

    cookie_lang = (request.cookies.get("lang") or "").lower().strip()
    if cookie_lang in SUPPORTED_LANGS:
        return cookie_lang, False

    return DEFAULT_LANG, False


def apply_lang_cookie(response, lang: str, should_set: bool) -> None:
    if not should_set:
        return
    response.set_cookie(
        "lang",
        lang,
        max_age=60 * 60 * 24 * 365,
        samesite="lax",
    )


def build_lang_urls(request: Request) -> dict[str, str]:
    base_path = request.url.path
    params = dict(request.query_params)
    params.pop("lang", None)

    urls = {}
    for lang in SUPPORTED_LANGS:
        params_with_lang = dict(params)
        params_with_lang["lang"] = lang
        query = urlencode(params_with_lang) if params_with_lang else ""
        urls[lang] = f"{base_path}?{query}" if query else base_path
    return urls

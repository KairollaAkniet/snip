# ✂ Snip — URL Shortener с аналитикой

Сервис коротких ссылок: создаёт короткий URL, генерирует QR-код и собирает аналитику кликов
(по дням, устройствам, браузерам, ОС и источникам трафика) с live-дашбордом.

**Стек:** Python 3.12 · FastAPI · SQLAlchemy 2.0 (async) · PostgreSQL · Redis · Docker · pytest

## Возможности

- Короткие ссылки со случайным кодом или своим алиасом, срок жизни ссылки
- Быстрый редирект через **Redis-кэш** (cache-aside, TTL учитывает срок жизни ссылки)
- Запись кликов в **фоне** (`BackgroundTasks`) — редирект не ждёт записи в БД
- Аналитика: клики за 30 дней, устройства, браузеры, ОС, источники (кэшируется на 10 сек)
- QR-код в SVG для каждой ссылки
- **Rate limiting** на создание ссылок (Redis, fixed window)
- Graceful degradation: если Redis упал — сервис продолжает работать без кэша
- `/health` — проверка БД и Redis
- Автодокументация API: `/docs`

## Запуск через Docker (рекомендуется)

```bash
docker compose up --build
```

Открыть http://localhost:8000

## Локальный запуск без Docker

```bash
python -m venv .venv
.venv\Scripts\activate          # Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt
copy .env.example .env          # Linux/macOS: cp .env.example .env
uvicorn app.main:app --reload
```

Нужны запущенные PostgreSQL и Redis. Для быстрого старта без них можно указать SQLite:
`DATABASE_URL=sqlite+aiosqlite:///./dev.db` (Redis необязателен).

## Тесты

```bash
pytest
```

Тесты используют SQLite и fakeredis — внешние сервисы не нужны.

## API

| Метод  | Путь                     | Описание                          |
|--------|--------------------------|-----------------------------------|
| POST   | `/api/links`             | Создать ссылку                    |
| GET    | `/api/links`             | Последние 20 ссылок               |
| GET    | `/api/links/{code}`      | Информация о ссылке               |
| GET    | `/api/links/{code}/stats`| Аналитика                         |
| GET    | `/api/links/{code}/qr`   | QR-код (SVG)                      |
| DELETE | `/api/links/{code}`      | Удалить ссылку и статистику       |
| GET    | `/{code}`                | Редирект (302) + запись клика     |
| GET    | `/health`                | Статус БД и Redis                 |

Пример:

```bash
curl -X POST http://localhost:8000/api/links -H "Content-Type: application/json" -d "{\"url\": \"https://github.com\", \"custom_alias\": \"gh\", \"expires_in_days\": 7}"
```

## Структура

```
app/
  main.py          # точка входа, роутинг, lifespan
  config.py        # настройки из переменных окружения
  database.py      # async engine и сессии SQLAlchemy
  models.py        # таблицы links и clicks
  schemas.py       # Pydantic-схемы и валидация
  services.py      # бизнес-логика: создание, редирект, аналитика
  cache.py         # Redis: кэш и rate limiter
  utils.py         # генерация кода, парсинг User-Agent
  routers/         # HTTP-эндпоинты
  static/          # фронтенд (HTML/CSS/JS + Chart.js)
tests/             # pytest
```

## Идеи для развития

- Миграции через Alembic
- Регистрация пользователей (JWT) — у каждого свои ссылки
- Live-обновление статистики через WebSocket + Redis Pub/Sub
- Геолокация кликов по IP
- CI в GitHub Actions

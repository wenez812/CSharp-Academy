# C# Academy Bot

Telegram-бот и Telegram Mini App для самостоятельного изучения C# на русском языке. В комплекте — 28 уроков в 14 этапах, примеры, практические задания, Monaco Editor, сохранение прогресса и запуск кода через внешний runner.

## Возможности первой версии

- `/start`, `/course`, `/progress`, `/review`, `/help`.
- 28 уроков: основы C#, условия, циклы, массивы, методы, обработка ошибок, ООП, коллекции/LINQ, Git, async/HTTP/JSON, SQL, ASP.NET Core, DI, EF Core, тестирование, безопасность, Docker и деплой.
- По 2 практических задания на урок. Подсказки доступны рядом с заданиями.
- Редактор Monaco с подсветкой синтаксиса, строками и запуском кода.
- SQLite-прогресс на пользователя, лимит запросов на запуск кода и health endpoint.
- Telegram Web App `initData` HMAC validation; запуск произвольного кода на вашем VPS не производится.

## Требования

- Сервер с Docker Engine и Docker Compose plugin.
- Домен и HTTPS для Telegram Mini App. Сам Telegram требует публичный HTTPS URL.
- Токен бота от `@BotFather`.
- Исходящий HTTPS-доступ с сервера к сервису выполнения кода.

## Быстрый запуск

1. Создай бота у `@BotFather` и скопируй токен.
2. Скопируй `.env.example` в `.env` и заполни `BOT_TOKEN` и `WEBAPP_URL`.
3. Настрой HTTPS reverse proxy для домена на `http://127.0.0.1:8000`. Подойдут Caddy или Nginx с сертификатом Let's Encrypt.
4. Запусти:

   ```bash
   docker compose up -d --build
   docker compose logs -f
   ```

5. В `@BotFather` при необходимости настрой домен Mini App, затем открой своего бота и отправь `/start`.
6. Проверь состояние API: `https://your-domain.example.com/health` должен вернуть `{"ok":true,"lessons":28}`.

## Локальная проверка интерфейса

Для разработки без Telegram временно установи в `.env` `DEV_MODE=true`, затем `docker compose up --build`. Открой `http://localhost:8000`. **Не включай `DEV_MODE=true` на публичном сервере**: в этом режиме запросы без Telegram-аутентификации разрешены.

## Важные ограничения MVP

- Код передаётся внешнему сервису Piston. Его публичная доступность, политика использования и поддержка версии C# могут меняться. При недоступности запуск кода не сработает; можно настроить свой изолированный runner через `RUNNER_URL`.
- Автоматическая оценка решений по скрытым тестам пока не реализована. Сейчас ученик запускает код и сам сверяет вывод; отметка о прохождении сохраняется вручную.
- Второе задание каждого урока — дополнительная практика с граничными случаями; задания и автоматические тесты можно улучшать по мере развития курса.
- SQLite подходит для личного MVP. Для большой нагрузки стоит перейти на PostgreSQL, настроить резервные копии и отдельный runner с жёсткими ресурсными лимитами.
- Не вставляй секреты и персональные данные в код редактора: код отправляется внешнему runner.

## Структура

```text
bot/main.py                Telegram bot (aiogram)
backend/app.py             FastAPI API, SQLite, Telegram initData validation
web/index.html             Telegram Mini App + Monaco editor
curriculum/curriculum.json 28 учебных уроков
Dockerfile
docker-compose.yml
.env.example
```

## Проверка

```bash
python -m compileall bot backend
python -c "import json; x=json.load(open('curriculum/curriculum.json')); print(len(x), 'lessons')"
curl http://localhost:8000/health
```

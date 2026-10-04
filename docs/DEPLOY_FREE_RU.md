# Бесплатный деплой: Cloudflare Pages + JustRunMy.App + Supabase + R2

Магазин работает без вашего компьютера и без оплаты:

| Часть | Где | Бесплатный лимит |
|---|---|---|
| Mini App (фронтенд) | Cloudflare Pages, `https://ecosmetics-shop.pages.dev` | без ограничений для статики |
| Бэкенд (API + бот) | JustRunMy.App, Docker-контейнер из `backend/` | 0.15 ГБ RAM, 0.15 vCPU; каждые ~36 ч нажимать **Reset timer**; бесплатно до 19.10.2026 |
| База PostgreSQL | Supabase | 500 МБ, пауза только после недели без запросов |
| Фото товаров | Cloudflare R2, бакет `ecosmetics-media` | 10 ГБ |

Как идут запросы: Telegram открывает `ecosmetics-shop.pages.dev`. Pages отдаёт приложение,
пересылает `/api/*` на бэкенд (секрет `BACKEND_URL`) и отдаёт `/media/*` прямо из R2.
Префикс `/api` при пересылке отрезается (`/api/health` → `/health`): у бэкенда все пути
начинаются от корня, а в Docker то же самое делает nginx.
Вебхук бота тоже смотрит на pages.dev, поэтому при переезде бэкенда его не трогают.

Сейчас бэкенд работает на `https://ecosmetics-api.k.onjrnm.vip` (приложение 66718 в панели JustRunMy).
Бесплатное приложение JustRunMy останавливается, если не нажимать **Reset timer** примерно раз
в 36 часов: так хостинг отключает заброшенные приложения. Проще всего нажимать раз в день.

Бэкенд в покое занимает ~115 МБ, при загрузке фото 12 Мп — до ~160 МБ (замерено в Docker).

Почему не Neon: бэкенд обращается к базе каждые 2 секунды (очередь уведомлений), база никогда
не засыпает, и бесплатные 100 CU-часов Neon кончаются примерно за 16 дней.

## 1. Supabase (база)

1. supabase.com → New project. Регион — ближайший к бэкенду (например, Frankfurt).
   Запишите пароль базы.
2. Кнопка **Connect** → **Session pooler** (порт 5432, работает по IPv4). Скопируйте строку:
   `postgresql://postgres.<id>:<пароль>@aws-0-<регион>.pooler.supabase.com:5432/postgres`
3. Допишите в конец `?sslmode=require`. Это и есть `DATABASE_URL`: приложение само превратит
   его в формат asyncpg. **Не берите Transaction pooler (порт 6543)**: asyncpg с ним не работает.

Таблицы создаст сам бэкенд при старте (`alembic upgrade head` в `docker-entrypoint.sh`).

## 2. Ключ R2 для бэкенда

Бакет `ecosmetics-media` уже создан и привязан к Pages (`frontend/wrangler.toml`).

1. dash.cloudflare.com → **R2** → **Manage API tokens** → **Create API token**.
2. Права: **Object Read & Write**, только бакет `ecosmetics-media`.
3. Запишите **Access Key ID** и **Secret Access Key** (секрет показывают один раз) и
   **Account ID** (виден на странице R2).

## 3. JustRunMy.App (бэкенд)

1. Регистрация на justrunmy.app (карта не нужна) → новое приложение из Git:
   репозиторий `https://github.com/Shokhanasser1/10-D-tgbot`, папка `backend` (там `Dockerfile`).
2. Добавьте HTTPS-порт **8000** (или задайте свой через переменную `PORT`).
3. Переменные окружения (значения берите из своего `.env`, кроме новых):

```
ENV=production
DATABASE_URL=<строка из шага 1>
TELEGRAM_BOT_TOKEN=...
TELEGRAM_WEBHOOK_SECRET=...
TELEGRAM_BOT_USERNAME=...
WEBAPP_URL=https://ecosmetics-shop.pages.dev/
INTERNAL_API_TOKEN=...
ADMIN_SESSION_SECRET=...
ADMIN_BOOTSTRAP_TELEGRAM_IDS=...
SHOP_TIMEZONE=Asia/Tashkent
DEFAULT_CURRENCY=UZS
CASH_ON_DELIVERY_ENABLED=true
TELEGRAM_PAYMENT_PROVIDER_TOKEN=...
MEDIA_STORAGE=r2
R2_ACCOUNT_ID=<шаг 2>
R2_ACCESS_KEY_ID=<шаг 2>
R2_SECRET_ACCESS_KEY=<шаг 2>
R2_BUCKET=ecosmetics-media
```

Остальные переменные (Stripe, доставка, резервы) — как в `docker-compose.yml`, если нужны
не значения по умолчанию.

**Копируйте значение без переноса строки.** Если скопировать строку из Блокнота целиком, в конец
значения попадёт невидимый `\n`. С ним `TELEGRAM_WEBHOOK_SECRET` не пройдёт проверку, и сервер
не запустится, а в остальных переменных перенос сломает работу без всякого сообщения (бот не
отправит уведомления, фото не загрузятся). Надёжный способ: курсор сразу после `=`,
**Shift+End**, **Ctrl+C**.

4. После деплоя проверьте `https://<ваше-приложение>/health` → `{"status":"ok"}`.

## 4. Направить Pages на бэкенд

Из папки `frontend/`:

```
npx wrangler pages secret put BACKEND_URL     # вставить https://<ваше-приложение> без / в конце
npm run deploy:pages
```

Проверка: `https://ecosmetics-shop.pages.dev/api/health` → `{"status":"ok"}`.
`npm run tunnel` и локальный Docker после этого больше не нужны.

## Если что-то не так

Сначала проверьте два адреса: `https://<ваше-приложение>/health` (сам бэкенд) и
`https://ecosmetics-shop.pages.dev/api/health` (бэкенд через Pages). Так сразу видно, какое звено сломалось.

- Адрес бэкенда отвечает текстом `404 page not found` — приложение остановлено, обычно потому, что
  не нажали **Reset timer**. В панели нажмите **Start** или **Restart**, затем **Reset timer**.
- Адрес бэкенда отвечает `502` — контейнер падает при старте. Причину пишет лог: панель →
  приложение → **Diagnostics** → **Live container output**, последние строки. Например,
  `TELEGRAM_WEBHOOK_SECRET must be 1-256 characters...` с `\n` в конце значения означает
  перенос строки, попавший в переменную (см. шаг 3).
- `530` на `/api/...` — `BACKEND_URL` указывает на старый туннель `trycloudflare`, который уже закрыт.
  Задайте адрес JustRunMy (шаг 4).
- `502 backend_unreachable` на `/api/...` — бэкенд не запущен или `BACKEND_URL` неверный.
- `503 backend_not_configured` — `BACKEND_URL` не задан; задайте и заново `npm run deploy:pages`.
- Загрузка фото в админке даёт `media_unavailable` — неверные `R2_*` или у токена нет прав на бакет.
- Контейнер перезапускается из-за памяти — посмотрите логи в JustRunMy; уменьшите нагрузку
  или перенесите бэкенд на сервер с большей памятью (например, Oracle Cloud Always Free).

Локальный запуск для студентов (`ZAPUSK_BEZ_DOCKER.md`) не меняется: по умолчанию
`MEDIA_STORAGE=local`, фото лежат в `MEDIA_ROOT`.

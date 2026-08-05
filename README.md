# Telegram Logo Overlay Bot

Бот для Telegram: принимает фото файлом без сжатия, предлагает канал и вариант логотипа, возвращает готовую картинку 4:5 как файл.

## Каналы

- Sportcore: слева/справа
- Sportcore Finds: слева/справа
- Music Core: слева/справа
- Больше: фиолетовый/желтый/белый
- Home of Hockey: винлайн/фонбет

Все текущие PNG-оверлеи лежат в `assets/logos/`. Оверлеи меньше итогового
холста `1080x1350` выравниваются по центру снизу без растягивания.

## Переменные окружения Vercel

Обязательные:

- `TELEGRAM_BOT_TOKEN` - новый токен от BotFather
- `WEBHOOK_SECRET` - любая длинная случайная строка

Рекомендуемые для продакшена:

- `UPSTASH_REDIS_REST_URL`
- `UPSTASH_REDIS_REST_TOKEN`

Бот также понимает старые имена Vercel KV:

- `KV_REST_API_URL`
- `KV_REST_API_TOKEN`

Без Redis/Vercel KV бот будет хранить выбор фото в памяти serverless-инстанса. Для первого теста этого может хватить, но в продакшене лучше подключить Redis, чтобы кнопки стабильно работали после cold start.

Опциональные:

- `OUTPUT_FORMAT=PNG` или `JPEG`
- `OUTPUT_QUALITY=100`
- `JPEG_SUBSAMPLING=0`
- `MAX_INPUT_MB=20`

`MAX_INPUT_MB=20` - верхняя граница для входящего файла: Telegram Bot API не дает боту скачать файл больше 20 MB через `getFile`.
По умолчанию результат сохраняется в PNG без JPEG-пережатия. Если нужен именно JPEG, он сохраняется с качеством 100, sRGB ICC-профилем и без цветовой субдискретизации (`JPEG_SUBSAMPLING=0`).

## Деплой на Vercel

1. Создать новый GitHub-репозиторий из этой папки.
2. Создать в Vercel отдельный Project рядом с `tennis-scores-daily-results`.
   Не импортировать этот код в старый теннисный Project: у него уже свой webhook, свои Neon-переменные и свои деплои.
3. Добавить переменные окружения из блока выше.
4. Задеплоить.
5. Поставить webhook:

```powershell
$token = "NEW_BOT_TOKEN"
$secret = "YOUR_WEBHOOK_SECRET"
$url = "https://YOUR_PROJECT.vercel.app/api/webhook"
Invoke-RestMethod -Method Post "https://api.telegram.org/bot$token/setWebhook" -Body @{
  url = $url
  secret_token = $secret
}
```

Проверить webhook:

```powershell
Invoke-RestMethod "https://api.telegram.org/bot$token/getWebhookInfo"
```

## Локальная проверка оверлеев

```powershell
python -m pip install -r requirements.txt
python scripts/preview_overlay.py
```

Превью появятся в `tmp/previews/`.

## Важно про токен

Токен, который уже отправлялся в чат, лучше перевыпустить через BotFather: `/revoke` или создание нового токена для этого бота. Старый токен не коммитить и не вставлять в README.

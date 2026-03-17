# Чат-бот "СВОй" для соревнований

## Quick Start

```bash
cp .env.example .env
docker compose up --build
```

After:

- Web: `http://localhost:8000/`
- iframe: `http://localhost:8000/widget`
- healthcheck: `http://localhost:8000/api/health`

## Встраивание на сайт

```html
<iframe
  src="https://your-domain.example/widget"
  width="420"
  height="720"
  style="border:0;border-radius:16px;overflow:hidden"
  loading="lazy"
></iframe>
```

## Переменные окружения

Смотри `.env.example`.

Для email-уведомлений заполни:

- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_USE_TLS`
- `MAIL_TO`

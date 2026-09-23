# HackAlem AI — чат-ассистент ekt.kz

Прототип ИИ-консультанта для каталога ekt.kz. Архитектура MVP, границы компонентов, API-контракт и ограничения текущих данных описаны в [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Данные для прототипа

- `dataset/api_products.json` и `dataset/api_products_page2.json` — две страницы каталога, всего 40 уникальных товаров.
- `dataset/api_products_detail.json` — подробная карточка товара `515291`, включая характеристики и остатки по складам.

Это тестовая выборка, а не полная синхронизация с ekt.kz. В ней нет сертификатов и справочника условий покупки. Для реального изменения корзины нужен согласованный API сайта и привязка к сессии пользователя.

## Локальный запуск

Нужны Python 3.10+ и Node.js 18+.

Backend:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
uvicorn app.main:app --app-dir backend --reload
```

Для подключения NVIDIA скопируйте `backend/.env.example` в `.env` и заполните
`NVIDIA_MODEL` и `NVIDIA_API_KEY`. Ключ не добавляйте в Git. Без этих переменных
backend использует deterministic MVP fallback.

Frontend в отдельном терминале:

```bash
cd frontend
npm install
npm run dev
```

Откройте `http://localhost:5173`. Проверка backend: `http://localhost:8000/api/v1/health`.

## Текущий срез

Прототип создаёт временную сессию и ищет товары по ID, артикулу или словам из названия. Ответы берутся из локальных JSON-файлов. LLM, загрузка вложений, проверка актуальных остатков и добавление в настоящую корзину пока не подключены; интерфейс помечает данные как демонстрационные.

Для демонстрации корзины backend предоставляет mock-адаптер: сначала создаётся одноразовое подтверждение, затем backend повторно проверяет остаток и только после подтверждения добавляет позиции. Настоящая корзина ekt.kz подключается отдельной реализацией `CartAdapter`.

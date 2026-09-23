# HackAlem AI — чат-ассистент ekt.kz

ИИ-ассистент помогает покупателю найти электротехнический товар, проверить доступное наличие, увидеть характеристики и получить предложение добавить позицию в корзину. Backend повторно проверяет остаток и изменяет mock-корзину только после явного подтверждения пользователя.

## Что демонстрирует прототип

- поиск по ID, внутреннему артикулу, артикулу поставщика и названию;
- карточки товара с ценой, ссылкой, изображением, остатками по складам и предупреждениями;
- обнаружение противоречивых характеристик в исходных данных;
- предложение добавить товар с указанным количеством;
- одноразовое подтверждение с повторной проверкой остатка;
- mock-ссылка на корзину после подтверждения;
- deterministic MVP-агент с интерфейсом, совместимым с NVIDIA NIM.

Полная архитектура и границы ответственности описаны в [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Технологии

- Backend: Python 3.10+, FastAPI, Pydantic, Uvicorn.
- AI boundary: `handle_message(request, services) -> AssistantResult`, `ProductHit[]`, NVIDIA NIM adapter.
- Frontend: React, TypeScript, Vite.
- Данные прототипа: JSON fixtures в `dataset/`.
- Корзина: backend `MockCartAdapter`; интеграция с настоящей корзиной ekt.kz требует официального API партнёра.

## Данные

- `dataset/api_products.json` — первая страница каталога, 20 товаров.
- `dataset/api_products_page2.json` — вторая страница каталога, ещё 20 товаров.
- `dataset/api_products_detail.json` — подробная карточка товара `515291`, характеристики и остатки по складам.

Выборка демонстрационная. В ней нет полного каталога, сертификатов и утверждённого FAQ по оплате и доставке. Неизвестные значения backend возвращает как отсутствующие, а не придумывает.

## Запуск

Нужны Python 3.10+ и Node.js 18+.

### Backend

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
uvicorn app.main:app --app-dir backend --reload --port 8000
```

Проверка состояния: `http://localhost:8000/api/v1/health`.

### Frontend

В отдельном терминале:

```bash
cd frontend
npm install
npm run dev
```

Откройте `http://localhost:5173`. Vite proxy направляет `/api` на `http://127.0.0.1:8000`.

Для live-запросов к backend используйте:

```env
VITE_API_MODE=live
```

Без этого параметра frontend работает в локальном demo-режиме.

## Проверка решения

1. Откройте frontend и отправьте вопрос `027228`.
2. Убедитесь, что карточка содержит цену, остаток, склады, ссылку и `data_source`.
3. Отправьте: `добавь 1 027228 в корзину`.
4. Проверьте, что backend вернул `pending_confirmation` с `confirmation_id`.
5. Нажмите подтверждение во frontend или вызовите endpoint подтверждения.
6. Убедитесь, что ответ содержит `cart_url`, а без подтверждения корзина остаётся пустой.

Минимальная проверка backend:

```bash
curl -X POST http://localhost:8000/api/v1/sessions
curl http://localhost:8000/api/v1/health
```

Основные endpoints:

```text
POST /api/v1/sessions
POST /api/v1/sessions/{session_id}/messages
POST /api/v1/sessions/{session_id}/confirmations
POST /api/v1/sessions/{session_id}/confirmations/{confirmation_id}/confirm
GET  /api/v1/sessions/{session_id}/cart
```

## NVIDIA NIM

Интеграция включается только при наличии настроек. Скопируйте `backend/.env.example` в `.env` и заполните `NVIDIA_MODEL` и `NVIDIA_API_KEY`. Ключ не добавляйте в Git.

```env
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
NVIDIA_MODEL=<модель из NVIDIA Console>
NVIDIA_API_KEY=<локальный секрет>
```

Если модель или ключ не заданы, используется deterministic MVP fallback.

## Ограничения демо

- NVIDIA-модель и реальная корзина ekt.kz требуют отдельных параметров/API.
- Условия оплаты, доставки и минимальной партии нельзя подтвердить по текущему датасету.
- Аналоги являются предварительными рекомендациями по доступной выборке и не считаются технически эквивалентными без подтверждённых характеристик.

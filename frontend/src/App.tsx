import { FormEvent, useEffect, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

type Product = {
  id: string;
  name: string;
  article: string | null;
  price: number | null;
  image: string | null;
  url: string | null;
  has_details: boolean;
};

type ChatMessage = {
  role: "assistant" | "user";
  content: string;
  products?: Product[];
};

const initialMessage: ChatMessage = {
  role: "assistant",
  content:
    "Здравствуйте! Я помогу найти товар в тестовой выборке ekt.kz. Введите артикул или часть названия.",
};

function App() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([initialMessage]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [connectionError, setConnectionError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    fetch(`${API_BASE}/api/v1/sessions`, { method: "POST" })
      .then(async (response) => {
        if (!response.ok) throw new Error("Не удалось начать диалог");
        return (await response.json()) as { session_id: string };
      })
      .then(({ session_id }) => {
        if (active) {
          setSessionId(session_id);
          setConnectionError(null);
        }
      })
      .catch(() => {
        if (active) setConnectionError("Не удалось подключиться к backend. Проверьте, что API запущен.");
      });
    return () => {
      active = false;
    };
  }, []);

  async function sendMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const message = draft.trim();
    if (!message || !sessionId || busy) return;

    setDraft("");
    setBusy(true);
    setConnectionError(null);
    setMessages((current) => [...current, { role: "user", content: message }]);

    try {
      const response = await fetch(`${API_BASE}/api/v1/sessions/${sessionId}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
      });
      if (!response.ok) throw new Error("Не удалось получить ответ");
      const result = (await response.json()) as {
        answer: string;
        products: Product[];
      };
      setMessages((current) => [
        ...current,
        { role: "assistant", content: result.answer, products: result.products },
      ]);
    } catch {
      setConnectionError("Не удалось получить ответ. Попробуйте отправить сообщение ещё раз.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="page-shell">
      <section className="chat-panel" aria-label="Чат-консультант ekt.kz">
        <header className="chat-header">
          <div className="brand-mark" aria-hidden="true">e</div>
          <div>
            <p className="eyebrow">ekt.kz</p>
            <h1>Помощник по товарам</h1>
          </div>
          <span className="status"><span /> Тестовый режим</span>
        </header>

        <div className="notice">
          Данные загружены из демонстрационной выборки. Цена и наличие требуют проверки на сайте.
        </div>

        <div className="messages" aria-live="polite" aria-busy={busy}>
          {messages.map((message, index) => (
            <article className={`message message-${message.role}`} key={`${message.role}-${index}`}>
              <p className="message-text">{message.content}</p>
              {message.products?.length ? (
                <div className="product-list">
                  {message.products.map((product) => (
                    <ProductCard product={product} key={product.id} />
                  ))}
                </div>
              ) : null}
            </article>
          ))}
          {busy ? <p className="typing">Ищу в каталоге…</p> : null}
        </div>

        {connectionError ? <p className="error" role="alert">{connectionError}</p> : null}

        <form className="composer" onSubmit={sendMessage}>
          <label className="sr-only" htmlFor="question">Ваш вопрос</label>
          <input
            id="question"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder="Например, 027228 или Legrand"
            maxLength={2000}
            disabled={!sessionId || busy}
          />
          <button type="submit" disabled={!sessionId || busy || !draft.trim()} aria-label="Отправить">
            <span aria-hidden="true">↑</span>
          </button>
        </form>
        <p className="footnote">Не вводите платёжные данные или конфиденциальную информацию.</p>
      </section>
    </main>
  );
}

function ProductCard({ product }: { product: Product }) {
  return (
    <article className="product-card">
      {product.image ? (
        <img src={product.image} alt="" loading="lazy" />
      ) : (
        <div className="product-placeholder" aria-hidden="true">e</div>
      )}
      <div className="product-info">
        <h2>{product.name}</h2>
        <p>Артикул: {product.article || "не указан"}</p>
        {product.price !== null ? (
          <p className="price">В выборке: {product.price.toLocaleString("ru-RU")} · валюта не указана</p>
        ) : null}
        {product.has_details ? <span className="details-badge">Есть подробная карточка</span> : null}
      </div>
      {product.url ? (
        <a href={product.url} target="_blank" rel="noreferrer" aria-label={`Открыть ${product.name}`}>
          ↗
        </a>
      ) : null}
    </article>
  );
}

export default App;

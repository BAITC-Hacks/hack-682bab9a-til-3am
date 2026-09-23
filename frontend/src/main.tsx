import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { catalog, live, sendMessage } from './api';
import type { Product } from './types';
import './style.css';

type Message = { role: 'user' | 'assistant'; text: string; products?: Product[]; warnings?: string[] };
const examples = ['DEMO-BREAKER-40A в Алматы', 'Автомат 40А', 'Реле RM17'];
const money = (value: number) => new Intl.NumberFormat('ru-KZ').format(value) + ' ₸';

function ProductCard({ product }: { product: Product }) {
  const [broken, setBroken] = useState(false);
  return <article className="product">
    <div className="product-image">{product.image && !broken ? <img src={product.image} alt={product.name} onError={() => setBroken(true)} /> : <span>Нет фото</span>}</div>
    <div className="product-info"><span className="article">Арт. {product.article}</span><h3>{product.name}</h3>
      <p className="stock">{product.quantity === null ? 'Наличие не уточнено' : `${product.quantity} шт. в демо`}</p>
      <div className="product-bottom"><strong>{money(product.price)}</strong>{product.url && <a href={product.url} target="_blank" rel="noreferrer">На сайт ↗</a>}</div>
    </div>
  </article>;
}

function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [failed, setFailed] = useState<string | null>(null);
  const messagesRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const container = messagesRef.current;
    if (container) container.scrollTop = container.scrollHeight;
  }, [messages, loading, error]);
  async function submit(text: string, retry = false) {
    if (!text.trim() || loading) return;
    setLoading(true); setError(''); setFailed(null); setInput('');
    if (!retry) setMessages(previous => [...previous, { role: 'user', text }]);
    try {
      const response = await sendMessage(text);
      setMessages(previous => [...previous, { role: 'assistant', text: response.message, products: response.products, warnings: response.warnings }]);
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Не удалось получить ответ.'); setFailed(text); }
    finally { setLoading(false); }
  }
  return <div className="app">
    <aside className="sidebar"><a className="logo" href="/">ekt<span>●</span></a><span className="sidebar-caption">ЭЛЕКТРОКОМПЛЕКТ</span>
      <div className="workspace-label">ВАШ ПОМОЩНИК</div><div className="nav-active">✦ <span>Консультант по каталогу</span></div>
      <div className="sidebar-note"><span className="note-icon">↗</span><h3>От вопроса к выбору</h3><p>Найдите товар, сравните характеристики и уточните наличие.</p></div>
      <div className="sidebar-footer"><span className="status-dot"/> {live ? 'Серверный режим' : 'Локальный прототип'}<small>HackAlem · команда ’til 3am</small></div>
    </aside>
    <main><header><div><span className="breadcrumb">Каталог /</span> AI-консультант</div><span className="mode">{live ? 'API подключается' : 'Демо · без LLM'}</span></header>
      <div className="content"><section className="intro"><span className="eyebrow">МЕНЬШЕ ПОИСКА. БОЛЬШЕ ЯСНОСТИ.</span><h1>Подберём нужное<br/><span>вместе.</span></h1><p>Расскажите, что ищете. Поможем разобраться<br className="desktop-break"/> в электротехнике и найти товар в каталоге.</p></section>
      <div className="stats"><span><strong>{catalog.length}</strong> демо-товара</span><span><strong>01</strong> карточка с остатками</span><span>Синтетический fixture</span></div>
      <section className="chat" aria-label="Чат с консультантом"><div className="chat-heading"><div className="avatar">✦</div><div><h2>EKT Assistant</h2><p>Ваш помощник по электротехнике</p></div><span className="chat-badge">BETA</span></div>
        <div className="messages" ref={messagesRef} aria-live="polite" aria-busy={loading}>
          <div className="message assistant"><span className="message-label">EKT ASSISTANT</span><p>Здравствуйте! Укажите название или артикул товара. Я найду его в каталоге и покажу доступные сведения.</p><div className="suggestions">{examples.map(example => <button key={example} disabled={loading} onClick={() => submit(example)}>{example} ↗</button>)}</div></div>
          {messages.map((message, index) => <div className={`message ${message.role}`} key={index}><span className="message-label">{message.role === 'user' ? 'ВЫ' : 'EKT ASSISTANT'}</span><p>{message.text}</p>{message.products?.map(product => <ProductCard key={product.id} product={product} />)}{message.warnings?.map(warning => <p className="warning" key={warning}>{warning}</p>)}</div>)}
          {loading && <p className="loading" role="status">Ищем ответ…</p>}
          {error && <div className="error" role="alert">{error} <button disabled={loading} onClick={() => failed && submit(failed, true)}>Повторить</button></div>}
        </div>
        <form onSubmit={event => { event.preventDefault(); void submit(input); }}><label className="sr-only" htmlFor="message">Ваш вопрос</label><input id="message" value={input} onChange={event => setInput(event.target.value)} placeholder="Например: есть ли DEMO-BREAKER-40A?" maxLength={2000}/><button className="send" type="submit" disabled={loading || !input.trim()} aria-label="Отправить сообщение">↑</button></form>
        <p className="chat-footer">{live ? 'Ответы сервера по каталогу.' : 'Синтетический демонстрационный каталог, без генерации AI.'} Цены в KZT — допущение прототипа.</p>
      </section>
      {!messages.length && <section className="featured"><div className="section-title"><h2>Демо-каталог</h2><span>Синтетические данные ↙</span></div><div className="featured-grid">{catalog.slice(0, 2).map(product => <ProductCard key={product.id} product={product}/>)}</div></section>}
      <footer>Данные синтетические и предназначены только для демонстрации. Корзина будет доступна после подключения бэкенда.</footer>
      </div>
    </main>
  </div>;
}

createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>);

"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";

type Message = { role: "user" | "assistant"; content: string };
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const welcomeMessage: Message = {
  role: "assistant",
  content: "Hi, I’m the US-Duct project assistant. What are you working on?",
};

export default function Home() {
  const [open, setOpen] = useState(false);
  const [sessionId, setSessionId] = useState<string>();
  const [messages, setMessages] = useState<Message[]>([welcomeMessage]);
  const [draft, setDraft] = useState("");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const pendingTextRef = useRef("");
  const displayedTextRef = useRef("");
  const drainPromiseRef = useRef<Promise<void> | null>(null);

  useEffect(() => {
    if (open) messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, open]);

  function updateAssistantText(content: string) {
    setMessages((current) => {
      const next = [...current];
      const last = next.length - 1;
      if (next[last]?.role === "assistant") next[last] = { ...next[last], content };
      return next;
    });
  }

  function drainAssistantText(): Promise<void> {
    if (drainPromiseRef.current) return drainPromiseRef.current;
    drainPromiseRef.current = (async () => {
      while (pendingTextRef.current.length > 0) {
        displayedTextRef.current += pendingTextRef.current.slice(0, 1);
        pendingTextRef.current = pendingTextRef.current.slice(1);
        updateAssistantText(displayedTextRef.current);
        await new Promise((resolve) => window.setTimeout(resolve, 22));
      }
      drainPromiseRef.current = null;
    })();
    return drainPromiseRef.current;
  }

  async function sendMessage(event?: FormEvent, override?: string) {
    event?.preventDefault();
    const message = (override ?? draft).trim();
    if (!message || busy) return;

    setMessages((current) => [...current, { role: "user", content: message }, { role: "assistant", content: "" }]);
    setDraft("");
    setBusy(true);
    pendingTextRef.current = "";
    displayedTextRef.current = "";
    drainPromiseRef.current = null;
    try {
      const response = await fetch(`${API_URL}/api/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          message,
          name: name || undefined,
          email: email || undefined,
        }),
      });
      if (!response.ok) {
        const errorBody = await response.json().catch(() => null) as { detail?: string } | null;
        throw new Error(errorBody?.detail ?? `Assistant request failed (${response.status})`);
      }
      if (!response.body) throw new Error("Streaming is not available in this browser");
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      const handleEvent = (event: { type?: string; content?: string; detail?: string; session_id?: string }) => {
        if (event.type === "start" && event.session_id) setSessionId(event.session_id);
        if (event.type === "token" && event.content) {
          pendingTextRef.current += event.content;
          void drainAssistantText();
        }
        if (event.type === "done" && event.session_id) setSessionId(event.session_id);
        if (event.type === "error") throw new Error(event.detail ?? "The assistant could not complete the request.");
      };

      while (true) {
        const { value, done } = await reader.read();
        buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done });
        const events = buffer.split("\n\n");
        buffer = events.pop() ?? "";
        for (const rawEvent of events) {
          const data = rawEvent.split("\n").find((line) => line.startsWith("data: "))?.slice(6);
          if (data) handleEvent(JSON.parse(data) as { type?: string; content?: string; detail?: string; session_id?: string });
        }
        if (done) break;
      }
      await drainAssistantText();
    } catch (error) {
      const detail = error instanceof Error ? error.message : "Unknown request error";
      setMessages((current) => {
        const next = [...current];
        const last = next.length - 1;
        if (next[last]?.role === "assistant" && !next[last].content) next[last] = { ...next[last], content: `I couldn’t complete that just now. ${detail}` };
        else next.push({ role: "assistant", content: `I couldn’t complete that just now. ${detail}` });
        return next;
      });
    } finally {
      setBusy(false);
    }
  }

  function resetConversation() {
    setSessionId(undefined);
    setMessages([welcomeMessage]);
    setName("");
    setEmail("");
  }

  return (
    <main className="site-shell">
      <nav className="site-nav">
        <div className="site-logo"><span>US</span> DUCT</div>
        <div className="site-nav-links"><span>Industrial ductwork</span><span>Dust collection</span><span>Resources</span></div>
        <button className="nav-quote" onClick={() => setOpen(true)}>GET A QUOTE <span>↗</span></button>
      </nav>

      <section className="site-hero">
        <div className="hero-copy">
          <p className="hero-kicker">INDUSTRIAL AIRFLOW / DUST COLLECTION</p>
          <h1>Built for the work<br /><em>inside</em> your operation.</h1>
          <p className="hero-description">Engineered ductwork, dust collection, and fume extraction systems for facilities that cannot afford to slow down.</p>
          <div className="hero-actions"><button onClick={() => setOpen(true)}>TALK TO US <span>↗</span></button><span className="hero-caption">AMERICAN-MADE<br />WORLDWIDE DISTRIBUTION</span></div>
        </div>
        <div className="hero-visual" aria-hidden="true">
          <div className="visual-grid" />
          <div className="duct duct-a" /><div className="duct duct-b" /><div className="duct duct-c" />
          <div className="visual-label"><span>01</span> AIRFLOW<br />DESIGNED AROUND<br />YOUR PROCESS</div>
        </div>
      </section>

      <section className="site-strip"><span>CLAMP-TOGETHER DUCT</span><span>US TUBING</span><span>LEGEND PERFORMANCE</span><span>DUSTEK COLLECTION</span></section>
      <section className="site-lower"><p>From point of capture to collector, we help industrial teams build cleaner, more flexible systems.</p><span>ARCHDALE, NORTH CAROLINA / EST. 2013</span></section>

      <button className={open ? "assistant-launcher active" : "assistant-launcher"} onClick={() => setOpen((current) => !current)} aria-label={open ? "Close US-Duct assistant" : "Open US-Duct assistant"} aria-expanded={open}>
        <span className="launcher-pulse" /><span className="launcher-icon"><i /><i /><i /></span><span className="launcher-text">ASK US-DUCT</span>
      </button>

      {open && (
        <section className="widget" aria-label="US-Duct assistant">
          <header className="widget-header"><div className="widget-title"><span className="widget-avatar">UD</span><div><strong>US-Duct assistant</strong><small><i /> Usually replies instantly</small></div></div><div className="widget-actions"><button onClick={resetConversation} aria-label="Start a new conversation" title="New conversation">↻</button><button onClick={() => setOpen(false)} aria-label="Close assistant" title="Close">×</button></div></header>
          <div className="widget-messages" aria-live="polite">
            {messages.map((message, index) => <div className={`widget-message ${message.role}`} key={`${message.role}-${index}`}><span className="message-avatar">{message.role === "assistant" ? "UD" : "YOU"}</span><div className="message-copy">{message.role === "assistant" ? (message.content ? <ReactMarkdown>{message.content}</ReactMarkdown> : <p className="typing"><i /><i /><i /></p>) : <p>{message.content}</p>}</div></div>)}
            <div ref={messagesEndRef} />
          </div>
          <div className="widget-details"><input value={name} onChange={(event) => setName(event.target.value)} placeholder="Name (when booking)" aria-label="Name" /><input type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="Work email (when booking)" aria-label="Work email" /></div>
          <form className="widget-composer" onSubmit={sendMessage}><input value={draft} onChange={(event) => setDraft(event.target.value)} placeholder="Ask about ductwork or dust collection..." aria-label="Message" /><button type="submit" disabled={busy || !draft.trim()} aria-label="Send message">↗</button></form>
          <div className="widget-footer">US-DUCT / INDUSTRIAL + COMMERCIAL PROJECTS</div>
        </section>
      )}
    </main>
  );
}

import { FormEvent, useCallback, useEffect, useState } from "react";

type Citation = { document_title: string; excerpt: string; score: number };
type Answer = { answer: string; grounded: boolean; abstained: boolean; confidence: number; citations: Citation[]; model: string };
type Document = { id: string; title: string; redacted_items: number; chunks: number; created_at: string };

const API = import.meta.env.VITE_API_BASE ?? "http://localhost:8002";
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, { ...init, headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) } });
  if (!response.ok) throw new Error((await response.json()).detail ?? "Request failed");
  return response.json() as Promise<T>;
}

const examples = [
  { title: "Downtown Shelter", source_url: "https://civicbridge.example/shelter", content: "The downtown shelter is open every day from 8 AM to 8 PM. Intake is first come, first served. The shelter has accessible showers and vegetarian dinner options." },
  { title: "Community Kitchen", source_url: "https://civicbridge.example/kitchen", content: "Community Kitchen serves hot vegetarian meals on Tuesday and Thursday from 5 PM to 7 PM. Guests can request a take-home pantry box while supplies last." },
  { title: "Legal Aid", source_url: "https://civicbridge.example/legal", content: "Legal Aid offers free housing consultations Monday through Saturday. Sunday appointments are not available. Walk-ins are accepted from 10 AM to 2 PM." },
];

export default function App() {
  const [question, setQuestion] = useState("When is the downtown shelter open?");
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [activeDoc, setActiveDoc] = useState(0);

  const refreshDocuments = useCallback(async () => {
    try { setDocuments(await request<Document[]>("/api/v1/documents")); } catch (error) { setNotice(error instanceof Error ? error.message : "API unavailable"); }
  }, []);
  useEffect(() => { void refreshDocuments(); }, [refreshDocuments]);

  async function ask(event?: FormEvent) {
    event?.preventDefault();
    setBusy(true); setNotice("");
    try { setAnswer(await request<Answer>("/api/v1/ask", { method: "POST", body: JSON.stringify({ question }) })); }
    catch (error) { setNotice(error instanceof Error ? error.message : "Could not answer"); }
    finally { setBusy(false); }
  }

  async function seedDocument() {
    const doc = examples[activeDoc];
    setBusy(true); setNotice("");
    try { await request<Document>("/api/v1/documents", { method: "POST", body: JSON.stringify(doc) }); setNotice(`${doc.title} indexed with PII-safe preprocessing.`); await refreshDocuments(); }
    catch (error) { setNotice(error instanceof Error ? error.message : "Could not index source"); }
    finally { setBusy(false); }
  }

  return <main className="page">
    <nav><div className="wordmark"><span className="sun">✦</span>CivicBridge <em>AI</em></div><div className="nav-right"><span><i className="online" /> knowledge base online</span><span className="model-tag">{answer?.model ?? "offline baseline"}</span></div></nav>
    <section className="intro"><p className="kicker">TRUSTED ANSWERS FOR REAL-WORLD HELP</p><h1>Find the next<br /><i>right step.</i></h1><p className="subtitle">A grounded resource navigator that turns scattered community updates into clear, cited answers — and knows when it should stay quiet.</p></section>

    <section className="workspace">
      <div className="ask-card"><div className="card-label"><span>ASK CIVICBRIDGE</span><span className="lock">⌁ grounded retrieval</span></div><form onSubmit={ask}><textarea value={question} onChange={(e) => setQuestion(e.target.value)} rows={3} /><button disabled={busy}>{busy ? "Thinking…" : "Find an answer  ↗"}</button></form><div className="suggestions"><span>Try</span><button onClick={() => setQuestion("Which location offers vegetarian meals?")}>vegetarian meals</button><button onClick={() => setQuestion("Can I get legal help on Sunday?")}>Sunday legal help</button></div></div>
      <div className={`answer-card ${answer?.abstained ? "caution" : ""}`}><div className="card-label"><span>{answer ? (answer.abstained ? "NEEDS MORE EVIDENCE" : "GROUNDED ANSWER") : "WAITING FOR A QUESTION"}</span>{answer && <span className="confidence">confidence {Math.round(answer.confidence * 100)}%</span>}</div>{answer ? <><p className="answer">{answer.answer}</p><div className="divider" /><p className="source-label">Sources used</p><div className="citations">{answer.citations.length ? answer.citations.map((citation) => <div className="citation" key={citation.document_title}><span className="citation-icon">↗</span><div><strong>{citation.document_title}</strong><p>{citation.excerpt}</p></div><span className="score">{Math.round(citation.score * 100)}%</span></div>) : <p className="muted">No source passed the confidence threshold. Add a resource update and try again.</p>}</div></> : <div className="empty-answer"><span>✧</span><p>Your answer will appear here with the exact passages that support it.</p></div>}</div>
    </section>

    <section className="lower-grid"><div className="sources-panel"><div className="section-head"><div><p className="kicker">INDEXED SOURCES</p><h2>Community updates</h2></div><span className="count">{documents.length.toString().padStart(2, "0")}</span></div><div className="seed-row"><select value={activeDoc} onChange={(e) => setActiveDoc(Number(e.target.value))}>{examples.map((doc, index) => <option key={doc.title} value={index}>{doc.title}</option>)}</select><button onClick={() => void seedDocument()} disabled={busy}>＋ index demo update</button></div><div className="document-list">{documents.map((doc) => <div className="document" key={doc.id}><span className="doc-dot" /><div><strong>{doc.title}</strong><p>{doc.chunks} chunks · {doc.redacted_items ? `${doc.redacted_items} PII pattern redacted` : "clean ingest"}</p></div><span className="arrow">→</span></div>)}{documents.length === 0 && <p className="muted">Index a demo update to see the retrieval layer populate.</p>}</div></div><div className="principles"><p className="kicker">SAFETY LAYER</p><h2>Useful, but<br /><i>never overconfident.</i></h2><div className="principle"><span>01</span><p><strong>Source-first</strong>Every response exposes the passages that shaped it.</p></div><div className="principle"><span>02</span><p><strong>Abstention</strong>Low-confidence questions receive a clear boundary, not a guess.</p></div><div className="principle"><span>03</span><p><strong>Privacy-aware</strong>Contact patterns are redacted before indexing.</p></div></div></section>
    <footer><span>CIVICBRIDGE AI / KNOWLEDGE SYSTEMS</span><span>RETRIEVAL · EVALUATION · PROVENANCE</span></footer>
    {notice && <div className="toast">{notice}</div>}
  </main>;
}

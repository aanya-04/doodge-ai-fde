import React, { useState, useRef, useEffect } from "react";

const EXAMPLE_QUERIES = [
  "Which products have the highest number of billing documents?",
  "Trace the full flow of billing document B1001",
  "Show sales orders delivered but not billed",
  "Which customers have the highest total order value?",
  "Find billing documents with no payments",
];

export default function ChatPanel({ apiUrl, onHighlight }) {
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      content: "Hello! I can answer questions about your business data — orders, deliveries, billing, customers, and products. Try an example below or ask your own question.",
      type: "welcome",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef(null);
  const inputRef = useRef(null);

  const conversationHistory = messages
    .filter((m) => m.role !== "welcome")
    .map((m) => ({ role: m.role, content: m.content }));

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendMessage = async (question) => {
    if (!question.trim() || loading) return;

    const userMsg = { role: "user", content: question, type: "user" };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const res = await fetch(`${apiUrl}/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question,
          conversation_history: conversationHistory,
        }),
      });

      const data = await res.json();

      const assistantMsg = {
        role: "assistant",
        content: data.answer,
        type: data.type,
        sql: data.sql,
        results: data.results,
        highlighted_nodes: data.highlighted_nodes,
      };

      setMessages((prev) => [...prev, assistantMsg]);

      if (data.highlighted_nodes?.length > 0) {
        onHighlight(data.highlighted_nodes);
      }
    } catch (e) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "Error connecting to the server. Please ensure the backend is running.",
          type: "error",
        },
      ]);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  };

  const handleKey = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  };

  return (
    <div className="chat-panel">
      <div className="chat-header">
        <span className="chat-title">◎ Natural Language Query</span>
        <span className="chat-subtitle">Ask anything about your data</span>
      </div>

      <div className="chat-messages">
        {messages.map((msg, i) => (
          <Message key={i} msg={msg} />
        ))}
        {loading && <ThinkingBubble />}
        <div ref={bottomRef} />
      </div>

      <div className="chat-examples">
        <div className="examples-label">Try asking:</div>
        <div className="examples-scroll">
          {EXAMPLE_QUERIES.map((q, i) => (
            <button
              key={i}
              className="example-chip"
              onClick={() => sendMessage(q)}
              disabled={loading}
            >
              {q}
            </button>
          ))}
        </div>
      </div>

      <div className="chat-input-row">
        <textarea
          ref={inputRef}
          className="chat-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKey}
          placeholder="Ask about your business data..."
          rows={2}
          disabled={loading}
        />
        <button
          className="send-btn"
          onClick={() => sendMessage(input)}
          disabled={loading || !input.trim()}
        >
          {loading ? "..." : "→"}
        </button>
      </div>
    </div>
  );
}

function Message({ msg }) {
  const [showSQL, setShowSQL] = useState(false);
  const [showTable, setShowTable] = useState(false);

  const isGuardrail = msg.type === "guardrail";
  const isError = msg.type === "error" || msg.type === "sql_error";
  const isUser = msg.role === "user";

  return (
    <div className={`message ${isUser ? "user" : "assistant"} ${isGuardrail ? "guardrail" : ""} ${isError ? "msg-error" : ""}`}>
      {!isUser && (
        <div className="msg-avatar">
          {isGuardrail ? "🚫" : isError ? "⚠" : "◈"}
        </div>
      )}
      <div className="msg-bubble">
        <div className="msg-text">{msg.content}</div>

        {msg.sql && (
          <div className="msg-meta">
            <button className="meta-toggle" onClick={() => setShowSQL(!showSQL)}>
              {showSQL ? "▼" : "▶"} SQL Query
            </button>
            {showSQL && (
              <pre className="sql-block">{msg.sql}</pre>
            )}
          </div>
        )}

        {msg.results?.length > 0 && (
          <div className="msg-meta">
            <button className="meta-toggle" onClick={() => setShowTable(!showTable)}>
              {showTable ? "▼" : "▶"} Results ({msg.results.length} rows)
            </button>
            {showTable && (
              <ResultsTable results={msg.results} />
            )}
          </div>
        )}

        {msg.highlighted_nodes?.length > 0 && (
          <div className="highlight-notice">
            ◈ {msg.highlighted_nodes.length} node{msg.highlighted_nodes.length !== 1 ? "s" : ""} highlighted in graph
          </div>
        )}
      </div>
      {isUser && <div className="msg-avatar user-avatar">U</div>}
    </div>
  );
}

function ResultsTable({ results }) {
  if (!results || results.length === 0) return null;
  const cols = Object.keys(results[0]);
  const rows = results.slice(0, 15);

  return (
    <div className="results-table-wrap">
      <table className="results-table">
        <thead>
          <tr>{cols.map((c) => <th key={c}>{c.replace(/_/g, " ")}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>
              {cols.map((c) => <td key={c}>{String(row[c] ?? "—")}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
      {results.length > 15 && (
        <div className="table-overflow">... and {results.length - 15} more rows</div>
      )}
    </div>
  );
}

function ThinkingBubble() {
  return (
    <div className="message assistant">
      <div className="msg-avatar">◈</div>
      <div className="msg-bubble thinking">
        <span className="dot" /><span className="dot" /><span className="dot" />
      </div>
    </div>
  );
}

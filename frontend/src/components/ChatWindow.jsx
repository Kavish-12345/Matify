import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { FIELD_LABELS, missingFields, streamChat } from "../api.js";
import QuestionCard from "./QuestionCard.jsx";
import SummaryCard from "./SummaryCard.jsx";
import { CarLoader, Logo } from "./mech.jsx";

const EXAMPLES = [
  "A bushing that slides on a steel shaft, used outdoors",
  "A lightweight bracket for a drone frame",
  "A gear for an industrial gearbox, machined",
  "A pump housing that sits in sea water",
];

export default function ChatWindow({ options, messages, setMessages, form, setForm, question, setQuestion, pendingPrompt, onPromptConsumed, busy, onConfirm, onEdit }) {
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [cardOpen, setCardOpen] = useState(!!question && question.type !== "text");
  const complete = missingFields(form).length === 0;
  const threadRef = useRef(null);
  const consumedRef = useRef(null);
  const inputRef = useRef(null);

  // example prompt from the homepage: send it once
  useEffect(() => {
    if (pendingPrompt && consumedRef.current !== pendingPrompt && !sending && messages.length === 0) {
      consumedRef.current = pendingPrompt;
      onPromptConsumed?.();
      send(pendingPrompt);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pendingPrompt, messages.length]);

  // a new question (from the chat or from a failed search) opens the card
  useEffect(() => {
    if (question && question.type !== "text") setCardOpen(true);
  }, [question]);

  // scroll only the chat thread, never the page
  useEffect(() => {
    const el = threadRef.current;
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [messages, sending, complete, cardOpen]);

  useEffect(() => {
    const el = inputRef.current;
    if (el) {
      el.style.height = "auto";
      el.style.height = Math.min(el.scrollHeight, 160) + "px";
    }
  }, [text]);

  async function send(raw, direct = null) {
    const content = (raw ?? text).trim();
    if (!content || sending) return;
    const history = [...messages, { role: "user", content }];
    const base = { role: "assistant", content: "", recorded: [] };
    setMessages([...history, base]);
    setText("");
    setCardOpen(false);
    setSending(true);

    let acc = "";
    let warn = "";
    let rec = [];
    let failed = false;
    let opened = false;
    const update = () =>
      setMessages([...history, { ...base, content: acc, warn, recorded: rec, error: failed && !acc }]);

    try {
      await streamChat(
        history,
        form,
        (ev) => {
          if (ev.type === "token") {
            acc += ev.text;
            update();
          } else if (ev.type === "recorded") {
            const fields = ev.items.map((x) => x.field);
            rec = [...rec.filter((r) => !fields.includes(r.field)), ...ev.items]; // no double ticks
            update();
          } else if (ev.type === "error") {
            warn = ev.message;
            failed = true;
            update();
          } else if (ev.type === "done") {
            setForm(ev.form);
            opened = !!ev.question && ev.question.type !== "text" && !ev.complete;
            setQuestion(ev.question);
            setCardOpen(opened);
            if (!acc && !warn) acc = ev.reply;
            update();
          }
        },
        direct
      );
    } catch (err) {
      warn = "Error: " + err.message;
      failed = true;
      update();
    } finally {
      setSending(false);
      if (opened) inputRef.current?.blur(); // let number keys pick card options
      else inputRef.current?.focus();
    }
  }

  function answerFromCard(value, label) {
    send(label, { field: question.field, value, label });
  }

  function onKey(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  }

  function onType(e) {
    setText(e.target.value);
    if (e.target.value && cardOpen) setCardOpen(false); // typing hides the card
  }

  const started = messages.length > 0;
  const last = messages[messages.length - 1];
  const waiting = sending && last?.role === "assistant" && !last.content && !last.warn;
  const showCard = cardOpen && question && !sending && !complete;

  return (
    <div className="chat2">
      <div className="thread" ref={threadRef}>
        <div className="thread-inner">
          {!started && (
            <div className="welcome">
              <div className="welcome-logo"><Logo size={56} /></div>
              <h2>What part are you designing?</h2>
              <p className="muted">
                Describe it in your own words. I'll ask a few quick questions, then the ML engine ranks materials for you.
              </p>
              <div className="examples">
                {EXAMPLES.map((ex) => (
                  <button key={ex} onClick={() => send(ex)}>
                    {ex}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((m, i) =>
            m.role === "user" ? (
              <div key={i} className="msg user">
                <div className="user-bubble">{m.content}</div>
              </div>
            ) : (
              <div key={i} className="msg assistant">
                <div className="avatar"><Logo size={22} /></div>
                <div className="msg-body">
                  {m.warn && <div className="warn">{m.warn}</div>}
                  {m.content ? (
                    <div className="md">
                      <ReactMarkdown>{m.role === "assistant" ? m.content.replace(/`?record_answer\s*\([^)]*\)`?/g, "").trim() : m.content}</ReactMarkdown>
                    </div>
                  ) : (
                    waiting &&
                    i === messages.length - 1 && (
                      <CarLoader label="Thinking…" />
                    )
                  )}
                  {m.recorded?.length > 0 && (
                    <div className="noted">
                      {m.recorded.map((r, j) => (
                        <span key={j} className="noted-chip">
                          <svg viewBox="-10 -10 20 20" width="12" height="12" className="nut" aria-hidden="true">
                            <polygon points="9,0 4.5,7.8 -4.5,7.8 -9,0 -4.5,-7.8 4.5,-7.8" />
                            <circle r="3.5" />
                          </svg>
                          {FIELD_LABELS[r.field] || r.field}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )
          )}

          {complete && !sending && (
            <div className="msg assistant">
              <div className="avatar"><Logo size={22} /></div>
              <div className="msg-body">
                <SummaryCard variant="inline" options={options} form={form} complete busy={busy} onConfirm={onConfirm} onEdit={onEdit} />
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="composer-wrap">
        <div className="composer-col">
          {showCard && <QuestionCard spec={question} onAnswer={answerFromCard} onClose={() => setCardOpen(false)} />}
          {!showCard && question && !complete && !sending && question.type !== "text" && (
            <button className="reopen" onClick={() => setCardOpen(true)}>
              Show answer options
            </button>
          )}
          <div className="composer">
            <textarea
              ref={inputRef}
              rows={1}
              value={text}
              onChange={onType}
              onKeyDown={onKey}
              placeholder={!started ? "Describe your part…" : showCard ? "Or type your own answer…" : "Reply…"}
              disabled={sending}
              autoFocus
            />
            <button className="send" onClick={() => send()} disabled={sending || !text.trim()} aria-label="Send">
              ↑
            </button>
          </div>
          <p className="composer-note">The assistant only collects requirements. Materials are selected by the ML engine after you confirm.</p>
        </div>
      </div>
    </div>
  );
}

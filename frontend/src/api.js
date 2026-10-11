// All backend calls. The backend is stateless; React keeps the conversation and form.

async function request(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail || detail;
    } catch (_) {}
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return res.json();
}

export const getOptions = () => request("/api/options");
export const getPrices = () => request("/api/prices");
export const sendChat = (messages, form) =>
  request("/api/chat", { method: "POST", body: JSON.stringify({ messages, form }) });
// Streaming chat: calls onEvent for each server event (token / recorded / done / error).
export async function streamChat(messages, form, onEvent, directAnswer = null) {
  const res = await fetch("/api/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      messages: messages.map(({ role, content }) => ({ role, content })),
      form,
      direct_answer: directAnswer,
    }),
  });
  if (!res.ok || !res.body) throw new Error(`Chat failed (${res.status})`);
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let i;
    while ((i = buffer.indexOf("\n\n")) >= 0) {
      const line = buffer.slice(0, i).trim();
      buffer = buffer.slice(i + 2);
      if (line.startsWith("data:")) onEvent(JSON.parse(line.slice(5)));
    }
  }
}

export const getRecommendation = (payload) =>
  request("/api/recommend", { method: "POST", body: JSON.stringify(payload) });

export const REQUIRED = ["part_name", "properties", "primary_property", "environment", "weight_priority", "cost_priority"];
export const OPTIONAL = ["volume_cm3", "min_limits", "include", "avoid"];
export const FIELD_ORDER = [...REQUIRED, ...OPTIONAL];

export const FIELD_LABELS = {
  part_name: "Part name",
  properties: "Properties",
  primary_property: "Most important",
  environment: "Environment",
  weight_priority: "Low weight",
  cost_priority: "Low cost",
  volume_cm3: "Part volume",
  min_limits: "Minimum limits",
  include: "Must include",
  avoid: "Avoid",
};

export function emptyForm() {
  const f = {};
  FIELD_ORDER.forEach((k) => (f[k] = null));
  f.user_words = {};
  f.suggested = [];
  return f;
}

// Same conversion for chat and No-AI form, so both give identical results.
export function toPayload(form, priceOverrides = {}, topN = 10) {
  const vol = form.volume_cm3;
  return {
    part_name: form.part_name || null,
    properties: form.properties && form.properties.length ? form.properties : ["not_sure"],
    primary_property: form.primary_property && form.primary_property !== "not_sure" ? form.primary_property : null,
    environment: form.environment || "not_sure",
    weight_priority: form.weight_priority || "not_sure",
    cost_priority: form.cost_priority || "not_sure",
    volume_cm3: typeof vol === "number" && vol > 0 ? vol : null,
    min_limits: form.min_limits && typeof form.min_limits === "object" ? form.min_limits : {},
    include: Array.isArray(form.include) ? form.include : [],
    avoid: Array.isArray(form.avoid) ? form.avoid : [],
    price_overrides: priceOverrides,
    top_n: topN,
  };
}

export const missingFields = (form) => FIELD_ORDER.filter((k) => form[k] === null || form[k] === undefined);

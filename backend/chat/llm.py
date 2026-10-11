"""
Chat interface: the LLM asks questions and fills the fixed form.

Rules enforced here:
  * The LLM has exactly one tool: record_answer(field, value, user_words).
  * Every value is validated by code (form_state.apply_answer).
  * The LLM never sees the dataset, materials, prices or results.
  * The code decides which field to ask next and when the form is complete;
    the engine runs only when the user clicks Confirm (POST /api/recommend).

Backend: Groq (default openai/gpt-oss-120b; Llama 3.3 was retired) via the
OpenAI-compatible API. Ollama offline: LLM_BASE_URL=http://localhost:11434/v1,
LLM_MODEL=llama3.1, LLM_API_KEY=ollama in .env.

chat_events() is a generator of events, used for streaming (SSE):
  {"type": "token", "text": "..."}            piece of the assistant reply
  {"type": "recorded", "items": [...]}        answers saved by record_answer
  {"type": "done", "reply", "form", "missing", "complete", "suggest"}
  {"type": "error", "message": "..."}
"""
from __future__ import annotations

import json
import os

from backend.engine.options import FIELDS, MIN_LIMIT_FIELDS, property_options

from .form_state import FIELD_ORDER, OPTIONAL, REQUIRED, apply_answer, missing_fields, normalise_form

BASE_URL = "https://api.groq.com/openai/v1"
MODEL = "openai/gpt-oss-120b"
MAX_TOOL_ROUNDS = 5

FAMILY_LABELS = {"ferrous": "Steels and cast irons", "aluminium": "Aluminium alloys",
                 "copper": "Copper alloys", "magnesium": "Magnesium alloys"}

QUESTION_HINT = {
    "part_name": "what the part is",
    "properties": "which properties the part needs (they can tick suggestions in the card below)",
    "primary_property": "which of the chosen properties matters most",
    "environment": "where it works (indoors, outdoors, water, chemicals, heat)",
    "weight_priority": "how important low weight is",
    "cost_priority": "how important low cost is",
    "volume_cm3": "the approximate part volume in cm3 (optional, used for cost per part)",
    "min_limits": "any minimum strength/elongation or maximum density limits (optional)",
    "include": "any material families they must use (optional)",
    "avoid": "any material families they want to avoid (optional)",
}

RECORD_TOOL = {
    "type": "function",
    "function": {
        "name": "record_answer",
        "description": "Record ONE answer the user has clearly given for ONE form field. "
                       "Call it once per field. Never record a value the user did not say.",
        "parameters": {
            "type": "object",
            "properties": {
                "field": {"type": "string", "enum": FIELD_ORDER + ["suggested_properties"]},
                "value": {"type": "string", "description": "Allowed option value(s). For 'properties' and "
                          "'suggested_properties' use a comma-separated list of class names. "
                          "Use 'not_sure' if the user is not sure."},
                "user_words": {"type": "string", "description": "The user's own words that justify this value."},
            },
            "required": ["field", "value", "user_words"],
        },
    },
}


def _client():
    from openai import OpenAI
    key = os.getenv("GROQ_API_KEY") or os.getenv("LLM_API_KEY")
    if not key:
        raise RuntimeError("No API key. Put GROQ_API_KEY=... in the .env file in the project root.")
    return OpenAI(api_key=key, base_url=os.getenv("LLM_BASE_URL", BASE_URL))


def group_labels(price_categories: dict) -> dict:
    return {**FAMILY_LABELS, **{k: v["label"] for k, v in price_categories.items()}}


QUESTION_TITLE = {
    "part_name": "What part are you designing?",
    "properties": "Which properties does the part need?",
    "primary_property": "Which one matters most?",
    "environment": "Where will it work?",
    "weight_priority": "How important is low weight?",
    "cost_priority": "How important is low cost?",
    "volume_cm3": "Approximate part volume?",
    "min_limits": "Any minimum property limits?",
    "include": "Only consider certain materials?",
    "avoid": "Any materials to avoid?",
}

LIMIT_UNITS = {"Su": "MPa", "Sy": "MPa", "A5": "%", "E": "MPa", "Ro_max": "kg/m³"}
LIMIT_HINTS = {"Su": "e.g. 600", "Sy": "e.g. 400", "A5": "e.g. 10", "E": "steel ≈ 210000",
               "Ro_max": "steel ≈ 7850, Al ≈ 2700"}


def question_spec(field: str | None, groups: dict, form: dict, classes: list[str] | None = None) -> dict | None:
    """Everything the UI needs to draw the question card for the next field."""
    if field is None:
        return None
    spec = {"field": field, "title": QUESTION_TITLE[field], "optional": field in OPTIONAL,
            "step": FIELD_ORDER.index(field) + 1, "total": len(FIELD_ORDER)}
    if field == "part_name":
        spec.update(type="text", options=[])
    elif field == "properties":
        # options = the classes the trained model predicts (not a hand-made list)
        spec.update(type="multi", options=property_options(classes or []),
                    preselected=[c for c in form.get("suggested") or [] if c in (classes or [])],
                    subtitle="Suggested from your description - please confirm" if form.get("suggested") else "")
    elif field == "primary_property":
        chosen = [p for p in form.get("properties") or [] if p != "not_sure"]
        desc = {o["value"]: o for o in property_options(classes or [])}
        spec.update(type="single", options=[{"value": c, "label": c, "description": desc.get(c, {}).get("description", "")}
                                            for c in chosen])
    elif field in FIELDS:
        spec.update(type="single", options=[{"value": k, "label": v["label"]}
                                            for k, v in FIELDS[field].items() if k != "not_sure"])
    elif field == "volume_cm3":
        spec.update(type="number", unit="cm³", hint="Used to show cost per part", options=[])
    elif field == "min_limits":
        spec.update(type="limits", options=[{"value": k, "label": MIN_LIMIT_FIELDS[k], "unit": LIMIT_UNITS[k],
                                             "hint": LIMIT_HINTS[k]} for k in MIN_LIMIT_FIELDS])
    else:  # include / avoid
        other = form.get("avoid" if field == "include" else "include") or []
        spec.update(type="multi", options=[{"value": k, "label": v, "disabled": k in other}
                                           for k, v in groups.items()])
    return spec


def _options_text(groups: dict, classes: list[str]) -> str:
    lines = []
    props = "; ".join(f"{o['value']} ({o['description']})" for o in property_options(classes))
    lines.append(f"- properties (one or more, use these exact class names): {props}")
    lines.append("- primary_property: one of the chosen properties (asked only if two or more are chosen)")
    for f in FIELDS:
        opts = "; ".join(f"{k} = {v['label']}" for k, v in FIELDS[f].items())
        lines.append(f"- {f}: {opts}")
    lines.append("- part_name: free text, e.g. 'gear shaft'")
    lines.append("- volume_cm3 (optional): number in cm3, or not_sure")
    lims = ", ".join(f"{k} = {v}" for k, v in MIN_LIMIT_FIELDS.items())
    lines.append(f"- min_limits (optional): e.g. 'Sy=400, Ro_max=3000', or none. Keys: {lims}")
    grp = "; ".join(f"{k} = {v}" for k, v in groups.items())
    lines.append(f"- include / avoid (optional): comma-separated group keys, or none. Groups: {grp}")
    return "\n".join(lines)


def _system_prompt(form: dict, groups: dict, classes: list[str], button_answer: bool = False) -> str:
    filled = {f: form[f] for f in FIELD_ORDER if form.get(f) is not None}
    missing = missing_fields(form)
    nxt = missing[0] if missing else None
    ask = (f"Next, ask ONE short question about {QUESTION_HINT[nxt]} (field '{nxt}')."
           if nxt else "Nothing is missing. Say in one short sentence that everything is noted and they can "
                       "review the summary card and press Confirm. Do not list the answers.")
    return f"""You are Matify's friendly requirements assistant for choosing a material for a mechanical part.
Your only job is to fill a fixed form by calling record_answer, then ask the next question.

How to talk:
- Write like a helpful engineer in a chat: warm, brief, natural. One or two short sentences.
- Ask about ONE thing at a time. No lists, no bullet points, no headings, no bold, no markdown.
- Never show internal codes such as not_important or sheet_forming. Use everyday words.
- The user can also click quick-reply buttons, so you do not need to list the options.
- Briefly acknowledge what you understood when useful (e.g. "Got it, indoors and machined.").

Recording rules:
- First record every answer the user gave in their latest message (one record_answer call per field).
- Record only what the user clearly said. Never assume. If unclear, ask a short clarifying question.
- "Not sure" / "don't know" -> value not_sure. Optional fields can be "none".
- Map the user's words to the allowed values exactly (e.g. "Outdoors / humid" -> outdoor_humid).
- Properties: after the user describes the part, call record_answer(field="suggested_properties") with the
  classes their description clearly points to (e.g. "bushing" -> Wear-resistant). These are ONLY suggestions,
  shown pre-ticked for the user to confirm. Record field "properties" yourself only if the user explicitly
  names or confirms the properties in their own words.
- You do NOT know any materials, properties or prices. Never suggest or name materials, even if asked;
  say the recommendation engine does that after they confirm.

Allowed values:
{_options_text(groups, classes)}
{"The user's latest message was a button click and is ALREADY recorded. Do not call record_answer for it; just acknowledge briefly and ask the next question." if button_answer else ""}

Already recorded: {json.dumps(filled, ensure_ascii=False)}
{ask}"""


def _apply_tool_calls(tool_calls: list[dict], form: dict, group_keys: list[str], recorded: list, errors: list, msgs: list,
                      classes: list[str]):
    msgs.append({"role": "assistant", "content": "",
                 "tool_calls": [{"id": tc["id"], "type": "function",
                                 "function": {"name": tc["name"], "arguments": tc["arguments"]}}
                                for tc in tool_calls]})
    new_items = []
    for tc in tool_calls:
        try:
            args = json.loads(tc["arguments"] or "{}")
        except json.JSONDecodeError:
            args = {}
        if tc["name"] != "record_answer":
            result = "error: the only tool is record_answer"
        else:
            err = apply_answer(form, args.get("field", ""), args.get("value"), args.get("user_words", ""),
                               group_keys, classes)
            if err:
                errors.append(err)
                result = f"error: {err}"
            elif args.get("field") == "suggested_properties":
                result = "suggestions saved (the user will confirm them in the card)"
            else:
                item = {"field": args["field"], "value": form[args["field"]], "user_words": args.get("user_words", "")}
                recorded[:] = [r for r in recorded if r["field"] != item["field"]] + [item]
                new_items = [r for r in new_items if r["field"] != item["field"]] + [item]
                result = "recorded"
        left = missing_fields(form)
        msgs.append({"role": "tool", "tool_call_id": tc["id"],
                     "content": f"{result}. Next field to ask: {left[0] if left else 'none - form complete'}"})
    return new_items


def chat_events(messages: list[dict], form: dict | None, price_categories: dict, direct_answer: dict | None = None,
                classes: list[str] | None = None):
    """
    Generator of chat events (see module docstring). Streams the reply text token by token.
    direct_answer = {"field", "value", "label"} from a question-card click: recorded by code, no LLM mapping.
    """
    form = normalise_form(form)
    classes = classes or []
    groups = group_labels(price_categories)
    group_keys = list(groups)
    button = False
    if direct_answer and direct_answer.get("field"):
        err = apply_answer(form, direct_answer["field"], direct_answer.get("value"),
                           direct_answer.get("label", ""), group_keys, classes)
        if err:
            # invalid click/entry: explain and ask the same question again (no LLM call needed)
            missing = missing_fields(form)
            yield {"type": "error", "message": err + " Please answer this question again."}
            yield {"type": "done", "reply": "", "form": form, "recorded": [], "errors": [err],
                   "missing": missing, "complete": not missing,
                   "question": question_spec(missing[0] if missing else None, groups, form, classes)}
            return
        button = True
        yield {"type": "recorded", "items": [{"field": direct_answer["field"],
                                              "value": form[direct_answer["field"]],
                                              "user_words": direct_answer.get("label", "")}]}
    history = [{"role": m["role"], "content": str(m.get("content", ""))[:2000]}
               for m in messages if m.get("role") in ("user", "assistant") and m.get("content")][-20:]
    recorded, errors, reply = [], [], ""

    try:
        client = _client()
        model = os.getenv("LLM_MODEL", MODEL)
        extra = {"extra_body": {"reasoning_effort": "low"}} if "gpt-oss" in model else {}
        msgs = [{"role": "system", "content": _system_prompt(form, groups, classes, button)}] + history

        for _ in range(MAX_TOOL_ROUNDS):
            tool_args = {} if button else {"tools": [RECORD_TOOL], "tool_choice": "auto"}
            stream = client.chat.completions.create(
                model=model, messages=msgs, temperature=0.3, max_tokens=2000, stream=True,
                **tool_args, **extra,
            )
            calls: dict[int, dict] = {}
            text = ""
            for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                if getattr(delta, "content", None):
                    text += delta.content
                    yield {"type": "token", "text": delta.content}
                for tc in getattr(delta, "tool_calls", None) or []:
                    c = calls.setdefault(tc.index, {"id": "", "name": "", "arguments": ""})
                    if tc.id:
                        c["id"] = tc.id
                    if tc.function and tc.function.name:
                        c["name"] += tc.function.name
                    if tc.function and tc.function.arguments:
                        c["arguments"] += tc.function.arguments
            reply += text
            button = False
            if not calls:
                break
            items = _apply_tool_calls([calls[i] for i in sorted(calls)], form, group_keys, recorded, errors, msgs, classes)
            if items:
                yield {"type": "recorded", "items": items}
            # refresh the instructions so the model asks about the new next field
            msgs[0] = {"role": "system", "content": _system_prompt(form, groups, classes)}

        if not reply.strip():
            missing = missing_fields(form)
            reply = ("That's everything I need. Review the summary and press Confirm when you're ready."
                     if not missing else f"Thanks! Could you tell me {QUESTION_HINT[missing[0]]}?")
            yield {"type": "token", "text": reply}
    except Exception as e:  # network / key / model errors -> friendly message, form kept
        reply = (f"Sorry, the chat service is unavailable right now ({type(e).__name__}: {str(e)[:150]}). "
                 "You can switch to Form mode; it gives identical results.")
        yield {"type": "error", "message": reply}

    missing = missing_fields(form)
    yield {"type": "done", "reply": reply.strip(), "form": form, "recorded": recorded, "errors": errors,
           "missing": missing, "complete": not missing,
           "question": question_spec(missing[0] if missing else None, groups, form, classes)}


def chat_turn(messages: list[dict], form: dict | None, price_categories: dict, direct_answer: dict | None = None,
              classes: list[str] | None = None) -> dict:
    """Non-streaming version (same logic): returns the final 'done' event."""
    last = {}
    for ev in chat_events(messages, form, price_categories, direct_answer, classes):
        last = ev
    return last

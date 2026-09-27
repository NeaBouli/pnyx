# MOD-22 Citizen Assistant — Prompt Trust Boundary (EKA-58)

Scope: `POST /api/v1/agent/ask` (`apps/api/routers/agent.py`) and its Ollama
path (`apps/api/services/ollama_service.py::answer_citizen_question`).
Implementation: `apps/api/services/agent_prompt.py`.
Tests: `apps/api/tests/test_agent_prompt_trust_boundary.py`.

## Trust levels

| Level | Content | Handling |
|---|---|---|
| Trusted | System rules in `agent_prompt._SYSTEM_RULES`, date line | Sent only in the provider's separate `system` field |
| Untrusted data | Parliament bill titles, Diavgeia-derived titles, AI-generated `pill_el`, knowledge-base rows, DeepL translations of those | Normalised, serialised, escaped, placed only inside the data block in the user turn |
| Untrusted input | Citizen question | Normalised and JSON-encoded after the data block |
| Untrusted output | Ollama / Claude answers | Output guard before returning to the client |

Official sources are lower-trust than the prompt: government sites are not
controlled by this project and ~1 775 Diavgeia publishing organisations are
ingested. Forum posts and GitHub issues are not ingested by the assistant.

## Input side

1. **Deterministic character/length control** (`sanitize_untrusted_text`):
   control, format (zero-width, bidi override), surrogate, private-use and
   unassigned code points are removed; whitespace is collapsed; hard per-field
   caps (title 300, summary 200, KB content 1 500, translated context 2 000,
   question 500 characters). Words and punctuation are never rewritten, so
   legitimate titles remain quotable verbatim.
2. **Unambiguous serialisation**: one JSON object per line inside a single
   `<untrusted_data>` … `</untrusted_data>` block. `<`, `>` and `&` are
   emitted as JSON `\u` escapes, so no field value can open or close the
   block; `json.loads` restores the original text. The whole block is capped
   at 12 000 characters; overflowing records are dropped whole.
3. **Explicit system rule**: everything inside the block is data, never
   instructions; requests or role changes inside it are not followed.
4. **One builder for both providers**: `build_agent_prompt()` returns
   `(system, user)`. Claude receives them as `system` / `messages[0]`,
   Ollama as `system` / `prompt` of `/api/generate`. Tests assert both
   payloads are identical apart from the date line. When DeepL translates the
   context for Ollama, the translation is treated as untrusted and re-enters
   the block as one escaped record.

## Output side

`is_unsafe_model_output()` flags answers that echo instructions, disclose the
system prompt (pattern match and verbatim overlap with any rule sentence), or
contain role-override / chat-template markers. The Ollama answer is checked
before and after the DeepL back-translation; the Claude answer is checked
before return. A hit returns a neutral fail-closed answer (EL or EN by
request language, `model: "output-guard"`, no sources) and never echoes the
rejected text. There is no fallback to the other model after a hit.

The pattern list is a second layer; the structural separation above is the
primary control. Patterns are tuned to avoid civic false positives (e.g.
"the rules state", "κανόνες του συστήματος υγείας").

## Residual risks

- A model can still be influenced semantically by data it reads (e.g. biased
  wording in an official title); delimiters reduce but do not eliminate this.
- The output guard is heuristic: paraphrased leaks or novel role markers may
  pass. Canonical answers (`_canonical_response`) never reach a model.
- `sources[].title` returned to the client carries the original bill title;
  rendering safety relies on the frontend escaping (see EKA-62).
- `/api/v1/claude/ask` is a separate endpoint and not covered here (EKA-61).

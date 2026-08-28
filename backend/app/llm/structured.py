from __future__ import annotations

import json
import re
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from app.llm.base import LLMClient, LLMRequest, Message

T = TypeVar("T", bound=BaseModel)


def _unwrap_array(raw, schema: type[T]):
    if isinstance(raw, list) and hasattr(schema, "model_fields") and len(schema.model_fields) > 1:
        first = raw[0] if raw else None
        if isinstance(first, dict):
            known_fields = set(schema.model_fields)
            if known_fields & set(first):
                target_field = next(
                    (f for f in schema.model_fields if f not in ("id",)), None
                )
                for field in schema.model_fields:
                    field_type = schema.model_fields[field].annotation
                    origin = getattr(field_type, "__origin__", None)
                    if origin is list:
                        return schema.model_validate({field: raw})
                if target_field:
                    return schema.model_validate({target_field: raw})
    return raw


def _unwrap_object(raw, schema: type[T]):
    """Unwrap a common provider-added result envelope around structured JSON."""
    if not isinstance(raw, dict) or not hasattr(schema, "model_fields"):
        return raw

    known_fields = set(schema.model_fields)
    if known_fields & set(raw):
        return raw

    for value in raw.values():
        if isinstance(value, dict) and known_fields & set(value):
            return value
    return raw


_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def extract_json_payload(text: str) -> str | None:
    fenced = _FENCE_RE.search(text)
    if fenced:
        text = fenced.group(1)
    start_candidates = [i for i, ch in enumerate(text) if ch in "{["]
    for start in start_candidates:
        opener = text[start]
        closer = "}" if opener == "{" else "]"
        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(text)):
            ch = text[i]
            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
            elif ch == opener:
                depth += 1
            elif ch == closer:
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]
    return None


class StructuredGenerationError(RuntimeError):
    def __init__(self, step: str, attempts: int, last_error: str) -> None:
        self.step = step
        self.attempts = attempts
        self.last_error = last_error
        super().__init__(
            f"step '{step}' failed to produce valid output after {attempts} attempt(s): {last_error}"
        )


async def generate_structured(
    client: LLMClient,
    schema: type[T],
    *,
    step: str,
    system_prompt: str,
    user_prompt: str,
    max_retries: int = 2,
    max_tokens: int | None = None,
    temperature: float | None = None,
    frequency_penalty: float | None = None,
) -> T:
    history: list[Message] = []
    last_error = ""
    attempts = max_retries + 1

    for attempt in range(attempts):
        request = LLMRequest(
            step=step,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            history=list(history),
            json_mode=True,
            max_tokens=max_tokens,
            temperature=temperature,
            frequency_penalty=frequency_penalty,
        )
        response = await client.complete(request)

        payload_text = extract_json_payload(response.text)
        if payload_text is None:
            looks_truncated = (
                len(response.text) > 4000
                and response.text.count("{") != response.text.count("}")
            )
            if looks_truncated:
                raise StructuredGenerationError(
                    step,
                    attempt + 1,
                    "output truncated at token limit with unbalanced JSON; "
                    "instruct model to emit terser output or raise max_tokens",
                )
            last_error = "no JSON object found in model output"
        else:
            try:
                raw = json.loads(payload_text)
                raw = _unwrap_array(raw, schema)
                raw = _unwrap_object(raw, schema)
                if (
                    isinstance(raw, dict)
                    and hasattr(schema, "model_fields")
                    and not (set(schema.model_fields) & set(raw))
                ):
                    raise ValueError(
                        "output has no recognized top-level schema fields: "
                        f"expected one of {sorted(schema.model_fields)}"
                    )
                return schema.model_validate(raw)
            except json.JSONDecodeError as exc:
                last_error = f"invalid JSON: {exc}"
            except ValidationError as exc:
                last_error = f"schema validation failed: {exc.error_count()} error(s): {exc.errors()[:3]}"
            except ValueError as exc:
                last_error = f"schema validation failed: {exc}"

        history.append(Message(role="assistant", content=response.text))
        history.append(
            Message(
                role="user",
                content=(
                    f"Your previous output was invalid: {last_error}\n"
                    f"Return ONLY corrected JSON matching the required schema. No prose."
                ),
            )
        )

    raise StructuredGenerationError(step, attempts, last_error)

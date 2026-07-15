from __future__ import annotations

import json
import re
import socket
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, Request, build_opener

from .analytics_nl_translation import SemanticTranslationPrompt
from .analytics_query_plan import (
    ALLOWED_FILTERS,
    IDENTIFIER_PATTERN,
    MAX_DIMENSIONS,
    MAX_FILTERS,
    MAX_IN_VALUES,
    MAX_LIMIT,
    MAX_METRICS,
    MAX_ORDER_RULES,
)
from .analytics_semantic_adapter import MAX_RELATIONSHIP_PATHS


DEFAULT_OLLAMA_ENDPOINT = "http://127.0.0.1:11434"
DEFAULT_OLLAMA_MODEL = "gpt-oss:20b"
DEFAULT_CONTEXT_TOKENS = 8_192
DEFAULT_MAX_OUTPUT_TOKENS = 1_024
DEFAULT_KEEP_ALIVE = "2m"
MAX_OLLAMA_REQUEST_BYTES = 512_000
MAX_OLLAMA_HTTP_RESPONSE_BYTES = 2_000_000
MODEL_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
LOOPBACK_HOSTS = {"127.0.0.1", "::1"}


class OllamaProviderError(RuntimeError):
    """Raised when a local Ollama response cannot satisfy the provider boundary."""


def validate_loopback_endpoint(endpoint: str) -> str:
    if not isinstance(endpoint, str) or not endpoint.strip():
        raise ValueError("Ollama endpoint must be a non-empty loopback HTTP URL.")
    parsed = urlsplit(endpoint.strip())
    try:
        port = parsed.port
    except ValueError as error:
        raise ValueError("Ollama endpoint contains an invalid port.") from error
    if (
        parsed.scheme != "http"
        or parsed.hostname not in LOOPBACK_HOSTS
        or port is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            "Ollama endpoint must be an explicit loopback HTTP origin with a port and no path."
        )
    host = f"[{parsed.hostname}]" if parsed.hostname == "::1" else parsed.hostname
    return f"http://{host}:{port}"


def _semantic_id_schema(semantic_context: dict[str, Any], collection: str) -> dict[str, Any]:
    rows = semantic_context.get(collection, [])
    identifiers = sorted(
        {
            row["id"]
            for row in rows
            if isinstance(row, dict) and isinstance(row.get("id"), str) and row["id"]
        }
    ) if isinstance(rows, list) else []
    schema: dict[str, Any] = {"type": "string", "minLength": 1}
    if identifiers:
        schema["enum"] = identifiers
    return schema


def ollama_semantic_response_schema(semantic_context: dict[str, Any]) -> dict[str, Any]:
    table_id = _semantic_id_schema(semantic_context, "tables")
    relationship_path_id = _semantic_id_schema(semantic_context, "relationship_paths")
    dimension_id = _semantic_id_schema(semantic_context, "dimensions")
    measure_id = _semantic_id_schema(semantic_context, "measures")
    selection = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "term": {"type": "string", "minLength": 1},
            "alias": {
                "type": "string",
                "pattern": IDENTIFIER_PATTERN.pattern,
            },
        },
        "required": ["term"],
    }
    scalar = {"type": ["string", "number", "boolean"]}
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "version": {"type": "integer", "const": 1},
            "from": table_id,
            "relationship_paths": {
                "type": "array",
                "items": relationship_path_id,
                "maxItems": MAX_RELATIONSHIP_PATHS,
            },
            "dimensions": {
                "type": "array",
                "items": {
                    **selection,
                    "properties": {**selection["properties"], "term": dimension_id},
                },
                "maxItems": MAX_DIMENSIONS,
            },
            "metrics": {
                "type": "array",
                "items": {
                    **selection,
                    "properties": {**selection["properties"], "term": measure_id},
                },
                "maxItems": MAX_METRICS,
            },
            "filters": {
                "type": "array",
                "maxItems": MAX_FILTERS,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "term": dimension_id,
                        "operator": {"type": "string", "enum": sorted(ALLOWED_FILTERS)},
                        "value": {
                            "anyOf": [
                                scalar,
                                {
                                    "type": "array",
                                    "items": scalar,
                                    "minItems": 1,
                                    "maxItems": MAX_IN_VALUES,
                                },
                            ]
                        },
                    },
                    "required": ["term", "operator"],
                },
            },
            "order_by": {
                "type": "array",
                "maxItems": MAX_ORDER_RULES,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "field": {
                            "type": "string",
                            "pattern": IDENTIFIER_PATTERN.pattern,
                        },
                        "direction": {"type": "string", "enum": ["asc", "desc"]},
                    },
                    "required": ["field", "direction"],
                },
            },
            "limit": {"type": "integer", "minimum": 1, "maximum": MAX_LIMIT},
        },
        "required": ["version", "from"],
    }


def _open_without_proxy(request: Request, timeout_seconds: int):
    return build_opener(ProxyHandler({})).open(request, timeout=timeout_seconds)


class OllamaSemanticIntentProvider:
    mode = "local_live"
    network_access_required = True

    def __init__(
        self,
        *,
        endpoint: str = DEFAULT_OLLAMA_ENDPOINT,
        model: str = DEFAULT_OLLAMA_MODEL,
        context_tokens: int = DEFAULT_CONTEXT_TOKENS,
        max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
    ) -> None:
        self.endpoint = validate_loopback_endpoint(endpoint)
        if not isinstance(model, str) or MODEL_NAME_PATTERN.fullmatch(model) is None:
            raise ValueError("Ollama model name contains unsupported characters or length.")
        if (
            isinstance(context_tokens, bool)
            or not isinstance(context_tokens, int)
            or not 1_024 <= context_tokens <= 131_072
        ):
            raise ValueError("Ollama context tokens must be between 1024 and 131072.")
        if (
            isinstance(max_output_tokens, bool)
            or not isinstance(max_output_tokens, int)
            or not 1 <= max_output_tokens <= 8_192
        ):
            raise ValueError("Ollama maximum output tokens must be between 1 and 8192.")
        self.model = model
        self.context_tokens = context_tokens
        self.max_output_tokens = max_output_tokens
        self.name = f"ollama:{model}"

    def translate(
        self,
        prompt: SemanticTranslationPrompt,
        *,
        timeout_seconds: int,
    ) -> dict[str, Any]:
        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, int)
            or timeout_seconds < 1
        ):
            raise ValueError("Ollama timeout must be a positive integer.")
        user_payload = {
            "question": prompt.question,
            "semantic_context": prompt.semantic_context,
            "response_contract": prompt.response_schema,
        }
        request_payload = {
            "model": self.model,
            "stream": False,
            "keep_alive": DEFAULT_KEEP_ALIVE,
            "format": ollama_semantic_response_schema(prompt.semantic_context),
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Translate one English analytical question into one semantic intent. "
                        "Use only supplied approved semantic entity IDs from each object's id field. "
                        "The from field must be a tables ID. Relationship path IDs belong only in "
                        "relationship_paths; dimension IDs belong only in dimensions and filters; "
                        "measure IDs belong only in metrics. "
                        "Return exactly one JSON object matching the response schema. "
                        "Never return the question, SQL, physical tables, physical columns, joins, "
                        "Markdown, explanations, or unsupported fields."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        user_payload,
                        ensure_ascii=True,
                        separators=(",", ":"),
                    ),
                },
            ],
            "options": {
                "temperature": 0,
                "num_ctx": self.context_tokens,
                "num_predict": self.max_output_tokens,
            },
        }
        body = json.dumps(
            request_payload,
            ensure_ascii=True,
            separators=(",", ":"),
        ).encode("utf-8")
        if len(body) > MAX_OLLAMA_REQUEST_BYTES:
            raise OllamaProviderError("The minimized Ollama request exceeds its local size limit.")
        request = Request(
            f"{self.endpoint}/api/chat",
            data=body,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        try:
            with _open_without_proxy(request, timeout_seconds) as response:
                raw = response.read(MAX_OLLAMA_HTTP_RESPONSE_BYTES + 1)
        except (socket.timeout, TimeoutError) as error:
            raise TimeoutError("The local Ollama request timed out.") from error
        except (HTTPError, URLError, OSError) as error:
            raise OllamaProviderError("The local Ollama endpoint request failed.") from error
        if len(raw) > MAX_OLLAMA_HTTP_RESPONSE_BYTES:
            raise OllamaProviderError("The local Ollama response exceeds its size limit.")
        try:
            envelope = json.loads(raw.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as error:
            raise OllamaProviderError("The local Ollama endpoint returned invalid JSON.") from error
        if not isinstance(envelope, dict) or envelope.get("error"):
            raise OllamaProviderError("The local Ollama endpoint returned an error response.")
        message = envelope.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            raise OllamaProviderError("The local Ollama response did not contain semantic JSON.")
        try:
            payload = json.loads(content)
        except json.JSONDecodeError as error:
            raise OllamaProviderError("The local Ollama semantic response is not valid JSON.") from error
        if not isinstance(payload, dict):
            raise OllamaProviderError("The local Ollama semantic response must be a JSON object.")
        return payload

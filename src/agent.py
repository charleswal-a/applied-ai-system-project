"""
Agentic pipeline that turns a free-text listening request into a taste
profile, checks it against the song catalog, and reviews the scored
recommendations before they're shown to the user. Uses Groq's chat
completions API (OpenAI-compatible).

Pipeline: parse_profile_from_text -> check_catalog_guardrails (no LLM) ->
recommend_songs (unchanged scoring, see recommender.py) -> review_and_summarize
-> (optional) refine_profile, looped by the caller in main.py.
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, List

import groq
from dotenv import load_dotenv
from groq import Groq

# Loads GROQ_API_KEY from a .env file at the project root, if present, without
# overriding a key already set in the shell environment.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

logger = logging.getLogger(__name__)

MODEL = "llama-3.3-70b-versatile"

PROFILE_SCHEMA = {
    "type": "object",
    "properties": {
        "genre": {"type": "string", "description": "Short lowercase genre tag, e.g. 'lofi'."},
        "mood": {"type": "string", "description": "Short lowercase mood tag, e.g. 'chill'."},
        "energy": {"type": "number", "description": "Desired intensity from 0.0 (calm) to 1.0 (intense)."},
        "likes_acoustic": {"type": "boolean", "description": "True if they want acoustic/organic sound."},
    },
    "required": ["genre", "mood", "energy", "likes_acoustic"],
}

REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "status": {"type": "string", "description": "One of: satisfied, needs_clarification."},
        "summary": {"type": "string", "description": "A short, friendly summary for the user."},
        "clarifying_question": {
            "anyOf": [{"type": "string"}, {"type": "null"}],
            "description": "One follow-up question, or null if status is 'satisfied'.",
        },
    },
    "required": ["status", "summary", "clarifying_question"],
}

_TYPE_MAP = {"string": str, "number": (int, float), "boolean": bool, "object": dict, "array": list}


class AgentUnavailableError(RuntimeError):
    """Raised when the AI-assisted pipeline can't be used (missing key, API failure, bad response)."""


def get_client() -> Groq:
    if not os.environ.get("GROQ_API_KEY"):
        raise AgentUnavailableError(
            "GROQ_API_KEY is not set. Get a free key from https://console.groq.com/keys and either "
            "export it as an environment variable or put it in the .env file at the project root "
            "(copy .env.example to .env and fill in GROQ_API_KEY=...)."
        )
    return Groq(api_key=os.environ["GROQ_API_KEY"])


def _describe_schema(schema: dict) -> str:
    lines = ["{"]
    for key, spec in schema["properties"].items():
        type_name = spec.get("type", "string or null")
        description = spec.get("description", "")
        lines.append(f'  "{key}": {type_name}' + (f"  // {description}" if description else ""))
    lines.append("}")
    return "\n".join(lines)


def _validate(data, schema: dict) -> None:
    if not isinstance(data, dict):
        raise AgentUnavailableError(f"Model response was not a JSON object: {data!r}")
    for key in schema["required"]:
        if key not in data:
            raise AgentUnavailableError(f"Model response missing required field '{key}': {data!r}")
    for key, spec in schema["properties"].items():
        if key not in data or "anyOf" in spec:
            continue
        expected_type = _TYPE_MAP[spec["type"]]
        if not isinstance(data[key], expected_type):
            raise AgentUnavailableError(f"Field '{key}' had an unexpected type: {data[key]!r}")


def _call_json(client: Groq, system: str, user: str, schema: dict) -> dict:
    full_system = f"{system}\n\nRespond with ONLY a JSON object matching this shape:\n{_describe_schema(schema)}"
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": full_system},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
        )
    except groq.AuthenticationError as e:
        raise AgentUnavailableError(f"Groq API key was rejected: {e.message}") from e
    except groq.RateLimitError as e:
        raise AgentUnavailableError(f"Groq API rate limit hit: {e.message}") from e
    except groq.APIConnectionError as e:
        raise AgentUnavailableError(f"Could not reach the Groq API: {e}") from e
    except groq.APIStatusError as e:
        raise AgentUnavailableError(f"Groq API error ({e.status_code}): {e.message}") from e

    content = response.choices[0].message.content or ""
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        raise AgentUnavailableError(f"Model returned malformed JSON: {e}") from e

    _validate(data, schema)
    return data


def parse_profile_from_text(client: Groq, text: str) -> Dict:
    system = (
        "You extract a music taste profile from a listener's free-text request. "
        "genre and mood should be short lowercase tags (e.g. 'lofi', 'chill'). "
        "energy is a float between 0 and 1 estimating desired intensity. "
        "likes_acoustic is true if they want acoustic/organic instrumentation, false for "
        "electric/electronic/produced sound. Make your best guess even if the request is vague."
    )
    profile = _call_json(client, system, text, PROFILE_SCHEMA)
    logger.info("Parsed profile from %r: %s", text, profile)
    return profile


def check_catalog_guardrails(profile: Dict, songs: List[Dict]) -> List[str]:
    """Flags catalog gaps and internal contradictions. May clamp profile['energy'] in place."""
    warnings: List[str] = []
    genres = {s["genre"] for s in songs}
    moods = {s["mood"] for s in songs}

    genre = profile.get("genre")
    mood = profile.get("mood")
    energy = profile.get("energy")
    likes_acoustic = profile.get("likes_acoustic")

    if genre and genre not in genres:
        warnings.append(
            f"No songs in the catalog are tagged genre='{genre}' — genre matching will score 0 for every song."
        )
    if mood and mood not in moods:
        warnings.append(
            f"No songs in the catalog are tagged mood='{mood}' — mood matching will score 0 for every song."
        )
    if energy is not None and not (0.0 <= energy <= 1.0):
        clamped = max(0.0, min(1.0, energy))
        warnings.append(f"target_energy {energy} is outside [0, 1]; clamping to {clamped}.")
        profile["energy"] = clamped
    if likes_acoustic and genre:
        genre_songs = [s for s in songs if s["genre"] == genre]
        if genre_songs:
            avg_acoustic = sum(s["acousticness"] for s in genre_songs) / len(genre_songs)
            if avg_acoustic < 0.3:
                warnings.append(
                    f"You asked for acoustic sound, but '{genre}' songs in the catalog average "
                    f"{avg_acoustic:.2f} acousticness — these two preferences are in tension."
                )

    for warning in warnings:
        logger.warning(warning)
    return warnings


def review_and_summarize(client: Groq, profile: Dict, warnings: List[str], results: List) -> Dict:
    results_desc = [
        {"title": song["title"], "score": round(score, 2), "reasons": reasons}
        for song, score, reasons in results
    ]
    user = json.dumps({"profile": profile, "guardrail_warnings": warnings, "top_results": results_desc})
    system = (
        "You are reviewing music recommendations before they're shown to a user. Given their taste "
        "profile, any guardrail warnings about catalog gaps or contradictions, and the top scored "
        "results, decide whether these results are good enough to present as-is ('satisfied') or "
        "whether one targeted clarifying question would meaningfully improve them "
        "('needs_clarification' — e.g. the warnings show the catalog can't satisfy the request as "
        "stated, or every score is low). Write a short, friendly summary that references the actual "
        "songs and warnings given — never invent songs that aren't in top_results. If status is "
        "'satisfied', clarifying_question must be null."
    )
    review = _call_json(client, system, user, REVIEW_SCHEMA)
    logger.info("Review: %s", review)
    return review


def refine_profile(client: Groq, profile: Dict, question: str, answer: str) -> Dict:
    system = (
        "You update a music taste profile based on the user's answer to a clarifying question. "
        "Keep whatever from the existing profile is still accurate; only change what the answer "
        "addresses. Return the profile using the same genre/mood/energy/likes_acoustic schema."
    )
    user = json.dumps({"current_profile": profile, "clarifying_question": question, "user_answer": answer})
    updated = _call_json(client, system, user, PROFILE_SCHEMA)
    logger.info("Refined profile: %s", updated)
    return updated

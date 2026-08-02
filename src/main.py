"""
Command line runner for the Music Recommender Simulation.

Asks for a free-text listening request and runs it through the agentic
pipeline in agent.py (parse -> guardrail check -> recommend -> review/clarify,
looped up to MAX_CLARIFY_ROUNDS times). If GROQ_API_KEY is missing or any
Groq call fails, falls back to manual input() prompts so recommendations
still get produced.
"""

import logging
import os

from src.agent import (
    AgentUnavailableError,
    check_catalog_guardrails,
    get_client,
    parse_profile_from_text,
    refine_profile,
    review_and_summarize,
)
from src.recommender import load_songs, recommend_songs

MAX_CLARIFY_ROUNDS = 2
DEFAULT_REQUEST = "Something upbeat and happy for a pop fan."
LOG_PATH = "logs/session.log"


def _setup_logging() -> None:
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    logging.basicConfig(
        filename=LOG_PATH,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def _safe_input(prompt: str, default: str = "") -> str:
    try:
        return input(prompt).strip()
    except EOFError:
        return default


def _manual_profile() -> dict:
    print("AI-assisted parsing is unavailable — please enter your preferences manually.")
    genre = _safe_input("Favorite genre: ", "pop").lower()
    mood = _safe_input("Favorite mood: ", "happy").lower()
    try:
        energy = float(_safe_input("Target energy (0.0-1.0): ", "0.5"))
    except ValueError:
        energy = 0.5
    likes_acoustic = _safe_input("Do you like acoustic sound? (y/n): ", "n").lower().startswith("y")
    return {"genre": genre, "mood": mood, "energy": energy, "likes_acoustic": likes_acoustic}


def _print_results(profile, warnings, results, summary=None) -> None:
    profile_summary = ", ".join(f"{key}={value}" for key, value in profile.items())
    print(f"\nUser profile: {profile_summary}")

    if warnings:
        print("\nHeads up:")
        for warning in warnings:
            print(f" - {warning}")

    if summary:
        print(f"\n{summary}")

    print("\nTop Recommendations")
    print("=" * 40)
    for rank, (song, score, explanation) in enumerate(results, start=1):
        print(f"{rank}. {song['title']}  (Score: {score:.2f})")
        print(f"   Because: {explanation}")
        print()


def main() -> None:
    _setup_logging()
    logger = logging.getLogger(__name__)

    songs = load_songs("data/songs.csv")
    print(f"Loaded songs: {len(songs)}")

    text = _safe_input("\nDescribe what you want to listen to: ", DEFAULT_REQUEST) or DEFAULT_REQUEST

    client = None
    try:
        client = get_client()
        profile = parse_profile_from_text(client, text)
    except AgentUnavailableError as e:
        logger.error("AI parsing unavailable: %s", e)
        print(f"\n[AI unavailable: {e}]")
        client = None
        profile = _manual_profile()

    for round_number in range(MAX_CLARIFY_ROUNDS):
        warnings = check_catalog_guardrails(profile, songs)
        results = recommend_songs(profile, songs, k=5)
        logger.info(
            "Round %d results: %s", round_number + 1, [(song["title"], round(score, 2)) for song, score, _ in results]
        )

        review = None
        if client is not None:
            try:
                review = review_and_summarize(client, profile, warnings, results)
            except AgentUnavailableError as e:
                logger.error("AI review unavailable: %s", e)
                print(f"\n[AI summary unavailable: {e}]")

        _print_results(profile, warnings, results, review["summary"] if review else None)

        if review is None or review["status"] == "satisfied" or not review.get("clarifying_question"):
            break
        if round_number == MAX_CLARIFY_ROUNDS - 1:
            break

        answer = _safe_input(f"\n{review['clarifying_question']}\n> ")
        if not answer:
            break
        try:
            profile = refine_profile(client, profile, review["clarifying_question"], answer)
        except AgentUnavailableError as e:
            logger.error("AI refine unavailable: %s", e)
            print(f"\n[Could not refine profile: {e}]")
            break


if __name__ == "__main__":
    main()

import csv
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass

@dataclass
class Song:
    """
    Represents a song and its attributes.
    Required by tests/test_recommender.py
    """
    id: int
    title: str
    artist: str
    genre: str
    mood: str
    energy: float
    tempo_bpm: float
    valence: float
    danceability: float
    acousticness: float

@dataclass
class UserProfile:
    """
    Represents a user's taste preferences.
    Required by tests/test_recommender.py
    """
    favorite_genre: str
    favorite_mood: str
    target_energy: float
    likes_acoustic: bool

class Recommender:
    """
    OOP implementation of the recommendation logic.
    Required by tests/test_recommender.py
    """
    def __init__(self, songs: List[Song]):
        self.songs = songs

    def recommend(self, user: UserProfile, k: int = 5) -> List[Song]:
        # TODO: Implement recommendation logic
        return self.songs[:k]

    def explain_recommendation(self, user: UserProfile, song: Song) -> str:
        # TODO: Implement explanation logic
        return "Explanation placeholder"

def load_songs(csv_path: str) -> List[Dict]:
    """Load songs from a CSV file into a list of dicts."""
    songs = []
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        for line_number, row in enumerate(reader, start=2):
            try:
                songs.append(
                    {
                        "id": int(row["id"]),
                        "title": row["title"],
                        "artist": row["artist"],
                        "genre": row["genre"],
                        "mood": row["mood"],
                        "energy": float(row["energy"]),
                        "tempo_bpm": float(row["tempo_bpm"]),
                        "valence": float(row["valence"]),
                        "danceability": float(row["danceability"]),
                        "acousticness": float(row["acousticness"]),
                    }
                )
            except (KeyError, ValueError) as e:
                raise ValueError(f"Invalid song data on row {line_number} of {csv_path}: {e}") from e
    return songs

def score_song(user_prefs: Dict, song: Dict) -> Tuple[float, List[str]]:
    """Score a song against user preferences, returning (score, reasons)."""
    weights = {"genre": 0.35, "energy": 0.30, "mood": 0.25, "acousticness": 0.10}
    reasons = []

    genre_score = 1.0 if song["genre"] == user_prefs.get("genre") else 0.0
    if genre_score:
        reasons.append(f"matches your favorite genre ({song['genre']})")

    mood_score = 1.0 if song["mood"] == user_prefs.get("mood") else 0.0
    if mood_score:
        reasons.append(f"matches your favorite mood ({song['mood']})")

    target_energy = user_prefs.get("energy")
    energy_score = 0.0 if target_energy is None else 1 - abs(song["energy"] - target_energy)
    if energy_score >= 0.8:
        reasons.append(f"close to your target energy ({song['energy']:.2f})")

    likes_acoustic = user_prefs.get("likes_acoustic")
    song_is_acoustic = song["acousticness"] > 0.5
    acousticness_score = 0.0 if likes_acoustic is None else float(song_is_acoustic == likes_acoustic)
    if acousticness_score:
        reasons.append("matches your acoustic preference")

    score = (
        weights["genre"] * genre_score
        + weights["mood"] * mood_score
        + weights["energy"] * energy_score
        + weights["acousticness"] * acousticness_score
    )

    return score, reasons

def recommend_songs(user_prefs: Dict, songs: List[Dict], k: int = 5) -> List[Tuple[Dict, float, str]]:
    """Score every song against user preferences and return the top k, sorted by score."""
    scored = [(song, *score_song(user_prefs, song)) for song in songs]
    top_k = sorted(scored, key=lambda item: item[1], reverse=True)[:k]
    return [(song, score, ", ".join(reasons) or "no strong matches") for song, score, reasons in top_k]

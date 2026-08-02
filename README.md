# 🎵 Music Recommender Simulation

## Project Summary

This project is a simple content-based music recommender. Each song in the catalog (`data/songs.csv`) is described by a set of audio and tag features — genre, mood, energy, tempo, valence, danceability, and acousticness. A `UserProfile` captures a listener's taste as a favorite genre, favorite mood, target energy level, and a preference for acoustic sound. The `Recommender` scores every song by comparing it to the user's profile, then returns the top-k highest-scoring songs along with an explanation of why each one was picked.

This matters because the same weighted-sum-of-features approach powers a lot of real recommenders, and building one by hand makes its blind spots visible instead of hidden behind a black box. On top of the deterministic scorer, the project also adds an agentic layer (`src/agent.py`) that turns a free-text request into a taste profile, checks it against the catalog for contradictions, and reviews the results before showing them — see Architecture Overview below.

---

## Architecture Overview

The system has two layers that share the same catalog and scoring code:

1. **Deterministic scorer** (`src/recommender.py`) — `Song`, `UserProfile`, and `Recommender` turn a structured profile into ranked, explainable results. See How The System Works and the Data Flow diagram below for the full breakdown.
2. **Agentic layer** (`src/agent.py`, powered by Groq's `llama-3.3-70b-versatile`) — lets the user describe what they want in plain English instead of filling out a `UserProfile` by hand, and reviews the scored results before showing them:

```
free-text request
      │  parse_profile_from_text() — Groq, JSON-mode structured output
      ▼
 {genre, mood, energy, likes_acoustic}
      │
      │  check_catalog_guardrails() — plain Python, no LLM
      ▼
 warnings (missing genre/mood in catalog, energy out of range,
           "likes acoustic" vs. a genre that's never acoustic in this catalog)
      │
      ▼
 recommend_songs()  (the same deterministic scorer described below)
      │
      ▼
 review_and_summarize() — Groq reviews the warnings + top results and
 decides: "satisfied" (write a summary) or "needs_clarification" (ask one
 targeted follow-up question)
      │
      ├── satisfied ──────────────────────────────► show results + summary
      │
      └── needs_clarification ── ask question ──► refine_profile() (Groq
                                                    merges your answer in)
                                                    └─► loop back to
                                                        check_catalog_guardrails()
                                                        (max 2 rounds)
```

If `GROQ_API_KEY` isn't set, or any Groq call fails, the app logs it to `logs/session.log` and falls back to manual `input()` prompts for genre/mood/energy/acoustic preference — you still get scored recommendations, just without the AI parsing/summary/clarification steps.

---

## How The System Works

- The values that will be used from the Song data include genre, mood, energy, and acousticness as primary signals, with valence held as a tie-breaker.
- The information that UserProfile stores includes favorite_genre, favorite_mood, target_energy, and likes_acoustics.
- The Recommender will calculate a score for each song by first comparing song to the UserProfile in four different categories (genre, mood, energy, and acousticness). Each category will be assigned a weight and the final score will be the sum of the four categories.
- The song recommended song will be determined by first scoring every song in the catalog against the UserProfile. The songs are then sorted descending by score and the top k songs are returned.

### Data Flow

```
data/songs.csv
      │  load_songs()
      ▼
 List[Song]                   UserProfile
      │                            │
      └───────────────┬────────────┘
                       ▼
          Recommender.recommend(user, k)
                       │
                       │  for each Song:
                       ▼
              score_song(user, song)
                       │
                       ▼
        (score, [reasons]) per song ── weighted sum of:
                                        genre match, mood match,
                                        energy closeness, acousticness match
                       │
                       ▼
        sort all songs by score, descending
                       │
                       ▼
              take top k songs
                       │
                       ▼
     explain_recommendation(user, song) per result
                       │
                       ▼
     Output: top-k [(Song, score, explanation), ...]
```

## Algorithm Recipe

Components: 
- Genre match: Score of 1.0 if genres match and 0.0 otherwise.
- Mood match: Score of 1.0 if moods match and 0.0 otherwise.
- Energy closeness: Compute 1 - abs(song.energy - user.target_energy), so a song exactly at the user's target energy scores 1.0
- Acousticness match: Convert acoutsticness to a boolean based on value and compare to user's likes_acoutsticness

Combination: Multiply each component by its weight and sum to final score between 0 and 1.
- Weights: genre 0.35, energy 0.30, mood 0.25, acousticness 0.10

Selection: Rank all songs by score descending and return the top k results.

Possible biases:
- Genre Matching: Genres like "indie pop" and "pop" are treated as completely unrelated even though they are adjacent.
- Mood Matching: The mood data entry can be subjective as some users could interpret songs as having different moods than they are listed as.

---

## Getting Started

### Setup

1. Create a virtual environment (optional but recommended):

   ```bash
   python -m venv .venv
   source .venv/bin/activate      # Mac or Linux
   .venv\Scripts\activate         # Windows

2. Install dependencies

```bash
pip install -r requirements.txt
```

3. Set your Groq API key (required for AI-assisted mode; the app still runs without it, falling back to manual prompts). Get a free key from [console.groq.com/keys](https://console.groq.com/keys), then copy `.env.example` to `.env` and paste it in:

```bash
cp .env.example .env
# then open .env and set GROQ_API_KEY=your-key-here
```

`.env` is listed in `.gitignore`, so it's never committed — the app loads it automatically on startup.

4. Run the app:

```bash
python -m src.main
```

### Running Tests

Run the starter tests with:

```bash
pytest
```

You can add more tests in `tests/test_recommender.py`.

---

## Sample Interactions

These are real transcripts from `python -m src.main` with `GROQ_API_KEY` set, run against the current 75-song catalog.

**Example 1 — a straightforward request, satisfied on the first pass:**

```
Describe what you want to listen to: something chill for late night studying, not too fast

User profile: genre=lofi, mood=chill, energy=0.2, likes_acoustic=True

We found some great lofi tracks that match your chill mood and acoustic preferences, like 'Library Rain', 'Midnight Coding', and 'Rainy Window Seat'.

Top Recommendations
========================================
1. Library Rain  (Score: 0.95)
   Because: matches your favorite genre (lofi), matches your favorite mood (chill), close to your target energy (0.35), matches your acoustic preference

2. Midnight Coding  (Score: 0.93)
   Because: matches your favorite genre (lofi), matches your favorite mood (chill), matches your acoustic preference
```

**Example 2 — a genre the catalog doesn't have, triggering a guardrail warning and a clarifying question, then a refined result:**

```
Describe what you want to listen to: vaporwave, dreamy, high energy, no acoustic instruments

User profile: genre=vaporwave, mood=dreamy, energy=0.9, likes_acoustic=False

Heads up:
 - No songs in the catalog are tagged genre='vaporwave' — genre matching will score 0 for every song.

We found some songs that match your dreamy mood, like 'Neon Cloud Nine' and 'Bloom Fantasy', but none of them are vaporwave. Since our catalog lacks vaporwave songs, we're having trouble finding perfect matches.

Would you be open to exploring other genres that often have a dreamy quality, or is vaporwave a must for you?
> sure, try synthwave or k-pop instead

User profile: genre=synthwave, mood=dreamy, energy=0.9, likes_acoustic=False

We found some great synthwave tracks that match your dreamy mood and high energy preferences, such as 'Retrofuture Drive' and 'Night Drive Loop'.

Top Recommendations
========================================
1. Retrofuture Drive  (Score: 0.72)
   Because: matches your favorite genre (synthwave), close to your target energy (0.80), matches your acoustic preference

2. Night Drive Loop  (Score: 0.70)
   Because: matches your favorite genre (synthwave), close to your target energy (0.75), matches your acoustic preference
```

---

## Experiments You Tried

Three tests of the agentic mode against the current 75-song catalog, each run through `python -m src.main`. All three needed a follow-up question, for three different reasons — a genuine contradiction, a mood gap, and a near-miss genre guess.

Experiment 1: Contradictory acoustic preference
```
Describe what you want to listen to: I want angry metal music, but purely acoustic instruments only

User profile: genre=metal, mood=angry, energy=1.0, likes_acoustic=True

Heads up:
 - You asked for acoustic sound, but 'metal' songs in the catalog average 0.03 acousticness — these two preferences are in tension.

We found metal songs like 'Iron Vein' and 'Hollow Crown' that match your angry mood and energy, but they might not be acoustic enough for your taste. On the other hand, 'Storm Movement No.3' is more acoustic but doesn't fit your metal genre. Can you prioritize: would you like more acoustic tracks or stick to metal even if they're not very acoustic?

Top Recommendations
========================================
1. Iron Vein  (Score: 0.89)
   Because: matches your favorite genre (metal), matches your favorite mood (angry), close to your target energy (0.97)

2. Hollow Crown  (Score: 0.89)
   Because: matches your favorite genre (metal), matches your favorite mood (angry), close to your target energy (0.95)

3. Blackout Requiem  (Score: 0.63)
   Because: matches your favorite genre (metal), close to your target energy (0.92)

4. Static Riot  (Score: 0.53)
   Because: matches your favorite mood (angry), close to your target energy (0.93)

5. Storm Movement No.3  (Score: 0.33)
   Because: matches your acoustic preference

Would you like to prioritize acoustic sound or metal genre in your recommendations?
```

Experiment 2: Sparse catalog genre
```
Describe what you want to listen to: upbeat afrobeat vibes for a summer party

User profile: genre=afrobeat, mood=upbeat, energy=0.9, likes_acoustic=False

Heads up:
 - No songs in the catalog are tagged mood='upbeat' — mood matching will score 0 for every song.

It looks like we couldn't find any upbeat afrobeat songs in our catalog, but we did find some songs like 'Sunlit Rhythm' and 'Broken Sirens' that match your genre or energy preferences. However, none of these songs exactly fit what you're looking for.

Top Recommendations
========================================
1. Sunlit Rhythm  (Score: 0.68)
   Because: matches your favorite genre (afrobeat), matches your acoustic preference

2. Broken Sirens  (Score: 0.40)
   Because: close to your target energy (0.90), matches your acoustic preference

3. Breakneck Transit  (Score: 0.40)
   Because: close to your target energy (0.90), matches your acoustic preference

4. Storm Runner  (Score: 0.40)
   Because: close to your target energy (0.91), matches your acoustic preference

5. Blackout Requiem  (Score: 0.39)
   Because: close to your target energy (0.92), matches your acoustic preference

Would you like to relax your mood preference to find more songs that match your favorite afrobeat genre and high energy level?
```

Experiment 3: Vague, minimal-info request
```
Describe what you want to listen to: just play something good

User profile: genre=indie, mood=chill, energy=0.6, likes_acoustic=True

Heads up:
 - No songs in the catalog are tagged genre='indie' — genre matching will score 0 for every song.

We found some chill and acoustic tracks like 'Midnight Coding', 'Library Rain', and 'Spacewalk Thoughts' that you might enjoy, but our catalog doesn't have any songs labeled as 'indie'. Would you like to explore other genres with a similar vibe?

Top Recommendations
========================================
1. Midnight Coding  (Score: 0.60)
   Because: matches your favorite mood (chill), close to your target energy (0.42), matches your acoustic preference

2. Library Rain  (Score: 0.57)
   Because: matches your favorite mood (chill), matches your acoustic preference

3. Spacewalk Thoughts  (Score: 0.55)
   Because: matches your favorite mood (chill), matches your acoustic preference

4. Sunday Morning Grace  (Score: 0.39)
   Because: close to your target energy (0.62), matches your acoustic preference

5. Backyard Fireflies  (Score: 0.39)
   Because: close to your target energy (0.55), matches your acoustic preference

Are you open to listening to music from other genres that match your preferred mood and energy?
```

Worth noting on Experiment 3: given almost nothing to go on, the parser guessed `genre=indie` — close to, but not the same as, the catalog's actual `indie pop` tag. That guess still routes into the same guardrail instead of silently scoring zero, which is the exact failure mode described in Limitations and Risks below.

**Screenshot or video** *(optional)*: <!-- Insert a screenshot or demo video link here -->

---

## Design Decisions

- **Weighted-sum scoring over a black-box model**: a simple linear combination (genre 0.35, energy 0.30, mood 0.25, acousticness 0.10) keeps every recommendation explainable in plain language — the trade-off is that it can't learn nuance like genre adjacency or a user's actual listening history.
- **Deterministic guardrails instead of asking the LLM to catch catalog gaps**: `check_catalog_guardrails()` is plain Python, so it's instant, free, unit-testable with no network call, and always catches the same class of problem (missing genre/mood, out-of-range energy, acoustic-vs-genre tension). The LLM is reserved for where natural language is actually needed — parsing free text, writing the summary, deciding whether to ask a follow-up.
- **Groq's JSON mode over strict schema enforcement**: Groq's `json_schema` structured-output mode isn't guaranteed on every hosted model, so the pipeline uses the more broadly-supported `json_object` mode (valid JSON, not a guaranteed shape) and validates the required fields and types itself. The trade-off is a bit of hand-rolled validation in exchange for not being locked to one specific model.
- **A bounded 2-round clarify loop**: the agent can ask at most one follow-up question before it has to present something, so a CLI user is never stuck in an endless back-and-forth if the model keeps finding new things to ask about.
- **Fail open, not closed**: if `GROQ_API_KEY` is missing or a Groq call errors, the app logs it and falls back to manual `input()` prompts instead of crashing — you always get scored recommendations, with or without the AI layer working.

---

## Limitations and Risks

The model only looks at tags and numbers. It doesn't know about lyrics, popularity, or past listening habits. Genres with just one song (like k-pop or classical) always get weak matches since there's nothing else to pick from. Genre and mood have to match exactly, so a typo or an unlisted genre gets zero credit, and similar genres like "pop" and "indie pop" count as totally unrelated. If a user's preferences contradict each other, the model just silently drops that part of the score instead of flagging it. Missing profile fields also score as zero, so an incomplete profile can't reach a high score even with a perfect partial match.

---

## Reflection

Read and complete `model_card.md`:

[**Model Card**](model_card.md)

Building this showed me that a recommender is really just a math formula because every "recommendation" is a weighted sum of a few number categories and string comparisons. There's no real understanding of music happening because the system doesn't know what a song sounds like, it just knows whether labels or numbers match. Turning data into a prediction is really turning a handful of features into a single score and sorting, which is a lot simpler than it feels from the outside as a listener.

The experiments also made it clear how easily bias creeps in from decisions that seem small. Whoever picks the feature weights decides what "good taste" means to the system, giving genre the highest weight meant genre mismatches were nearly impossible to overcome. Whoever builds the catalog decides whose taste gets served well, since a genre with one song can never produce a strong recommendation no matter what the user asks for. Because the matching is exact-text rather than exact-meaning, small differences in labeling can zero out a whole category of the score without ever telling the user why.
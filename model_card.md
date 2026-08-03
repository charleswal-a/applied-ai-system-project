# 🎧 Model Card: Music Recommender Simulation

## 1. Model Name  

**TasteMatch 2.0**

---

## 2. Intended Use  

TasteMatch takes a listener's stated taste (favorite genre, favorite mood, target energy, and whether they like acoustic sound) and returns a ranked list of the best-matching songs from a small catalog, along with a plain-language reason for each pick. As of 2.0, that taste doesn't have to arrive as a structured profile — the user can describe what they want in a sentence, and an agentic layer turns it into the same genre/mood/energy/acoustic shape before scoring. It still assumes the user's taste can be reduced to one favorite genre, one favorite mood, and a single energy level; if that description doesn't line up well with the catalog, the system will ask one follow-up question before handing back its final picks.

---

## 3. How the Model Works  

Every song has a genre, a mood, and a few numeric traits: energy, tempo, valence, danceability, and acousticness. The user's profile has a favorite genre, a favorite mood, a target energy level, and a yes/no acoustic preference.

To score a song, the model checks four things and gives credit for each: does the genre match (worth 35% of the score), does the mood match (25%), how close is the song's energy to the target energy (30%, with partial credit the closer it gets), and does the song's acoustic level match what the user said they like (10%). Those four pieces are added up into one final score between 0 and 1, and the songs with the highest scores are recommended.

Starting from the empty starter code, I implemented the CSV loading, wrote the four-part weighted scoring formula above, added logic to rank all songs and keep only the top matches, and cleaned up the terminal output so it shows the user's profile, a numbered list of recommendations, and the specific reasons behind each score.

For 2.0, I added an agentic layer (`src/agent.py`) in front of that same scorer. A Groq-hosted model (`llama-3.3-70b-versatile`) turns a free-text request like "chill music for studying" into the same genre/mood/energy/acoustic profile the scorer already expects, a plain-Python guardrail check compares that profile against what's actually in the catalog before anything is scored, and after scoring, the model reviews the warnings and top results to decide whether to show them as-is or ask one clarifying question first. If the API key is missing or a call fails, the app falls back to asking for genre/mood/energy/acoustic directly — the deterministic scorer itself never changed, and it never depends on the AI layer being available.

---

## 4. Data  

The catalog has grown to 75 songs across 28 genres and 27 moods. It started with 10 songs across 7 genres (pop, lofi, rock, ambient, jazz, synthwave, indie pop) and 6 moods, then grew to 20 songs covering 17 genres, and most recently grew again to fill most existing genres out to 3-4 songs each and add new ones — soul, funk, gospel, punk, disco, house, techno, drum and bass, singer-songwriter, latin, and afrobeat.

Even at 75 songs, the dataset is missing a lot of what actually shapes musical taste: no lyrics or language, no artist popularity or era, no actual listening history. One genre (afrobeat) still has just a single song, and ten others (soul, funk, gospel, punk, disco, house, techno, drum and bass, singer-songwriter, latin) have only two, so those genres still can't show much variety within themselves.

---

## 5. Strengths  

The model still gives sensible results for tastes that are well represented in the catalog. A "chill, lofi" request pulls back Library Rain (0.95) and Midnight Coding (0.93) as its top two picks, in the order I'd expect a person to pick by hand, and the energy-closeness scoring keeps behaving the way it should: songs near the target energy score higher and songs far from it score lower, instead of a hard match/no-match cutoff.

The bigger strength in 2.0 is what the agentic layer catches before a result ever gets shown. Asking for "angry metal music, but purely acoustic instruments only" gets flagged immediately — the guardrail notices metal songs in the catalog average 0.03 acousticness, and the model asks the user to prioritize instead of silently zeroing out the acoustic score. Asking for a genre the catalog doesn't have (vaporwave) gets caught the same way, with the model suggesting real alternatives (synthwave, k-pop) instead of returning a confident-looking but wrong top result.

---

## 6. Limitations and Bias 

The scorer itself hasn't changed: it only looks at tags and numbers, has no idea about lyrics, artist popularity, or what the user has actually listened to before, and genre/mood matching is still all-or-nothing text matching — a genre typed slightly differently, or one that isn't in the catalog at all (like "electronic"), gets zero credit for that entire 35% of the score, and closely related genres like "pop" and "indie pop" are still treated as completely unrelated. Genres with only one or two songs in the catalog (afrobeat, and the ten genres added at just two songs each) will still get weak recommendations no matter how good the match is, because there's nothing else to choose from.

What 2.0 changes is what happens with a contradiction before scoring: instead of quietly dropping the acoustic score to zero, the guardrail flags the tension and the model asks the user to prioritize. But it never resolves that tension on its own — it always hands the decision back to the user, so a fully unattended run still stalls on a genuinely contradictory profile. The agentic layer also introduces its own new failure mode: the parser doesn't always land on an exact catalog tag ("just play something good" produced genre=indie instead of the catalog's actual indie pop), and a near-miss like that gets treated exactly the same as a genre that isn't in the catalog at all, rather than being matched to the closest real tag.

---

## 7. Evaluation  

Testing now happens on two tracks. `pytest` covers the deterministic logic automatically — 2 tests on the scorer itself, plus 5 on the guardrail check (missing genre, missing mood, out-of-range energy, an acoustic/genre contradiction, and a clean profile with no warnings) — none of which need a network call or an API key. On top of that, I ran five live sessions through the full agentic pipeline against the current 75-song catalog, recorded as transcripts in the README: a straightforward request, a genre the catalog doesn't have, a genuinely contradictory request, a sparse-genre request, and a vague one-line request with almost no information to go on.

The most interesting result was the vague request ("just play something good") — with almost nothing to go on, the parser guessed genre=indie, which is close to but not the same as the catalog's actual indie pop tag, so a genre that's actually a near-match still got treated as a total miss. That's the same class of problem as the old "electronic" test used to show, just introduced by the parsing step now instead of by the user typing something wrong. I didn't run any numeric metrics — just pytest's pass/fail plus manual review of each transcript.

---

## 8. Future Work  

Next steps would still include letting genre and mood scoring give partial credit for closely related tags instead of exact-match-only, and folding valence in as a real scored feature instead of just an unused tie-breaker. I'd also want the explanations to mention what didn't match, not just what did, so users understand a low score's cause. Adding more variety to the top-k results (instead of several very similar songs) and supporting more than one favorite genre or mood would make the model feel more realistic.

On the agentic side, the clearest next step is matching a near-miss genre guess (like indie) to the closest real catalog tag (indie pop) instead of treating it as a total miss. I'd also want a way to let the model propose a resolution to a simple contradiction when the user doesn't answer the follow-up question, instead of the pipeline having nowhere to go. And since the guardrail already knows exactly which requests the catalog can't satisfy, logging how often each warning type fires would be a cheap way to see which genres and moods actually need more songs next.

---

## 9. Personal Reflection  

During the original project, I learned the importance of the data that you pick from the data set to use in the recommendation algorithm. My biggest learning moment during this project came from testing the music recommender using different user profiles. It showed me weaknesses in the algorithm I picked, and how the weights/features I chose affected the returned songs. AI tools were a big help in giving me feedback on the algorithm, as well as implementing the algorithm in an efficient way. I was surprised that the simple 4 values I chose would give an effective recommendation most of the time. In the future, I would've extended this project by using more features and incorporating way more songs in the dataset.

In the final project, I got to use Claude Code to enhance this project and add the agentic layer that can create a user profile from the user's answer to a single question. I got to collaborate and work with Claude by prompting to generate code, troubleshoot errors, and create tests for the music recommendation model. One example of a helpful suggestion that AI gave was using the universal json_object when getting a result from the GROQ API. This ensured that the outputs are relaibly readable and ready to by parsed by the program. A flawed suggestion that was given by Claude was to build the entire agentic layer using Anthropic's Claude API when I was unable to obtain a free key. I was able to obtain a GROQ API key instead and prompt the system to alter the code to account for this fundamental change.
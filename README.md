# Live Knowledge Check

A live, group quiz app for coworking sessions, similar to Kahoot. One person
hosts, everyone else joins with a 4-letter code on their own device, and
answers sync live with a shared leaderboard.

## How it works

- Streamlit runs as one server process. All connected browser tabs (host and
  every player) share the same in-memory game state, so no external database
  is needed for a small group.
- **This only works if everyone is on the same running app.** If you deploy
  it and it somehow ends up running as more than one instance, players could
  land on different processes that don't share state. Streamlit Community
  Cloud's free tier runs a single instance per app, which is what this is
  built for.
- Game state lives in memory only. If the app restarts or redeploys mid-game,
  the game is lost and everyone needs to rejoin with a new code.

## Editing the questions

Open `data/questions.json` and replace the placeholder questions with your
own, keeping the same structure:

```json
{
  "question": "Your question text",
  "options": ["Option A", "Option B", "Option C", "Option D"],
  "correct_index": 0,
  "duration": 20
}
```

- `correct_index` is zero-based (0 = first option).
- `options` can have 2 to 6 entries.
- `duration` is how many seconds players get to answer, in seconds (optional,
  defaults to 20).

Commit the change and push to GitHub — Streamlit Community Cloud
auto-redeploys on push.

## Running it locally

```bash
pip install -r requirements.txt
streamlit run Home.py
```

Then open the printed local URL in a browser tab for yourself as host, and
have others on the same network open your machine's local network URL
(Streamlit prints one, like `http://192.168.x.x:8501`) to join as players.
Everyone must reach the *same* running app.

## Deploying to Streamlit Community Cloud (recommended for a real session)

1. Push this repo to GitHub (see below).
2. Go to [share.streamlit.io](https://share.streamlit.io) and sign in.
3. Click "New app", pick this repo/branch, and set the main file path to
   `Home.py`.
4. Deploy. You'll get one public URL — that's the link you share with the
   group. The host opens it and goes to the Host page; everyone else opens
   the same link and goes to the Player page.

## Pushing this project to GitHub

```bash
cd zevo-live-quiz
git init
git add .
git commit -m "Initial live knowledge check app"
git branch -M main
git remote add origin <your-empty-github-repo-url>
git push -u origin main
```

## Running a session

1. Host opens the app, goes to **Host**, clicks "Create new game", and shares
   the 4-letter code on screen (or just says it out loud).
2. Everyone else opens the same app link, goes to **Play**, and enters their
   name and the code.
3. Host clicks "Start game" once everyone's joined.
4. Each question: players pick an answer against the clock (faster correct
   answers score more, 500-1000 points). The host's screen shows how many
   have answered and reveals the correct answer and leaderboard between
   questions.
5. After the last question, both host and players see the final leaderboard.

## Known limitations

- No persistence across app restarts — this is meant for one live session,
  not long-term score tracking.
- No protection against someone joining twice with different names, or a
  player refreshing mid-game and losing their local session (their score is
  still tracked server-side under their name, they'd just need to rejoin
  with the exact same name to see the "already answered" waiting states
  render correctly next time).
- Built for a small group (well under a hundred concurrent players). It
  hasn't been load-tested beyond that.

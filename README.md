# Mighty Command Center

A mobile-first CEO dashboard built for loss aversion — showing the **cost of inaction** rather than just a task list.

## Architecture
- `generate-data.py` — Reads workspace files and generates `public/data.json`
- `public/index.html` — Single-file static app (vanilla HTML/CSS/JS, no frameworks)
- Deployed via Vercel

## Sections
1. **Q1 Countdown** — Animated progress ring with days remaining
2. **Cost of Inaction** — Stalled deals, cooling relationships, at-risk goals with $ values
3. **Pipeline Pulse** — Horizontal scrolling kanban view
4. **Goal Tracker** — Animated progress bars with key results
5. **Relationship Radar** — Interactive concentric circle visualization
6. **Open Loops** — Tabbed follow-up tracker
7. **Key Dates** — Color-coded timeline

## Local Development
```bash
python3 generate-data.py
open public/index.html
```

## Deploy
Connected to Vercel — auto-deploys on push. Run `python3 generate-data.py` before pushing to update data.

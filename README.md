# Prepdrill

> Codecademy-style interactive practice for Indian govt-exam aptitude — timed drills, instant AI explanations, weakness-targeted daily sets.

**Alternative to the product-shape pioneered by Codecademy (YC S11)** — rank #19 of 500 in the [YC-500 Fable 5 Venture Blueprint](https://github.com/) (score 7.05/10).

## Why this exists
Practice-first learning with instant feedback beat passive video courses. The buildable wedge: interactive practice engine with ai feedback for any skill domain.

## MVP scope
- [ ] Question bank importer
- [ ] timed drill player
- [ ] AI explanations on wrong answers
- [ ] weakness heatmap
- [ ] daily streaks

## Architecture
`Workers+Supabase+Claude` — Cloudflare Workers + Hono API, Supabase (Postgres + RLS + Auth + pgvector), Claude API via Agent SDK (claude-fable-5 for agent reasoning, claude-haiku-4-5 for volume), wrangler deploys.

**Integrations:** Claude API; Razorpay; WhatsApp Cloud API
**Data:** Authored/licensed question banks per exam.
**Agent core:** Agent generates fresh practice variants and personalized explanations from syllabus.

## Business
| | |
|---|---|
| Monetization | INR 299-999/mo learner subscription |
| First customer | UGC NET / SSC aspirants in India |
| GTM wedge | Telegram/YouTube exam-prep communities; free daily drill funnel |
| Competition risk | High: Testbook, Adda247 dominate |
| Regulatory/trust risk | Low: consumer education content |
| India angle | Core market is India; vernacular explanations via Claude. |
| Difficulty / build time | Medium / 2-3 weeks |

## 30-day plan
- **W1:** core loop — Question bank importer + timed drill player
- **W2:** AI explanations on wrong answers + weakness heatmap + daily streaks + auth + billing
- **W3:** polish, instrument events, seed first users via: Telegram/YouTube exam-prep communities; free daily drill funnel
- **W4:** launch + first revenue; kill/scale decision

---
*Built with Fable 5 (Claude Code). Blueprint row: inspired by Codecademy — "Interactive browser-based coding courses with instant feedback."*
---
name: budget
description: How to use the budget tool and phrase the result
targets: [main]
---

## Budget

- `calculate_budget` is the only source of money maths. Never add up costs in
  your head.
- Put every cost mentioned in the plan into the tool: food, entry, transport,
  activities. Use `per_person=true` for per-head prices.
- Call it last. It must be the final tool call in a planning turn.
- Copy the tool's `display` string exactly into the reply.
- If the plan is slightly over budget (up to about 10%), say so once and keep
  the plan. Do not loop, rewrite everything, or shave a few rupees.
- If it is clearly over budget, name the biggest cost and offer one simple
  cheaper swap. Do not run a revision loop.

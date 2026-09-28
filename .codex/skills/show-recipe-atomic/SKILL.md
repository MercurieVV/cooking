---
name: show-recipe-atomic
description: Use when the user asks for a recipe/recepee with atomic steps — one action per step, nothing bundled — or says a show-recipe output's steps are too bundled/coarse and need splitting into the smallest independently-doable actions.
---

# Show Recipe (Atomic Steps)

**REQUIRED BASE SKILL:** show-recipe. Everything there applies unchanged — output
contract (Assumptions / Required / Steps), VR SPA, photo sourcing and caching,
entity rules, workflow, renderer, quality bar. This skill only replaces the
step-granularity rule: **every step is atomic.**

Use the same scripts and schema: `.codex/skills/show-recipe/scripts/render_recipe_card.py`,
`.codex/skills/show-recipe/references/recipe-card-schema.md`.

## What "atomic" means

A step is atomic when it has **exactly one `done` cue reached by one continuous
action**, at one tool, one setting, touching **at most 2 ingredients**. Split
a step when its `do` text spans a point where the cook could stop, put the
spoon down, and the pause would be invisible to the dish — a tool change, a
setting change, a different ingredient going in, or a 3rd ingredient joining
what's already there.

Don't split a single motion just because its description uses "and" — `peel
and core` with the same knife, no stopping point between them, is one step.

**Test per step:** read `do`. If it names two or more of: different tools,
different settings/programs, ingredients added at genuinely separate moments,
or more than 2 ingredients total — split. If it's one motion described in two
clauses touching ≤2 ingredients, keep it.

**Every `do` must carry its numbers.** State amount for each ingredient named
(`100 g sugar`, not `sugar`) and any action parameter that applies (duration,
temperature, speed/setting, count) — `"Bake at 180°C for 20 minutes"`, not
`"Bake until done"`. Pull the values from the step's `ingredients` list and
from the base recipe's timings/temperatures; never leave a bare noun where a
number is known.

## Splitting worked example

Bundled (from a non-atomic show-recipe run of apple slab pie):

> **Step 1 — Prep trays and butter**
> `do`: "Line both trays. Cube butter. Weigh flour, sugar, baking powder, salt."

Three tools, three stopping points, and the dry-mix clause alone names 4
ingredients (over the 2-ingredient cap). Split into five atomic steps:

> **Step 1 — Line trays**
> `tool`: Worktop · `do`: "Line both oven trays with baking paper." · `done`: "Both trays lined."
>
> **Step 2 — Cube cold butter**
> `tool`: Worktop · `do`: "Cut 450 g cold butter into 1-2 cm cubes." · `done`: "Butter cubed, still cold."
>
> **Step 3 — Weigh flour and sugar**
> `tool`: Kenwood mixer bowl (integrated scale) · `do`: "Weigh 900 g plain flour and 200 g sugar into the bowl." · `done`: "Flour and sugar weighed."
>
> **Step 4 — Add baking powder**
> `tool`: Kenwood mixer bowl (integrated scale) · `do`: "Weigh 10 g baking powder into the bowl." · `done`: "Baking powder added."
>
> **Step 5 — Add salt**
> `tool`: Kenwood mixer bowl (integrated scale) · `do`: "Weigh 5 g salt into the bowl." · `done`: "Salt added, dry mix complete."

Same treatment for any step whose `do` reads as a list: "Roll bases in.
Crumbs, apples, lid, vents, egg wash, coarse sugar." is six stopping points →
six steps (roll base / scatter breadcrumbs / fill apples / place lid / cut
vents / egg wash + sugar), each carrying its own amount.

## Consequences for the rest of the spec

- **Renumber `n`** sequentially after splitting — no gaps, no reused numbers.
- **Title still covers the `do` text** (show-recipe's rule) — atomic steps make
  this easy since each step now does one thing: `Line trays`, not `Prep trays
  and butter`.
- **`ingredients` per step still must match `do`, and holds at most 2 entries**
  — a split step lists only the ≤2 ingredients it actually touches, each with
  its `amount` (cubing butter lists only butter, 450 g).
- **Timeline lanes stay coarse** — `required.timeline` tasks may still group
  several atomic steps under one lane task (e.g. "Line trays, cube butter,
  weigh dry mix" as one 10-min block) since the timeline is a schedule
  overview, not the step list. Only the `steps` array must be atomic.
- More steps than a show-recipe run of the same dish is expected and correct
  — it is the point of this skill, not a sign of over-splitting.

## Quality bar (adds to show-recipe's)

- [ ] Every step's `do` describes one action, one tool, one setting, one `done` cue, ≤2 ingredients.
- [ ] No step's `do` text lists two or more items separated by a full stop that could each stand alone as a step.
- [ ] No step's `ingredients` array has more than 2 entries.
- [ ] Every ingredient named in `do` carries its amount; every action parameter (time, temp, setting, count) is stated, not implied.
- [ ] No step was split at a point that isn't a real stopping point (same motion, same tool, no pause) — don't fragment `peel and core` or `season and stir` into two steps.
- [ ] `n` is sequential with no gaps after splitting.
- [ ] Step titles were re-checked after splitting — a title written for the old bundled step must not survive onto a narrower one.

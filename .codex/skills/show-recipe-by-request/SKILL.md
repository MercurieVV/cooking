---
name: show-recipe-by-request
description: Generate a requested recipe as a PDF, adapting the method to the user's owned kitchen appliances, programs, settings, accessories, photos, timings, and optional multi-cook parallel work plans with synchronization points. Use when the user asks to show, prepare, plan, or generate a recipe/recepee/meal/cooking procedure and wants appliance-specific instructions or PDF output.
---

# Show Recipe By Request

## Overview

Create a polished PDF recipe from a user request. The output must be a usable cooking plan, not just a generic recipe: map steps to the user's available appliances, include program names/numbers/IDs when known, specify settings/accessories/timings, include relevant appliance pictures, and parallelize work across multiple cooks when the user asks for several people.

## Required Context

1. Read the local project knowledge base before writing the recipe:
   - Prefer `wiki/kitchen-tools/kitchen-appliance-inventory.md`.
   - Also search `raw/kitchen-tools/` for model-specific details, programs, photos, and user statements.
2. If the project has no appliance wiki, ask for the appliance list or proceed with clearly marked assumptions.
3. For external recipe facts, browse or use user-provided sources when the user asks for a named/current recipe or when precise appliance program data is not already in the wiki.
4. Use only confirmed appliance programs/settings as exact claims. If a program number or model-specific setting is unknown, write a practical setting with a note such as `Program: not confirmed; use Manual 180 C for 12 min`.

## Workflow

1. Clarify only blocking constraints: servings, dietary restrictions, target cuisine, exact dish, deadline, and number/skill level of cooks. If missing, choose reasonable defaults and state them in the PDF.
2. Build a recipe plan:
   - Ingredients with metric units and optional shopping notes.
   - Mise en place.
   - Appliance assignment for each step.
   - Active time, passive time, total time, servings, and difficulty.
3. Apply appliances:
   - Prefer owned appliances when they improve quality, reliability, or parallelism.
   - Include accessory names, e.g. Kenwood pasta press, meat grinder attachment, ThermoResist bowl, TempPro probes.
   - Treat inventory-listed appliances/accessories as available. Do not write vague phrases like `if available` for tools confirmed in `wiki/` or `raw/`.
   - Include program names/numbers/IDs, temperature, pressure level, speed, duration, preheat, probe targets, release method, and rest time when relevant.
   - Include an alternative when an owned appliance's exact model or program is unconfirmed.
4. If multiple cooks are requested, split the work by cook skill and station. Create sync points where dependent work joins, with exact readiness criteria.
5. Generate a PDF as the final artifact. Also provide a short final message with the PDF path and any assumptions.

## PDF Requirements

Use `scripts/render_recipe_pdf.py` when possible. Provide it a JSON spec matching `references/recipe-schema.md`; it generates a Markdown sidecar and renders the PDF with `pandoc --pdf-engine=weasyprint` so appliance photos render from local paths. If Pandoc or WeasyPrint is unavailable, it still emits a valid text PDF and includes local image paths.

Write recipe text maximally structured, short, and clear. Include only what is needed to cook the dish safely and reliably. Formatting must carry the structure: concise headings, aligned tables, restrained colors, clear parent/child text blocks, and the most readable practical font stack. Avoid long prose, decorative sections, or repeated explanations.

The PDF should include:

- Title and short description.
- Assumptions and serving count.
- Appliance plan with pictures where local images exist.
- Ingredients.
- Timeline displayed as a horizontal classic timeline diagram, not a plain table and not raw HTML.
- Vector sketches/diagrams when a structure, layering, tray layout, cut pattern, assembly order, or timing relationship is clearer visually than in words.
- Step-by-step method where every step shows: needed tools/ingredients, appliance photo when relevant, settings/accessory, timing, action, and readiness cue.
- Sync points for multi-cook recipes.
- Food-safety notes where relevant.

## Quality Rules

- Keep both Markdown and PDF compact: prefer tables, short bullets, and single-purpose step paragraphs.
- Use visual styling to clarify hierarchy, timing, appliance/settings, and sync points; do not use color as decoration.
- Use the timeline field as a horizontal swimlane diagram. Separate people work and appliance work into rows, using `lane` and `lane_type` when needed. Keep each block short: time range, actor/appliance, task. In generated Markdown/PDF, embed the timeline as an SVG/image so the user never sees HTML code.
- Generate simple local SVG files for visual explanations when words would be clumsy. Use vector sketches for cross-sections, appliance loading, tray positioning, layering, piping shapes, cuts, and multi-cook dependency maps.
- Make every generated diagram immediately understandable: include a clear title, direct labels/arrows, and the exact cooking decision it supports. If the diagram's purpose is not obvious, simplify it or omit it.
- Use the best available local photo for each appliance/tool used. If a separate accessory photo does not exist, use the parent appliance photo and name the exact accessory in the step.
- Make step blocks visually scannable: parent line is the step title; child lines are `Need`, `Tool`, `Set`, `Do`, `Done`.
- Do not invent exact model numbers, program IDs, temperatures, or timings from the user's appliance inventory. Mark uncertain data plainly.
- Keep the recipe operational: each step should say who does it, where, with what tool, for how long, and what "done" looks like.
- Prefer metric units. Add Fahrenheit only when helpful.
- Use project-root-relative paths for local images in the JSON spec.
- When using facts from `wiki/`, respect its Raw evidence rules if updating the wiki. This skill normally writes only the PDF, not wiki files.

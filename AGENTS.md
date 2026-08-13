# Repository Guidelines

## Project Structure & Module Organization

This repository is a small Scala CLI project paired with a personal cooking knowledge base.

- `main.scala` contains the current application entry point.
- `project.scala` contains Scala CLI directives, including `//> using scala 3.8.4`.
- `raw/` stores immutable source material for the knowledge base. Do not rewrite source facts; add new source files instead.
- `wiki/` stores compiled knowledge articles, plus `wiki/index.md` and `wiki/log.md`.
- Generated IDE/build state lives in `.bsp/`, `.scala-build/`, and `.idea/`; avoid relying on those files for source behavior.

## Build, Test, and Development Commands

- `rtk scala-cli run .` runs the application from the repository root.
- `rtk scala-cli compile .` compiles all Scala sources.
- `rtk scala-cli test .` runs tests once tests are added.
- `rtk scala-cli fmt .` formats Scala sources using Scala CLI/Scalafmt defaults when configured.

Use the `rtk` prefix for shell commands in this repository.

## Coding Style & Naming Conventions

Use Scala 3 syntax and keep source files focused. Prefer clear, descriptive names in `camelCase` for values/functions and `PascalCase` for types. Use two-space indentation, as in `main.scala`. Add comments only when they explain non-obvious reasoning.

For wiki files, use lowercase kebab-case filenames, for example `wiki/kitchen-tools/kitchen-appliance-inventory.md`.

## Testing Guidelines

There are no tests yet. When adding behavior, add focused Scala tests alongside the source layout you introduce, and name tests after observable behavior rather than implementation details. Run `rtk scala-cli test .` before opening a pull request.

## Commit & Pull Request Guidelines

This repository currently has no committed history, so no existing commit convention can be inferred. Use short, imperative commit subjects such as `Add appliance inventory article` or `Implement recipe parser`.

Pull requests should include a concise description, the commands run for verification, and screenshots only when changing rendered documentation or UI. Link related issues when available.

## Knowledge Base Rules

Treat `raw/` as append-only source evidence and `wiki/` as compiled knowledge. When updating wiki articles, keep `wiki/index.md` current and append the action to `wiki/log.md`. Facts, dates, numbers, and direct quotes in `wiki/` should be traceable to linked files in `raw/`.

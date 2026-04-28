---
project_name: "OoT Live Dungeon"
wiki_root: ".wiki"
article_dir: "articles"
inbox_dir: "_inbox"
archive_dir: "_archive"
default_language: "de"
auto_index: true
auto_crosslink: true
categories:
  - architecture
  - features
  - milestones
---

# Wiki Configuration

This wiki is maintained by Claude Code. Articles are created and updated
through slash commands and grow organically as the LLM works with the codebase.

## Code Roots

- Sidecar: `sidecar/src/livegen/`
- Tests: `sidecar/tests/`
- Docs: `docs/`
- SoH-Fork (ab M4): `soh-fork/soh/src/livegen/`
- Tooling: `tooling/`

## Conventions

- Articles use kebab-case filenames
- Each article documents ONE topic
- Mermaid diagrams are encouraged but not required
- Code locations use relative paths from project root
- Frontmatter is required on every article
- Cross-references are bidirectional (if A links B, B links A)
- Language: German for descriptions, English for code/technical terms

## Article Lifecycle

| Status   | Meaning                                    |
|----------|--------------------------------------------|
| current  | Active and accurate                        |
| draft    | Work in progress                           |
| stale    | Needs review (auto-detected or manual)     |
| archived | Moved to `_archive/`, no longer maintained |

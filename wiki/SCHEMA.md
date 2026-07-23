# Wiki Schema

## Domain
待定义 — 由首次导入的文档自动确定

## Conventions
- File names: lowercase, hyphens, no spaces
- Every wiki page starts with YAML frontmatter
- Use `[[wikilinks]]` to link between pages
- Sources reference original files in vault/
- Folder: entities/ concepts/ comparisons/ queries/

## YAML Frontmatter
```yaml
title: 页面标题
created: 2026-01-01
updated: 2026-01-01
type: entity|concept|comparison|query
tags: [tag1, tag2]
sources:
  - raw/articles/source-file.md
confidence: low|medium|high
```

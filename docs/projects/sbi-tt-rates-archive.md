---
title: SBI TT Rates Archive
description: An automatically updated archive of historical SBI telegraphic transfer (TT) rates since July 2020, with pre-parsed CSVs per currency pair.
template: project.html
category: Data & Automation
repo: https://github.com/anoopgarlapati/sbi-tt-rates-archive
---

SBI TT rates are the reference exchange rates needed for Indian income tax returns, but neither RBI nor SBI publishes a historical archive. This repository keeps one.

# How it works

A scheduled GitHub Action runs twice a day. It downloads the latest SBI TT rates PDF and commits it, then parses the PDF and updates the derived CSVs in a second commit, so the raw source and the structured data never drift apart.

PDFs are stored by year and month, named by retrieval timestamp:

```text
2021/
  01/
    2021-01-01-00:00.pdf
```

Parsed rates live in `rates/`, one CSV per currency pair (`USD-INR.csv`, `EUR-INR.csv`, …) plus a `_metadata.csv` audit trail with one row per processed PDF.

# Scripts

```bash
# Parse all historical PDFs and generate initial CSVs
uv run python scripts/backfill.py

# Parse a single PDF and append to CSVs
uv run python scripts/daily_update.py 2026/06/2026-06-20-14:00.pdf

# Validate CSV integrity
uv run python scripts/validate.py
```

The archive is forked from [skbly7/sbi-tt-rates-historical](https://github.com/skbly7/sbi-tt-rates-historical). Data is collected automatically; no guarantee is made about completeness or correctness.

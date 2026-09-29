---
title: TestNG Report Action
description: A GitHub Action that parses TestNG XML results, writes Markdown test reports to the workflow summary and annotates failed tests in pull requests.
template: project.html
category: Developer Tools
repo: https://github.com/anoopgarlapati/action-testng-report
topics:
  - Developer Tooling
  - Testing & Debugging
---

Java projects that use TestNG produce `testng-results.xml`, but GitHub Actions has no built-in way to surface those results. This action closes that gap so test failures show up where reviewers already look.

# What it does

- Parses TestNG XML result files, including runs with multiple suites.
- Adds workflow annotations for failed tests, with stack traces.
- Writes a summary report and an optional detailed Markdown report to the workflow summary.
- Optionally fails the job when no results are found.

# Usage

```yaml
jobs:
  testng-report:
    runs-on: ubuntu-latest
    steps:
      - name: Generate TestNG Report
        uses: runekit-oss/action-testng-report@v1
        with:
          summary_report: 'true'
          detailed_report: 'true'
          fail_if_empty: 'true'
```

| Input | Description | Default |
| --- | --- | --- |
| `report_paths` | Glob for TestNG XML files | `**/testng-results.xml` |
| `summary_report` | Generate a summary report | `true` |
| `detailed_report` | Generate a detailed report | `false` |
| `fail_if_empty` | Fail if no test results are found | `true` |

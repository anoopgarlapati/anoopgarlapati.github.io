---
title: Why we should ship containers for on-premises software and not the appliances
description: Operating system vendors take roughly a week to a month to ship a patch, while attackers can move in a day. Containers leave the OS and the host to the customer.
date: 2026-11-05
categories:
  - Architecture
tags:
  - Containers
  - Appliances
  - On-Premises
  - CVE
---

In October 2026, nine critical CVEs were reported against AlmaLinux OS. Six of them came from AI security and research labs.

| CVE {: style="width: 10rem" } | Component/Package | Reporter |
| --- | --- | --- |
| CVE-2026-115557 | python | Independent researcher (no evidence of AI usage) |
| CVE-2026-98490 | kernel | Open source review process (no evidence of AI usage) |
| CVE-2026-98548 | kernel | Tencent Corvus (AI security lab) |
| CVE-2026-86414 | curl | Aisle Research (AI security lab) |
| CVE-2026-92388 | curl | Aisle Research (AI security lab) |
| CVE-2026-111497 | brotli | OpenAI Codex Security (AI lab) |
| CVE-2026-98432 | kernel | Anthropic (AI lab) |
| CVE-2026-114406 | eMudhra CA trust store in Java, AlmaLinux, Python, etc | Independent researcher (no evidence of AI usage) |
| CVE-2026-93479 | nginx | Tolmo Inc (AI cybersecurity lab) |

AI tools now find and report flaws faster than before. That changes how we have to ship software that runs on a customer's own hardware.

# The patching gap

Appliances ship with an operating system, such as AlmaLinux. That means we have to track and patch the OS too. Based on recent trends, a high or critical OS CVE shows up roughly once a week.

Some of these CVEs reach the CISA Known Exploited Vulnerability (KEV) list within a day. Some exploits even appear within an hour. AI agents make this faster, because they can turn a CVE description into a working attack.

The OS vendor takes roughly a week or a month to ship a patch. Attackers can move in a day or less. That gap is the real problem in this agentic era.

# Scanners decide what customers see

Many of these CVEs cannot be exploited in our software or in the restricted network setup we recommend. Customers often trust their scanner more than our analysis. A scanner flags the CVE and the customer asks us to fix it.

So we need to show, one CVE at a time, why our product is not affected. Saying so is often not enough as customers still trust their security scanners which flag the CVE.

# Licenses and blind spots

When we ship an appliance, we typically pay for OS licenses too. Without proper telemetry from the on-premises software, we do not know how many machines customers run our appliances. That makes it hard to report the right license count to our vendor.

# Why containers

Products or services nowadays are mostly shipped as containers. Running an OS management business when we do not need to is very painful for the reasons mentioned above.

If we ship containers with an appropriate container runtime platform, the customer runs the OS and the host. We manage our own services and the libraries they use. Patching a container image or a Java/Go library is faster than patching OS packages as observed historically.

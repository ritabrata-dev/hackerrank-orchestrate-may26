# Multi-Domain Support Triage Agent

## Overview

This project implements a terminal-based support triage agent that processes support tickets across three domains:

* HackerRank
* Claude
* Visa

The agent classifies issues, retrieves relevant support documentation, decides whether to respond or escalate, and generates grounded responses.

---

## Key Features

### 1. Corpus-Driven Retrieval

* Uses only the provided support corpus (`data/`)
* Keyword-based scoring system (no external knowledge sources)
* Returns top relevant documents for each query

### 2. Confidence-Aware Reasoning

* Retrieval produces a confidence score
* Response strategy:

  * **High confidence** → direct solution
  * **Medium confidence** → cautious guidance
  * **Low confidence** → fallback asking for details

### 3. Intelligent Classification

* Detects:

  * company (HackerRank / Claude / Visa)
  * product area (payments, assessments, API, etc.)
  * request type (bug, feature_request, product_issue)

### 4. Safe Escalation Handling

Automatically escalates high-risk cases such as:

* fraud / unauthorized transactions
* account compromise
* security vulnerabilities
* prompt injection attempts

---

## System Architecture

```text
main.py        → reads tickets & writes output
agent.py       → classification, escalation, response logic
retriever.py   → corpus indexing + retrieval
```

Pipeline:

1. Parse ticket
2. Detect company + category
3. Retrieve relevant documents
4. Assign confidence score
5. Decide:

   * reply OR escalate
6. Generate structured response

---

## Response Strategy

Each response:

* is grounded in retrieved corpus content
* contains actionable steps
* avoids hallucinated policies

Example flow:

* Strong match → step-by-step resolution
* Weak match → partial guidance + clarification request
* No match → safe fallback

---

## Use of AI

OpenAI API is used **only for response formatting and natural language generation**.

All critical decisions are rule-based and corpus-driven:

* retrieval is strictly from provided data
* classification uses deterministic logic
* escalation is keyword-driven

The model does NOT introduce external knowledge.
All responses are grounded in retrieved support content.

---

## How to Run

```bash
python main.py ../support_tickets/support_tickets.csv ../support_tickets/output.csv
```

---

## Design Decisions

* Avoided embeddings to ensure speed and reproducibility
* Used keyword scoring for transparency and control
* Added confidence-based routing to prevent hallucination
* Limited corpus size for precision over noise

---

## Notes

* No external data sources are used
* Fully deterministic retrieval pipeline
* Designed for reliability, safety, and explainability

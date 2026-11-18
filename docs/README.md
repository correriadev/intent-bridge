# IntentBridge research overview

[Project home](../README.md) · [Architecture decision](ADR.md) · [Product requirements](PRD.md)

## Research question

How can an AI agent recognize that its interpretation of a person’s intent needs to change, and carry that correction into future decisions?

An agent can retrieve an accurate statement and still apply it in the wrong situation, treat an inference as a confirmed preference, or keep relying on a premise after the person has corrected it. IntentBridge studies how evidence, context, and human correction can make the agent’s interpretation revisable.

The original proposal described four roles. A language model interprets and drafts. Active memory uses evidence and its relationships to select which hypotheses deserve attention. A bounded evaluator can check a specific proposal against the available evidence. The person can clarify, reject, or revise the interpretation and recognize what a change resolved.

## Why use an artifact?

The first study explores a narrower hypothesis. Seeing a reversible draft may help a person express an expectation they could not yet formulate. A participant reviews an initial retirement-income screen using fictional data, responds in their own words, and reviews a revision informed by that response. The record connects what the person recognized to the actual version, the observed change or learning, and the contribution that led to it. A rejected version can also yield recognized learning.

The interaction starts with empty project memory. Agreement to try the first artifact opens the session. Recognition of a result is a later event. The pendulum metaphor describes how new evidence can narrow or widen disagreement and change the effort needed for the next agreement. Counts of integrations describe the journey.

## Evidence to date

| Study | Observed result | Open question |
| --- | --- | --- |
| f03 routing spike | A scripted two-turn handoff moved from clarification to answer. The two models tied on one synthetic case, with 12 valid outputs across four test conditions for that case. | Does the result generalize across tasks, models, and handoff failures? |
| F04 graph and semantic review spike | Transitively excluding unsupported derivatives preserved an item with independent support. With a single semantic-review batch, the combined condition passed zero of seven unsuitable proposals and held back one of three proposals labeled acceptable. The label for that case is disputed. | Does graph storage add value over applying the same rules to flat data? Does a semantic reviewer improve results on new cases? |
| Scripted terminal prototype | Four checks covered refusal, acceptance of the original draft without a recorded change, a pending checkpoint on exit, and recognition attached to v2. The scenario also ran through standard input. | Can a live participant give unprompted, specific feedback and recognize what the revision resolved? |
| Local integration spikes | An in-memory SQLite fixture reproduced the F04 projection and rejected an out-of-scope endpoint. Codex App Server discovered a test MCP tool over standard I/O. A simulated MCP client exercised accept, decline, and cancel. | The sandbox prevented a Codex thread from starting. Native confirmation, database durability, multi-user authorization, and Rust performance remain open. |

## What the broader proposal tests

- **Context selection.** Compare a model with no memory, flat retrieval, passive graph retrieval, and active graph selection at the same context budget. Measure whether each approach surfaces relevant corrections and avoids relying on superseded assumptions.
- **Competing interpretations.** Surface contrary evidence when it could change the next action. Track whether it improves decisions or adds unnecessary questions. Preserve the distinction between a primary observation, a human-confirmed preference, and an agent-generated hypothesis.
- **Bounded judgment.** Establish whether a separate evaluator improves outcomes over rules and a structured language model. Track false acceptance, unnecessary intervention, abstention, latency, and cost.

## Research sequence

First, observe a live conversation with free-form feedback. Next, reproduce the workflow and resume it across client sessions with minimal local storage. Compare equivalent retrieval and eligibility policies before attributing gains to a graph. Evaluate bounded review in observation mode before allowing it to alter the workflow.

The [PRD](PRD.md) defines what to observe and the [ADR](ADR.md) records the design and what would justify changing it.

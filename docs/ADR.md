# ADR-001 — Validate intent through a revisable artifact

**Status:** Proposed for the first live study. Validation is pending. The memory server and evaluator choices below are candidates for later experiments.

[Research overview](README.md) · [Product requirements](PRD.md)

## Context

The study starts with an underdefined goal: an app that helps older adults track retirement income. A word such as “balance” can refer to a benefit payment, the amount left after expenses, or something the person has yet to articulate. The initial design asked the person to define the word up front. A reversible draft with fictional data lets the person examine one interpretation and express what they would change. Presenting it as provisional keeps that interpretation open to correction.

The paper’s larger question concerns judgment after human correction. The first experiment isolates a part of that question and keeps the baseline small enough to run locally.

## Decision

Run the first live study with a conversational client, a versioned textual or visual draft, and a record of the exchange. A local terminal or Codex session and manual observation are sufficient for the first run. The scripted terminal prototype demonstrates the workflow with prepared responses. Use actual free-form human feedback for the live study.

1. Propose the smallest examinable artifact. Agreement to try it opens a session with the stated goal and any provisional assumptions. The first study starts with empty project memory.
2. Present v1. Capture the participant’s contribution against that version. A person or agent can supply an artifact.
3. If a revision is warranted, create v2, retaining v1 and linking v2 to the feedback that prompted it. Capture a concrete observation tied to the candidate version.
4. Keep the candidate checkpoint pending until a human recognizes a specific change or learning tied to the examined version. A rejection can support a learning checkpoint if the person identifies what they learned. Silence, cancellation, and a generic response with an ambiguous referent leave the candidate pending.
5. Preserve recognition and provenance on reopening. Update what future turns can rely on while retaining the history of the earlier decision.

## Minimal data contract

| Record | Required relationship |
| --- | --- |
| Contribution | Origin and actor, source event, text, and target version when applicable |
| Artifact version | Stable identifier, examinable snapshot or immutable reference, author, previous version, and originating contributions |
| Evidence | Observation and location on the exact version, with supporting contributions |
| Checkpoint | Candidate change or learning, version, evidence references, lifecycle status, and the human event that recognizes it |
| Session | Stated goal, agreed first step, revisions, and links to the records above |

Only a verified human event can authorize recognition in an automated flow. The client or a trusted adapter supplies a record of an actual human action tied to the candidate and exact version. Model-provided labels such as “human” carry no authority by themselves. Check the candidate version at write time, reject stale revisions, and make retrying the same write idempotent. In an observed study, the facilitator can record the originating human turn directly.

## Later implementation candidates

| Mechanism | Plan and decision trigger |
| --- | --- |
| Local memory | Prototype a Rust MCP server over standard I/O with embedded SQLite after the live study. Expose typed operations to open a session, read context, record contributions, publish a version, propose or request recognition, and reopen a checkpoint. Measure performance before attributing gains to Rust. |
| Codex integration | Use Desktop or CLI for the conversational loop. Test tool discovery, free-form response collection, attribution, and resumption on each client. Consider a small App Server client if a native surface cannot provide the confirmation flow. |
| Session graph | Represent versions, feedback, evidence, and decisions as typed links. Resolve eligibility before building the next context. A dependent item remains eligible when at least one complete, valid support set remains. Compare flat storage and graph storage using the same rules. |
| Referential graph | Promote an explicitly approved, versioned decision when a second session demonstrates a need for reuse. Bind records to tenant and project. Cross-project reuse requires an authorized reference to a specific source and destination, with revocation and validity checked on read. |
| System 1 | Assemble eligible context on each interaction while keeping the evaluator and rubric fixed for comparisons. Compare deterministic rules, a structured LLM, local multilingual Laya, and hosted Jev using the same proposals. Observe supported, conflicting, insufficient, and abstain outcomes before adding any intervention. Human recognition remains a separate event. |

## Consequences and tradeoffs

Asking for a definition before showing a draft is a useful experimental control. It requires less artifact work and could reduce anchoring. Showing a draft may expose unspoken expectations sooner, but the draft can also suggest preferences the participant would not otherwise have expressed.

A local, observed workflow makes the first test cheap and reversible. It leaves persistence, client attribution, and retrieval performance for separate experiments. The [PRD](PRD.md) defines the evidence required to move forward.

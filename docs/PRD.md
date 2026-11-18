# IntentBridge product requirements

**Status:** Research prototype. A supported production release has yet to be planned.

[Research overview](README.md) · [Architecture decision](ADR.md)

## Problem and audience

People often know the outcome they want before they know how to specify it. An AI agent can turn its first guess into a default and keep acting on it after the person offers a correction. The first study is for a person commissioning a retirement-income app and a facilitator observing the collaboration. Older adults are the intended audience for the example app. The study evaluates the interaction with the agent.

## First study

The participant asks for an app that helps older adults track retirement income. The agent offers a provisional screen using fictional data. After the participant agrees, the agent presents v1 and asks an open question such as “What would you change about this screen?” The participant’s own words guide any revision. If they say what the revised version resolved, the facilitator or verified client records that recognition with the change and its evidence.

The session may end without a checkpoint. If the participant rejects a draft and identifies what they learned, that learning can be recorded against the draft they examined. Avoid suggesting the expected preference in the study prompt.

## Acceptance criteria

| ID | Expected behavior | Evidence |
| --- | --- | --- |
| R1 | The session opens only after agreement to try the first artifact. | A refusal leaves the session unopened. The first study starts with empty project memory. |
| R2 | The first draft is clearly provisional, examinable, and uses fictional data. | The exact version shown can be recovered from the study record. |
| R3 | The version and feedback are linked. When v2 is produced, its documented change reflects the participant’s contribution. | v1, the participant’s verbatim feedback, v2, and the change can be inspected together. |
| R4 | A checkpoint becomes integrated only when the participant recognizes a specific change or learning tied to the version they examined. | The checkpoint refers to the candidate, version, evidence, and a distinct human recognition event. Silence and ambiguous recognition leave it pending. |
| R5 | A rejection can yield recognized learning, and reopening preserves history. | A rejected draft can support a learning checkpoint. A reopening records a new event and retains the earlier recognition. |
| R6 | The automated follow-up enforces provenance and version matching. | Agent-authored recognition and confirmation of a superseded version leave the candidate pending. Retrying a valid recognition returns the original result with one integration. |

R1–R5 describe study behavior. R6 is a criterion for the automated follow-up. A single live conversation can demonstrate one path. Use separate scripted cases for branches the participant does not take.

## What to measure

For the first run, record the participant’s initial description, the exact version shown, what they articulated after seeing it, changes made, any recognized outcome, and open disagreements. Compare the feedback after v1 with the participant’s verbatim initial request. A concrete expectation absent from that request is a qualitative observation for that case. Causal effects and changes in effort require a comparison. Record signs that the draft itself suggested the preference.

For a later comparison, test a draft-first condition against open clarification before showing a draft. Keep the goal and task budget comparable. Measure time to the first recognized checkpoint, redundant questions, self-reported effort, rework, and fidelity to the recognized intent. Compare storage and evaluator choices in separate experiments so improvements can be attributed to the change under test.

## Scope and completion

The first study needs fictional inputs, one collaboration journey, and traceable artifacts. A production retirement app, financial recommendations, hosted multi-tenancy, and model training are outside this study.

The next milestone is a completed live session with its evidence recorded, including any pending or rejected candidate. A later beta can close a complete, demonstrable journey and serve as the starting artifact for another cycle. The number of checkpoints is descriptive.

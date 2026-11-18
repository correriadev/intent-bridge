# IntentBridge

An AI agent can remember the facts and still act on the wrong interpretation of what you want. IntentBridge is a research project exploring how people can correct that interpretation and carry the correction into the agent’s next decision.

## The first case

Imagine asking an agent for an app that helps older adults track their retirement income. A first screen shows a balance and a payment history with fictional data. Seeing that screen might help you say something you hadn’t put into words yet: “I want to see what I received this month first.” The agent revises the screen. When you explain what the revision resolved, the system links that recognition to the version you reviewed and the feedback that prompted it.

This is the study scenario. The open question is whether giving someone a reversible draft helps them articulate a preference they had yet to express.

## Project status

The repository starts with the research and design documentation. A scripted terminal prototype exercised four workflow cases before this repository was created. Earlier synthetic experiments examined decision routing, semantic review, and the effect of withdrawing evidence. The live prototype study, Codex confirmation flow, and evaluator comparison are pending.

## Documentation

| Start here | What you’ll find |
| --- | --- |
| [Research overview](docs/README.md) | The hypothesis, prior results, and research questions |
| [Architecture decision](docs/ADR.md) | The minimum workflow, evidence model, and implementation choices |
| [Product requirements](docs/PRD.md) | The first study, acceptance criteria, and evaluation plan |

## Contributing

Open a [GitHub issue](https://github.com/correriadev/intent-bridge/issues) to propose a study case, challenge a hypothesis, or report a reproducible issue. For a proposed case, include the initial request, the feedback or correction, and what you would expect the agent to do next. Use fictional or anonymized examples.

## License

A license has yet to be selected.

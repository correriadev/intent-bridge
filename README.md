# IntentBridge

An AI agent can remember the facts and still act on the wrong interpretation of what you want. IntentBridge is a research project exploring how people can correct that interpretation and carry the correction into the agent’s next decision.

## The first case

Imagine asking an agent for an app that helps older adults track their retirement income. A first screen shows a balance and a payment history with fictional data. Seeing that screen might help you say something you hadn’t put into words yet: “I want to see what I received this month first.” The agent revises the screen. When you explain what the revision resolved, the system links that recognition to the version you reviewed and the feedback that prompted it.

This is the study scenario. The open question is whether giving someone a reversible draft helps them articulate a preference they had yet to express.

## Project status

The repository starts with the research and design documentation. A scripted terminal prototype exercised four workflow cases before this repository was created. Earlier synthetic experiments examined decision routing, semantic review, and the effect of withdrawing evidence. The live prototype study, Codex confirmation flow, and evaluator comparison are pending.

## Local prototype

### Conversation graph in Codex

Start a new Codex chat after registering the local `intentbridge` MCP server.
Invoke `$intentbridge` to activate selective recording in that chat. Ask Codex
to deactivate IntentBridge to stop writes. You can query a saved graph without
activating recording. To continue an existing graph, specify its session ID.
The server offers
`open_session`, `record_turn`, `write_graph`, `list_sessions`, `query_graph`,
and `get_node`. Graph records are stored in `graph/graph.sqlite3` under the
IntentBridge data directory.

For another machine, register from the repository root in PowerShell:

```powershell
$project = (Get-Location).Path
$python = (Get-Command python).Source
codex mcp add intentbridge --env "PYTHONPATH=$project" -- $python -m intent_bridge.mcp
```

### Facilitated terminal study

Requires Python 3.12 or newer. In a terminal, run `python -m intent_bridge check`
and `python -m intent_bridge study`. On Windows the default data directory is
`%LOCALAPPDATA%\IntentBridge\study`. Use `--data-dir` before the command to
select an absolute directory outside this repository.

The facilitator transcribes the participant's words and confirms which version
they examined. Record the session ID displayed in the terminal. Resume with
`python -m intent_bridge resume --session <session-id>`. Run
`python -m unittest discover -s tests -v` to execute the local checks.
Export a session with `python -m intent_bridge export --session <session-id>
--output <absolute-json-path>`. Create a recoverable copy with
`python -m intent_bridge backup --session <session-id> --output
<absolute-sqlite-path>`. Both destinations must be new files in a private
directory. To restore a backup, copy it into the data directory under the
original session ID and retain the `.sqlite3` extension.

The facilitator can show the draft, record feedback or rejection, publish one
revision, propose a checkpoint, record a specific recognition, reopen a
checkpoint, pause, and resume. Review the history before resuming and present
the version again before another recognition.

The prototype stores session records locally. The data and export directories
must be private. The program creates a private data directory when it does not
exist. On Windows it accepts access for the current user, Administrators and
SYSTEM. For an existing directory, correct its permissions or choose another
private directory with `--data-dir`. Use the same option for resume, export
and backup.

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

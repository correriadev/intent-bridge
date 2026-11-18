"""Local newline-delimited MCP stdio server."""

import json
import sqlite3
import sys
from contextlib import closing

from .cli import create_private_directory, data_directory
from .graph import Graph
from .store import connect


def fields(required, optional=None):
    return {"type": "object", "properties": required | (optional or {}),
            "required": list(required), "additionalProperties": False}


def choices(*values):
    return {"type": "string", "enum": list(values)}


def array(items):
    return {"type": "array", "items": items, "maxItems": 100}


ID = {"type": "string", "minLength": 1, "maxLength": 128}
TEXT = {"type": "string", "minLength": 1, "maxLength": 16000}
LIMIT = {"type": "integer", "minimum": 1, "maximum": 100}
NODE = fields({"id": ID, "type": choices("request", "hypothesis", "artifact_version", "feedback",
                                         "evidence", "decision"), "text": TEXT})
EDGE = fields({"id": ID, "type": choices("supports", "contradicts", "revises", "supersedes"),
               "source": ID, "target": ID, "weight": {"type": "number", "minimum": 0, "maximum": 1},
               "rationale": TEXT})
SESSION = {"session_id": ID}
TOOLS = {
    "open_session": ("Open a conversation graph. Reuse this session ID in later turns.",
                     fields(SESSION | {"objective": TEXT})),
    "list_sessions": ("Find previously saved graph sessions.", fields({}, {"limit": LIMIT})),
    "record_turn": ("Record a conversation turn with a stable ID. Role is agent-declared attribution.",
                    fields(SESSION | {"turn_id": ID, "role": choices("user", "assistant"), "text": TEXT})),
    "write_graph": ("Save typed nodes and weighted edges from a recorded turn. IDs are immutable.",
                    fields(SESSION | {"turn_id": ID, "nodes": array(NODE), "edges": array(EDGE)})),
    "query_graph": ("Read graph records and optional continuation cursor.",
                    fields(SESSION, {"kind": choices("node", "edge"), "type": ID, "node_id": ID,
                                     "limit": LIMIT, "after": {"type": "integer", "minimum": 0,
                                                               "maximum": 2**63 - 1}})),
    "get_node": ("Read a node, its source turn and direct relations.", fields(SESSION | {"node_id": ID})),
}


def validate(value, schema):
    kind = schema["type"]
    if kind == "object" and isinstance(value, dict):
        properties = schema["properties"]
        if set(schema["required"]) <= value.keys() <= properties.keys():
            for key, item in value.items():
                validate(item, properties[key])
            return
    elif kind == "array" and isinstance(value, list) and len(value) <= schema["maxItems"]:
        for item in value:
            validate(item, schema["items"])
        return
    elif kind == "string" and isinstance(value, str) and value.strip():
        if ("enum" in schema and value in schema["enum"]
                or "enum" not in schema and len(value) <= schema["maxLength"]):
            return
    elif kind in ("integer", "number"):
        types = (int,) if kind == "integer" else (int, float)
        if type(value) in types and schema["minimum"] <= value <= schema["maximum"]:
            return
    raise ValueError(f"Argumento inválido para {kind}")


def dispatch(graph, method, params):
    if method == "initialize":
        version = params.get("protocolVersion")
        return {"protocolVersion": version if version in {"2024-11-05", "2025-03-26", "2025-06-18",
                                                           "2025-11-25"} else "2025-11-25",
                "capabilities": {"tools": {}}, "serverInfo": {"name": "intentbridge", "version": "0.1.0"},
                "instructions": "During IntentBridge conversations, open a session, record relevant turns, then "
                                "save typed nodes and weighted edges. Reuse stable IDs. Record corrections as "
                                "new nodes and supersedes edges. Use list_sessions to resume. Queries are available "
                                "on request. Tool attribution does not verify human confirmation."}
    if method == "ping":
        return {}
    if method == "tools/list":
        return {"tools": [{"name": name, "description": description, "inputSchema": schema}
                          for name, (description, schema) in TOOLS.items()]}
    if method == "tools/call":
        try:
            name = params.get("name")
            if not isinstance(name, str) or name not in TOOLS:
                raise ValueError("Ferramenta desconhecida")
            arguments = params.get("arguments", {})
            validate(arguments, TOOLS[name][1])
            output = getattr(graph, name)(**arguments)
            return {"content": [{"type": "text", "text": json.dumps(output, ensure_ascii=False)}]}
        except (ValueError, sqlite3.IntegrityError, UnicodeError) as error:
            return {"isError": True, "content": [{"type": "text", "text": str(error)}]}
        except sqlite3.Error:
            return {"isError": True, "content": [{"type": "text", "text": "Falha no SQLite local"}]}
    raise LookupError


def serve(graph, incoming, outgoing):
    for line in incoming:
        request_id = None
        try:
            message = json.loads(line)
            if not isinstance(message, dict) or not isinstance(message.get("method"), str):
                raise ValueError
            if "id" not in message:
                continue
            request_id = message["id"]
            params = message.get("params", {})
            if not isinstance(params, dict):
                raise ValueError
            response = {"result": dispatch(graph, message["method"], params)}
        except LookupError:
            response = {"error": {"code": -32601, "message": "Method not found"}}
        except (ValueError, TypeError):
            response = {"error": {"code": -32600, "message": "Invalid request"}}
        outgoing.write(json.dumps({"jsonrpc": "2.0", "id": request_id, **response}) + "\n")
        outgoing.flush()


def main():
    directory = data_directory(None) / "graph"
    create_private_directory(directory)
    with closing(connect(directory / "graph.sqlite3")) as db:
        serve(Graph(db), sys.stdin.buffer, sys.stdout)


if __name__ == "__main__":
    main()

import io
import json
import unittest

from intent_bridge.graph import Graph
from intent_bridge.mcp import dispatch, serve
from intent_bridge.store import connect


class GraphTest(unittest.TestCase):
    def test_protocol_and_graph_integrity(self):
        db = connect(":memory:")
        self.addCleanup(db.close)
        graph = Graph(db)
        outgoing = io.StringIO()
        serve(graph, [
            '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18"}}',
            '{"jsonrpc":"2.0","method":"notifications/initialized"}',
            '{"jsonrpc":"2.0","id":2,"method":"tools/list"}',
        ], outgoing)
        init, listed = map(json.loads, outgoing.getvalue().splitlines())
        self.assertEqual("2025-06-18", init["result"]["protocolVersion"])
        self.assertEqual(6, len(listed["result"]["tools"]))

        def call(name, **arguments):
            return dispatch(graph, "tools/call", {"name": name, "arguments": arguments})

        graph.open_session("s1", "Objetivo")
        graph.open_session("s2", "Outro objetivo")
        graph.record_turn("s1", "t1", "user", "Quero pesquisar")
        graph.record_turn("s2", "t2", "user", "Outro pedido")
        graph.write_graph("s2", "t2", [{"id": "foreign", "type": "request", "text": "Outro"}], [])
        nodes = [{"id": "n1", "type": "request", "text": "Pesquisa"},
                 {"id": "n2", "type": "evidence", "text": "Fala"}]
        edge = {"id": "e", "type": "supports", "source": "n2", "target": "n1",
                "weight": 0.8, "rationale": "Pedido direto"}
        args = {"session_id": "s1", "turn_id": "t1", "nodes": nodes}
        for invalid in ({**edge, "weight": 1.2}, {**edge, "target": "foreign"}):
            self.assertTrue(call("write_graph", **args, edges=[invalid])["isError"])
            self.assertEqual([], graph.query_graph("s1")["records"])
        self.assertNotIn("isError", call("write_graph", **args, edges=[edge]))
        self.assertNotIn("isError", call("write_graph", **args, edges=[edge]))
        self.assertEqual(3, len(graph.query_graph("s1")["records"]))
        self.assertEqual("codex_declared", graph.get_node("s1", "n1")["turn"]["origin"])
        self.assertTrue(call("record_turn", session_id="s1", turn_id="t3", role="user",
                             text="Pedido", verified=True)["isError"])

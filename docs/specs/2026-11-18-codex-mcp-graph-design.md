# Grafo de intenção no chat do Codex

Você conversa no Codex. Durante a conversa, o Codex chama ferramentas do IntentBridge para registrar o que foi dito, relacionar os registros e consultar o grafo. O teste termina com um grafo recuperável após reabrir o Codex.

## Integração escolhida

MCP local por stdio, registrado no Codex. O Codex inicia o servidor e usa ferramentas com parâmetros tipados. O servidor grava em SQLite privado e reutiliza as regras de sessão e de confirmação do IntentBridge quando aplicáveis. Um comando local também poderia gravar os dados, mas exigiria invocações de shell durante a conversa. O caminho escolhido é MCP.

## Dados e ferramentas

| Ferramenta proposta | Operação |
|---|---|
| `open_session` | Abre uma sessão com identificador estável e objetivo. |
| `record_turn` | Registra um turno e seu papel declarado, com identificador estável para repetição segura. |
| `write_graph` | Grava em uma transação os nós e arestas extraídos de um turno. |
| `query_graph` | Lista ou filtra nós e arestas por sessão, tipo ou nó de origem, com limite de resultados. |
| `get_node` | Mostra um nó, sua evidência e relações diretas. |

Os nós representam pedido, hipótese, versão de artefato, feedback, evidência e decisão. As arestas tipadas registram relações como `supports`, `contradicts`, `revises` e `supersedes`. Cada escrita identifica sessão, turno de origem e autor declarado. Uma correção acrescenta histórico e pode superseder um registro anterior. O servidor valida tipos, existência dos nós, pertencimento à sessão e referências a turnos. Repetir a mesma escrita devolve o resultado anterior.

O ADR especifica relações tipadas e suporte por evidência. Ele não define uma escala numérica de pesos. Para o primeiro teste, a proposta é armazenar em cada aresta um peso entre 0 e 1, atribuído pelo Codex e acompanhado de justificativa curta. O peso representa a força de suporte estimada. Elegibilidade por evidência e confirmação humana continuam sendo verificações distintas. A autoria declarada em argumentos de ferramentas fica registrada como declaração do Codex. Ela não autoriza confirmação humana verificada.

## Uso e aceite

O Codex recebe instruções de uso das ferramentas para registrar os eventos relevantes ao longo do chat. As consultas ficam disponíveis ao usuário e ao Codex durante a conversa. A recuperação automática de contexto, quando usada, segue a elegibilidade por evidência do ADR. JEV fica fora desta integração.

A entrega exige o servidor iniciado pelo Codex, descoberta das ferramentas e um ensaio no chat real. A conversa registra pedido, hipótese, correção e decisão, consulta a decisão com sua evidência, repete uma escrita sem duplicá-la e recupera o mesmo grafo depois de reiniciar o cliente. Testes verificam rejeição de referências entre sessões, peso inválido e tentativa de confirmação humana por mero rótulo do modelo.

## Ativação e gravação durante a conversa

Cada chat começa com a gravação desativada. A pessoa invoca a skill `$intentbridge` para ativar a gravação. A partir daí, o Codex abre uma sessão ou retoma a sessão indicada pela pessoa. O registro vale a partir da ativação e termina se a pessoa pedir para desativar. Ao retomar um chat, o Codex usa o histórico disponível para recuperar a última instrução explícita. Se ela estiver indisponível, pede nova ativação antes de gravar. Consultas explícitas podem ocorrer sem ativar gravações.

Com o registro ativo, o Codex salva por iniciativa própria decisões, restrições, preferências e correções que mudem o entendimento. Usa o turno de origem como evidência, agrupa as mudanças relacionadas em uma gravação e representa interpretações como hipóteses. A instrução orienta o uso seletivo das ferramentas MCP. O término do turno independe de gravação bem-sucedida. Se uma chamada falhar, o Codex segue a conversa e informa o que ficou pendente.

Alternativas consideradas foram instruções de projeto e hooks por turno. Instruções de projeto ficam disponíveis em todos os chats naquele diretório. Hooks por turno podem tornar a captura mais previsível, com custo adicional de execução. O desenho escolhido usa uma skill de invocação explícita. O ensaio deve cobrir chats paralelos, retomada após compactação, desativação e uma falha de MCP que permita concluir o turno.

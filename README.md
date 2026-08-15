# tare.tools — Graph Backlog

Motor determinístico de **Backlog em Grafos Acíclicos Dirigidos (DAG)**, analisador de dependências e gerador de pacotes de implementação para desenvolvimento humano e agentes autônomos.

> **Origem:** Este projeto foi desacoplado do projeto principal (`universal-agent-harness-prototype`, [Issue #35](https://github.com/augusto-scarvalho/universal-agent-harness-prototype/issues/35) e [PR #38](https://github.com/augusto-scarvalho/universal-agent-harness-prototype/pull/38)), tornando-se um **side project independente**, sem dependências externas obrigatórias (funciona com puro Python 3.10+ stdlib).

---

## 🎯 Por que Backlog em Grafos? (vs. Listas / Kanban Tradicionais)

Listas planas e quadros Kanban sofrem de limitações graves em projetos complexos ou orientados a agentes de IA:
1. **Falta de visibilidade de bloqueios:** Não é óbvio qual tarefa desbloqueia o quê.
2. **Priorização cega:** Tarefas de alta prioridade podem estar completamente bloqueadas por itens esquecidos de prioridade menor.
3. **Impossibilidade de cálculo de fronteira:** Um desenvolvedor ou agente precisa adivinhar o que pode ser executado agora sem quebrar dependências.

Com o **Graph Backlog**:
- **`frontier` determinística:** Calcula instantaneamente quais tarefas estão prontas para execução (todos os pré-requisitos satisfeitos).
- **Análise de Bloqueios (`why` / `blockers`):** Explica a causa raiz exata pela qual uma tarefa está travada.
- **Raio de Impacto (`impact` / `deps`):** Mapeia toda a cadeia descendente (o que essa tarefa destrava) e ascendente (do que ela depende).
- **Caminho Crítico (`critical-path`):** Encontra a maior sequência de dependências do projeto.
- **Pacotes de Implementação (`packet`):** Compila o contexto completo de uma tarefa em Markdown para guiar prompts de agentes ou revisões de código.
- **Simulação "What-If" (`simulate`):** Preveja quais tarefas serão destravadas ao concluir itens específicos.
- **Visualizador Web Interativo:** Interface local ou exportável em HTML estático independente.

---

## 🚀 Instalação e Execução Rápida

### Zero Dependências (Pure Python Stdlib)
Você pode executar diretamente sem instalar nada:
```bash
python graph_ops.py --graph fixtures/sample-backlog.json summary
python graph_ops.py --graph fixtures/sample-backlog.json frontier --format ids
```

### Instalação como Pacote Python
```bash
pip install -e .
```
Após instalado, os comandos `graph-backlog` e `graph-ops` ficam disponíveis no seu terminal.

---

## ⚡ Guia Rápido de Comandos CLI

| Comando | O que responde? | Exemplo |
|---|---|---|
| `validate` | A estrutura e o DAG do grafo são válidos? | `python graph_ops.py validate` |
| `summary` | Quantas tarefas, clusters e status existem? | `python graph_ops.py summary` |
| `frontier` | O que está pronto para ser executado **agora**? | `python graph_ops.py frontier --format ids` |
| `next` | Qual é a melhor tarefa factível para puxar? | `python graph_ops.py next --limit 5` |
| `why <id>` | Por que a tarefa está pronta ou bloqueada? | `python graph_ops.py why TASK-03` |
| `blockers <id>` | Quais pré-requisitos diretos travam `<id>`? | `python graph_ops.py blockers TASK-03` |
| `deps <id>` | Quais são todos os pré-requisitos transitivos? | `python graph_ops.py deps TASK-03` |
| `impact <id>` | Quais tarefas serão destravadas no futuro? | `python graph_ops.py impact TASK-01` |
| `path <a> <b>` | Qual é o caminho de dependências de `A` até `B`? | `python graph_ops.py path TASK-01 TASK-03` |
| `critical-path` | Qual é a cadeia mais longa do projeto? | `python graph_ops.py critical-path` |
| `packet <id>` | Gera contexto completo em Markdown para prompts | `python graph_ops.py packet TASK-02 --format md` |
| `simulate` | O que desbloqueia se concluirmos `<id>`? | `python graph_ops.py simulate --mode complete --complete TASK-02` |
| `diff <other>` | O que mudou semanticamente entre 2 versões? | `python graph_ops.py diff other-graph.json` |
| `doctor` | Relatório completo de saúde, integridade e ciclo | `python graph_ops.py doctor` |
| `export` | Exporta para HTML interativo, JSON ou Markdown | `python graph_ops.py export --output backlog.html` |
| `visualize` | Abre servidor web local com visualizador DAG | `python graph_ops.py visualize --port 8080` |

---

## 💻 Uso como Biblioteca Python

```python
from graph_backlog import WorkGraph, compute_frontier, ranked_next, generate_packet

# 1. Carregar grafo
graph = WorkGraph.from_file("fixtures/sample-backlog.json")

# 2. Obter itens prontos para execução
ready_tasks = compute_frontier(graph)
print(f"Tarefas na fronteira: {[t['id'] for t in ready_tasks]}")

# 3. Ranqueamento com pesos determinísticos
top_work = ranked_next(graph, limit=3)
print(f"Próxima recomendada: {top_work[0]['id']} (score: {top_work[0]['score']})")

# 4. Gerar pacote de implementação em Markdown
packet = generate_packet(graph, "TASK-02")
from graph_backlog.packet import format_packet_markdown
print(format_packet_markdown(packet))
```

---

## 📊 Estrutura do Repositório

```text
tare.tools.graph-backlog/
├── README.md                      # Documentação geral
├── pyproject.toml                 # Configuração de empacotamento
├── graph_ops.py                   # Executável CLI direto (zero-config)
├── src/
│   └── graph_backlog/             # Pacote Python principal
│       ├── __init__.py            # Exportações da API
│       ├── core.py                # Modelo de dados e classes WorkGraph / Node / Edge
│       ├── algorithms.py          # Fronteira, ciclos (Tarjan), caminhos, ranking
│       ├── validation.py          # Validação estrutural, de esquemas e integridade
│       ├── diff.py                # Comparação semântica e validação de mudanças
│       ├── ledger.py              # Ledger append-only para auditoria e histórico
│       ├── simulation.py          # Overlays de simulação ("what-if")
│       ├── packet.py              # Compilador de pacotes de implementação
│       ├── visualizer.py          # Exportador HTML e servidor web interativo
│       └── cli.py                 # Parser e despachante da linha de comando
├── docs/
│   ├── ARCHITECTURE.md            # Modelo conceitual e decisões de design
│   ├── CLI_REFERENCE.md           # Referência completa de todos os subcomandos
│   ├── QUICKSTART.md              # Tutorial passo a passo
│   └── ONTOLOGY.md                # Taxonomia de relações e vocabulário
├── fixtures/                      # Exemplos de grafos e fixtures de teste
│   ├── sample-backlog.json        # Template de backlog inicial
│   ├── work-graph-v0.5.json       # Grafo de trabalho completo
│   └── negative-*.json            # Casos de borda para validação de erros
├── visualizer/
│   └── index.html                 # Visualizador estático interativo
└── tests/                         # Suíte de testes automatizados (100% passing)
```

---

## 🧪 Testes Automatizados

Para rodar toda a suíte de testes:
```bash
python -m unittest discover -s tests -v
```

---

## 📄 Licença

MIT License.

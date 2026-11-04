# tare.tools.backlog-graph

Um backlog mantido como grafo de dependências. Ele diz qual trabalho está pronto agora, o que bloqueia o resto e o
que a conclusão de um item destravaria, e compila um resumo autossuficiente para quem pega um item, seja uma pessoa
ou um agente de código. Python 3.10 ou mais novo, só a biblioteca padrão.

[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python Version](https://img.shields.io/badge/Python-3.10%2B-brightgreen.svg)](https://python.org)
[![CI](https://github.com/augusto-scarvalho/tare.tools.backlog-graph/actions/workflows/ci.yml/badge.svg)](https://github.com/augusto-scarvalho/tare.tools.backlog-graph/actions/workflows/ci.yml)

🇺🇸 [Read in English](README.md)

---

## O que faz

O backlog é um grafo de trabalho em JSON: itens com status, prioridade (`P0`–`P3`), horizonte (`H0`–`H3`),
criticidade e definição de pronto, ligados por arestas de dependência tipadas. Sobre ele o motor calcula:

- **Trabalho pronto** (`frontier`, `next`): os itens abertos cujos pré-requisitos estão todos concluídos, ordenados
  por prioridade, horizonte e por quanto trabalho a jusante cada um destrava.
- **Bloqueios e alcance** (`why`, `blockers`, `deps`, `impact`, `path`, `critical-path`): pré-requisitos diretos e
  transitivos, dependentes a jusante, o caminho de dependência mais curto entre dois itens e a cadeia mais longa de
  trabalho aberto.
- **Pacotes de implementação** (`packet`): um resumo em Markdown de um item, com contexto, pré-requisitos e
  definição de pronto.
- **Grounding de trabalho gerenciado** (`ground`): JSON canônico e limitado em bytes, só para trabalho
  operacionalmente pronto com critérios de saída explícitos. O digest do escopo de execução muda quando mudam o item,
  as dependências incidentes, os pré-requisitos diretos ou as fontes referenciadas, para que um runtime gerenciado
  pare quando houver deriva. Ele não concede Authority e nunca escreve o backlog canônico
  ([`docs/MANAGED_WORK_GUARD.md`](docs/MANAGED_WORK_GUARD.md)).
- **E se** (`simulate`): quais itens ficariam prontos se itens candidatos fossem concluídos, sem alterar o grafo.
- **Verificações** (`validate`, `doctor`): validação de esquema e integridade, ciclos (componentes fortemente
  conexos de Tarjan), referências pendentes, requisitos órfãos e lacunas nas notas de evidência.
- **Histórico**: as mudanças rodam como transações compare-and-swap com trava sobre o hash de revisão do grafo, e um
  ledger só de acréscimo encadeia cada evento ao anterior por SHA-256, então editar ou remover um evento antigo
  quebra a cadeia.
- **Visualizações** (`export`, `visualize`): um visualizador HTML autônomo e exports em JSON, Markdown, Mermaid, CSV
  e GraphML.

---

## Importar um backlog

Os importadores leem exports de outras ferramentas e não precisam de pacotes extras:

```bash
# GitHub Issues (lê pela GitHub CLI ou por um export JSON)
gh issue list --limit 100 --json number,title,body,labels,state | python graph_ops.py import-github --out work-graph.json

# Linear (lê um export CSV do Linear ou JSON da API GraphQL)
python graph_ops.py import-linear linear-export.csv --out work-graph.json

# GitLab Issues (lê pela GitLab CLI ou por um export JSON)
glab issue list --output json | python graph_ops.py import-gitlab --out work-graph.json

# Jira Cloud e Server (lê um export CSV do Jira ou o JSON de busca da API REST)
python graph_ops.py import-jira jira-export.csv --out work-graph.json

# Listas de tarefas em Markdown (lê checklists com anotações de dependência)
python graph_ops.py import-md backlog.md --out work-graph.json
```

---

## Instalação e início rápido

### O que você precisa
- Python 3.10 ou mais novo. O motor usa apenas a biblioteca padrão.
- Git, para clonar o repositório.
- Para os testes: `pytest` (instalado pelo extra `dev` abaixo).

### Rodar sem instalar
`graph_ops.py` coloca `src/` no caminho de importação, então um clone novo roda direto:
```bash
git clone https://github.com/augusto-scarvalho/tare.tools.backlog-graph.git
cd tare.tools.backlog-graph

# Resumo do grafo
python graph_ops.py --graph fixtures/sample-backlog.json summary

# Fronteira de execução pronta
python graph_ops.py --graph fixtures/sample-backlog.json frontier --format ids

# Tarefa mais recomendada
python graph_ops.py --graph fixtures/sample-backlog.json next --limit 1
```

### Instalar como pacote
Num ambiente virtual, a partir da raiz do repositório:
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
python -m pip install -e ".[dev]"
```
Depois da instalação, os comandos `backlog`, `graph-backlog` e `graph-ops` ficam disponíveis no ambiente. São a mesma CLI que `python graph_ops.py`.

---

## Referência de comandos da CLI

Todo comando lê o grafo indicado por `--graph <arquivo>` (padrão: `work-graph.json` no diretório atual). Os exemplos abaixo supõem esse arquivo; acrescente `--graph fixtures/sample-backlog.json` para testá-los no exemplo incluído.

| Subcomando | Função e saída | Exemplo de uso |
|---|---|---|
| `validate` | Valida o schema do grafo, a integridade do DAG e a ausência de ciclos | `python graph_ops.py validate` |
| `summary` | Calcula contagens por cluster, status e fronteira | `python graph_ops.py summary` |
| `frontier` | Calcula todas as tarefas prontas, com dependências satisfeitas | `python graph_ops.py frontier --format ids` |
| `next` | Ordena as tarefas acionáveis por prioridade, horizonte e unlock score | `python graph_ops.py next --limit 3` |
| `why <id>` | Explica por que uma tarefa está pronta ou bloqueada, listando os pré-requisitos | `python graph_ops.py why TASK-03` |
| `blockers <id>` | Lista os bloqueios diretos de pré-requisito não satisfeitos | `python graph_ops.py blockers TASK-03` |
| `deps <id>` | Calcula todas as dependências transitivas a montante | `python graph_ops.py deps TASK-03 --format md` |
| `impact <id>` | Calcula todos os dependentes a jusante desbloqueados por `<id>` | `python graph_ops.py impact TASK-01` |
| `path <a> <b>` | Calcula o menor caminho de dependências de `A` até `B` | `python graph_ops.py path TASK-01 TASK-03` |
| `critical-path` | Calcula a sequência de gargalos mais longa do DAG | `python graph_ops.py critical-path` |
| `packet <id>` | Compila contexto Markdown autocontido para agentes de IA | `python graph_ops.py packet TASK-02 --format md` |
| `ground <id>` | Emite JSON operacional limitado e uma cerca de escopo de execução | `python graph_ops.py --format json ground TASK-02 --work-graph fixtures/sample-backlog.json` |
| `simulate` | Projeta as mudanças na fronteira ao concluir trabalho candidato | `python graph_ops.py simulate --complete TASK-02` |
| `diff <other>` | Calcula o diff semântico profundo entre duas fotografias do grafo | `python graph_ops.py diff previous-graph.json` |
| `doctor` | Roda a auditoria de estrutura, ciclos, evidências e reconciliação | `python graph_ops.py doctor` |
| `export` | Exporta para o visualizador HTML autônomo, JSON, Markdown, Mermaid, CSV ou GraphML | `python graph_ops.py export -o index.html --export-format html` |
| `visualize` | Inicia um servidor web local com a interface interativa do DAG | `python graph_ops.py visualize --port 8080` |
| `import-github` | Importa JSON do GitHub Issues ou stdin para o grafo | `python graph_ops.py import-github issues.json` |
| `import-linear` | Importa exports CSV ou JSON do Linear | `python graph_ops.py import-linear export.csv` |
| `import-gitlab` | Importa JSON do GitLab Issues ou stdin para o grafo | `python graph_ops.py import-gitlab gitlab.json` |
| `import-jira` | Importa um export CSV do Jira ou o JSON de busca da API REST | `python graph_ops.py import-jira jira.csv` |
| `import-md` | Importa listas de tarefas estruturadas em Markdown (`backlog.md`) | `python graph_ops.py import-md backlog.md` |

A lista completa, incluindo os comandos de mutação (`add-node`, `complete-node`, `land`, `supersede`), está em [docs/CLI_REFERENCE.md](docs/CLI_REFERENCE.md) (em inglês).

---

## API da biblioteca Python

O mesmo motor como biblioteca Python:

```python
from graph_backlog import (
    WorkGraph,
    compute_frontier,
    ranked_next,
    generate_packet,
    critical_path,
    simulate_completions
)
from graph_backlog.packet import format_packet_markdown

# 1. Carregar o grafo de trabalho
graph = WorkGraph.from_file("fixtures/saas-backlog.json")

# 2. Calcular a fronteira de execução acionável
ready_tasks = compute_frontier(graph)
print(f"Ready to execute: {[t['id'] for t in ready_tasks]}")

# 3. Ordenação determinística
top_work = ranked_next(graph, limit=1)
target_task_id = top_work[0]["id"]
print(f"Next recommended task: {target_task_id} (Score: {top_work[0]['score']})")

# 4. Gerar o pacote de implementação para o prompt de IA
packet = generate_packet(graph, target_task_id)
markdown_prompt = format_packet_markdown(packet)
print(markdown_prompt)

# 5. Simulação contrafactual what-if
sim = simulate_completions(graph, [target_task_id])
print(f"Newly unlocked tasks: {sim['newly_unlocked_nodes']}")
```

---

## O visualizador HTML

`export --export-format html` e `visualize` geram uma página autônoma, sem framework, para qualquer grafo;
[`visualizer/index.html`](visualizer/index.html) é uma cópia pronta que abre no sintético
`fixtures/work-graph-v0.5.json` e também traz os backlogs de demonstração. Ela tem três visões (grafo de
dependências, quadro Kanban, clusters), doze temas de cor (seis escuros, seis claros) e um painel com as ferramentas
de análise, o sandbox de "e se" e o ledger.

### Ler o grafo por um script no navegador

1. **`window.tareGraph`**, pelo console do DevTools ou por um assistente no navegador:
   ```javascript
   window.tareGraph.getSummary();
   window.tareGraph.getFrontier();
   window.tareGraph.getCriticalPath();
   window.tareGraph.simulate(["AUTH-01"], true);
   ```
2. **Um manifesto JSON na página**, `<script id="signal-agentic-manifest" type="application/json">`, mantido em
   sincronia com o grafo, para que um script leia a estrutura sem interpretar o SVG.
3. **Um prompt de briefing**: um texto que resume os gargalos atuais e os itens prontos, para colar num assistente.

---

## Em CI e com agentes de código

### Uma verificação no GitHub Actions
```yaml
name: Work Graph Quality Gate
on: [pull_request, push]

jobs:
  graph-audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Validate DAG & Check Cycles
        run: |
          python graph_ops.py --graph work-graph.json doctor
          python graph_ops.py --graph work-graph.json validate
```

### Entregar um item pronto a um agente de código
```bash
# Compila o resumo do primeiro item pronto:
NEXT_ID=$(python graph_ops.py frontier --format ids | head -n 1)
python graph_ops.py packet $NEXT_ID --format md > .agent/current-context.md
```

---

## Uso no tare.tools.os

O [tare.tools.os](https://github.com/augusto-scarvalho/tare.tools.os) fixa este repositório como submódulo Git em
`satellites/tare.tools.backlog-graph` e o instala como o pacote `tare-tools-backlog-graph`. O OS o usa para validar o
grafo de trabalho, calcular hashes de revisão e fazer transações compare-and-swap no grafo, para ranking e prontidão, e
para o grounding de trabalho gerenciado. Este repositório continua utilizável sozinho: nada aqui importa o OS.

---

## Estrutura do repositório

```text
tare.tools.backlog-graph/
├── README.md / README.pt-BR.md    # Documentação em inglês e em português do Brasil
├── LICENSE, NOTICE                # Apache License 2.0 e atribuição
├── CHANGELOG.md                   # Registro append-only de mudanças
├── pyproject.toml                 # Configuração do pacote
├── graph_ops.py                   # CLI executável direto, sem configuração
├── src/
│   └── graph_backlog/             # Pacote Python principal
│       ├── core.py                # Modelo de dados (WorkGraph) e carga da política padrão
│       ├── algorithms.py          # Fronteira, ciclos (SCC de Tarjan), caminhos, ranking
│       ├── validation.py          # Validação estrutural, de schema e de integridade
│       ├── mutations.py           # Transações compare-and-swap do grafo, com lock
│       ├── grounding.py           # Grounding de trabalho gerenciado (`ground`)
│       ├── diff.py                # Diff semântico e verificação de mutações
│       ├── ledger.py              # Ledger de auditoria append-only encadeado por hash
│       ├── simulation.py          # Sobreposições contrafactuais what-if
│       ├── packet.py              # Compilador de pacotes de implementação
│       ├── adapters.py            # Adaptadores GitHub, Linear, GitLab, Jira, Markdown, Mermaid, CSV, GraphML
│       ├── visualizer.py          # Exportador HTML e visualizador web interativo
│       ├── cli.py                 # Parser de argumentos e despacho da CLI
│       └── contracts/             # Cópias empacotadas das políticas e schemas
├── policies/, schemas/            # Taxonomia de relações, política graph-ops, JSON schemas
├── ontology/                      # Ontologia de domínio legível por máquina
├── docs/                          # Arquitetura, ontologia, referência da CLI, guias (veja docs/INDEX.md)
├── fixtures/                      # Grafos de trabalho sintéticos usados em testes e demos
│   ├── sample-backlog.json        # Backlog inicial com 3 nós
│   ├── work-graph-v0.5.json       # Exemplo completo do schema v0.5 (app de notas fictício)
│   ├── saas-backlog.json          # Backlog SaaS CloudPulse (33 nós)
│   ├── crm-rag-chatbot-backlog.json # Backlog de pipeline RAG de IA (27 nós)
│   ├── transmedia-book-comic-film-backlog.json # Saga transmídia (42 nós)
│   └── negative-*.json            # Um defeito cada: aresta pendente, self loop, status inválido, ...
├── visualizer/index.html          # Visualizador autônomo pré-gerado
├── scripts/                       # Diagnóstico do grafo, quebra de ciclos, relatório de topologia
├── tools/                         # Guard do changelog e instalador de hooks Git
└── tests/                         # Suíte de testes offline
```

Todos os grafos em `fixtures/` são sintéticos. [docs/guides/REPOSITORY_CONTENT.md](docs/guides/REPOSITORY_CONTENT.md)
(em inglês) explica o que a árvore contém e onde estão listados os registros históricos removidos.

---

## Testes automatizados

Com o extra `dev` instalado (veja [Instalar como pacote](#instalar-como-pacote)), rode os mesmos comandos do CI:
```bash
# Canários herméticos de mutação (alguns minutos)
python -m pytest tests/test_mutation_testing.py -v

# Suíte principal de testes
python -m pytest tests/ -v --ignore=tests/test_mutation_testing.py

# Testes do guard do changelog
python -m unittest discover -s tools/tests -p "test_changelog_guard.py"
```

Os testes são offline e usam apenas as fixtures incluídas e diretórios temporários. O teste ponta a ponta no navegador
em `tests/test_e2e_visualizer.py` é pulado se o Playwright não estiver instalado.

Os canários limitados de PR e as campanhas manuais mais amplas de mutação estão documentados
em [docs/MUTATION_TESTING.md](docs/MUTATION_TESTING.md) (em inglês).

---

## Licença e atribuição

Licenciado sob a **Apache License, Version 2.0**. Veja os arquivos [LICENSE](LICENSE) e [NOTICE](NOTICE).

### Autor
- **Autor:** Augusto Carvalho ([augusto-scarvalho@users.noreply.github.com](mailto:augusto-scarvalho@users.noreply.github.com))
- **Projeto:** [tare.tools.backlog-graph](https://github.com/augusto-scarvalho/tare.tools.backlog-graph)
- **Origem:** extraído do protótipo de pesquisa do harness de agentes do tare.tools.

# ADR-001: North Star do tare.tools.backlog-graph — Motor Determinístico de DAG de Tarefas e Framework de Execução Topológica

- **Status:** Ratificado e Aprovado pela Mesa Redonda Tripartite (`CASE-2026-08-17-BACKLOG-GRAPH-NORTH-STAR`)
- **Data:** 2026-08-17
- **Autores:** Antigravity Mediator (sob direcionamento do Operador Humano e consenso da Mesa Tripartite: Google Gemini 3.7 Flash High, Anthropic Claude Fable 5 High, OpenAI GPT-5.6 Sol High)
- **Escopo:** `tare.tools.backlog-graph` (Repositório Standalone Universal)

---

## 1. Contexto e Motivação

Sistemas tradicionais de gestão de tarefas (Jira, Linear, GitHub Projects) operam sobre **filas lineares ou quadros Kanban planos**, ignorando a estrutura topológica inerente da engenharia de software. Essa abordagem gera três patologias sistêmicas:
1. **Cegueira de Bloqueios (*Blocker Blindness*):** Dificuldade de identificar a cadeia de dependências que trava entregas críticas;
2. **Priorização Ilusória (*Blind Prioritization*):** Itens P0 bloqueados por pré-requisitos secundários esquecidos;
3. **Alucinação de Fronteira (*Frontier Hallucination*):** Agentes de IA escolhendo tarefas inviáveis por falta de pré-condições satisfeitas.

O **`tare.tools.backlog-graph`** resolve esse problema transformando o backlog em um **Grafo Acíclico Dirigido (DAG)** com cálculo matemático determinístico da fronteira de trabalho executável.

---

## 2. Decisão Arquitetural

### A. Desacoplamento & Zero Dependências (Pure Python Stdlib):
* O `tare.tools.backlog-graph` é construído **100% em Python puro (stdlib)**, rodando instantaneamente sem dependências pesadas em qualquer ambiente de CI/CD ou máquina local.
* 79 testes unitários e de integração cobrem validação de schemas, ordenação topológica, detecção de ciclos de Tarjan e reconciliação.

### B. Ordenação Total e Determinismo Matemático:
* A fronteira de execução (`frontier` / `next`) segue uma ordenação total estável:
  $$\text{FrontierOrder} = \langle \text{Priority (P0 } > \text{ P1 } > \text{ P2)},\ -\text{CriticalPathDepth},\ \text{NodeID (Lexicográfico)} \rangle$$
* O estado `READY` é **estritamente derivado**: um nó torna-se elegível se e somente se todos os seus pré-requisitos estão `DONE`.

### C. Hash de Revisão Canônico (RFC 8785 / JCS):
* O estado do grafo é content-addressed:
  $$\text{revision\_hash} = \text{sha256}(\text{JCS\_CanonicalJSON}(\text{work-graph without revision}))$$

### D. Transação CAS com Exclusão Mútua:
* Toda mutação é serializada sob um **lockfile exclusivo (`.work-graph.json.lock`)** com gravação em `.tmp`, `fsync` e `os.replace` atômico.
* Landings concorrentes com revisão obsoleta falham fechados com `RevisionMismatchError`.

### E. Conectores Universais:
* Suporte nativo para Jira, Linear, GitLab, GitHub Issues, CSV, Markdown, Mermaid e GraphML.

---

## 3. Roadmap de Implementação em 4 Fases

1. **Fase 1 (Motor Core & Validação — Atual v0.5):** 79 testes passando 100%, algoritmos topológicos e visualizador HTML offline.
2. **Fase 2 (Conectores & Adapters Unidirecionais):** Ingestão de tickets de Jira/Linear/GitHub e sub-grafos federados.
3. **Fase 3 (Visualizador Interativo & Copilot Bridge):** Canvas interativo com simulação *what-if* e injeção de contexto in-editor.
4. **Fase 4 (Distribuição Global & Pacote PyPI):** Pacote oficial no PyPI (`pip install tare-backlog-graph`) e extensão do VS Code.

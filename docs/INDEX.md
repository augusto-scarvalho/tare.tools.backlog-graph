# 📚 ÍNDICE DE DOCUMENTAÇÃO — TARE.TOOLS.BACKLOG-GRAPH

> **Documentação técnica, arquitetura formal e especificações do motor determinístico de DAG de tarefas.**

---

## 🏛️ 1. Decisões Arquiteturais & North Star
* **[`ADR-001_BACKLOG_GRAPH_NORTH_STAR.md`](ADR-001_BACKLOG_GRAPH_NORTH_STAR.md):** Especificação formal dos 8 invariantes do motor (BG-01 a BG-08), garantias de aciclicidade e concorrência CAS.

---

## 📐 2. Arquitetura & Ontologia
* **[`ARCHITECTURE.md`](ARCHITECTURE.md):** Visão arquitetural profunda do grafo acíclico dirigido, isolamento SQLite WAL e transições de estado.
* **[`ONTOLOGY.md`](ONTOLOGY.md):** Taxonomia dos nós de tarefa, relações de bloqueio/dependência e vocabulário semântico.

---

## 🚀 3. Guias & Referência CLI
* **[`QUICKSTART.md`](QUICKSTART.md):** Guia rápido de primeiros passos e comandos essenciais.
* **[`CLI_REFERENCE.md`](CLI_REFERENCE.md):** Manual completo de comandos CLI (`graph_ops.py`) e opções de validação/doctor.
* **[`MANAGED_WORK_GUARD.md`](MANAGED_WORK_GUARD.md):** Cerca de escopo, bloqueio de drift e controle frugal contra estagnação tipo Zenão.

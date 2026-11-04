# OmniAgent CRM — Enterprise RAG & Autonomous Support Chatbot

## Cluster: 00-ai-infra-embeddings
- [x] RAG-01: Vector Database Deployment & Multi-Tenant Partitioning #vector-db,qdrant,hnsw,ai-infra [P0]
- [x] RAG-02: Embedding Pipeline & Semantic Chunking Strategy #embeddings,chunking,nlp,tokenization [P0]
- [x] RAG-03: Document Parsing Engine (PDF, HTML, Docx & Knowledge Articles) #parser,pdf,unstructured,knowledge-base [P0]
- [ ] RAG-04: Cross-Encoder Semantic Re-ranking Service (depends: RAG-01, RAG-02) #reranking,cross-encoder,relevance,search [P0]

## Cluster: 01-crm-connectors
- [x] RAG-10: Salesforce & HubSpot CRM Connector #crm,salesforce,hubspot,oauth [P0]
- [ ] RAG-11: Zendesk & Freshdesk Support Ticket Ingestion (depends: RAG-03, RAG-10) #zendesk,support,help-center,crm [P0]
- [ ] RAG-12: Incremental CDC Sync & Webhook Event Stream (depends: RAG-10, RAG-11) #cdc,webhooks,incremental-sync,streaming [P1]
- [ ] RAG-13: PII Masking, DLP & Sanitization Guardrail (depends: RAG-10) #pii,dlp,security,gdpr,sanitization [P0]

## Cluster: 02-rag-core-engine
- [ ] RAG-20: Hybrid Search Engine (Dense Vectors + Sparse BM25 Fusion) (depends: RAG-01, RAG-04) #hybrid-search,bm25,rrf,retrieval [P0]
- [ ] RAG-21: Contextual Query Rewriter & Multi-Turn Conversation Memory (depends: RAG-20) #query-rewriting,conversation-memory,multi-turn [P0]
- [ ] RAG-22: Grounding System, Prompt Assembly & Citations Anchor (depends: RAG-20, RAG-13) #grounding,citations,prompt-engineering,synthesis [P0]
- [ ] RAG-23: Hallucination Detector & Real-Time Fact-Checking Guardrail (depends: RAG-22) #hallucination-detection,nli,guardrails,safety [P0]
- [ ] RAG-24: Seamless Human Agent Handoff Protocol (depends: RAG-22, RAG-11) #handoff,human-in-the-loop,escalation,support [P1]

## Cluster: 03-agentic-tooling
- [ ] RAG-30: Autonomous Function Calling Engine for CRM Actions (depends: RAG-22, RAG-10) #function-calling,tool-use,autonomous-agent,crm [P0]
- [ ] RAG-31: Human-in-the-Loop Confirmation Gate for Critical Actions (depends: RAG-30) #hitl,safety,approval-workflow,security [P1]
- [ ] RAG-32: Real-Time Sentiment Analysis & High-Value Account Routing (depends: RAG-21, RAG-30) #sentiment,routing,vip,churn-prevention [P1]

## Cluster: 04-frontend-chat-ui
- [x] RAG-40: Embeddable Chatbot Widget & SIGNAL Design Tokens #widget,frontend,signal-design,shadow-dom [P0]
- [ ] RAG-41: Streaming Markdown Renderer & Source Citations Drawer (depends: RAG-40, RAG-22) #streaming,markdown,sse,citations-ui [P0]
- [ ] RAG-42: Copilot Sidebar Extension for Internal Support Agents (depends: RAG-40, RAG-30) #copilot,zendesk-app,chrome-extension,agent-tools [P1]
- [ ] RAG-43: Interactive Feedback Loop (RLHF Thumbs Up/Down & Flagging) (depends: RAG-41) #feedback,rlhf,evals,telemetry [P2]

## Cluster: 05-evals-observability
- [x] RAG-50: LLM Tracing, Token Analytics & OpenLLMetry Pipeline #observability,tracing,langfuse,token-metrics [P0]
- [ ] RAG-51: Automated RAG Triad Evaluation Pipeline (Ragas) (depends: RAG-22, RAG-50) #evals,ragas,faithfulness,ci-cd-evals [P0]
- [ ] RAG-52: Token Quota & LLM Cost Allocation Engine (depends: RAG-50) #cost-control,quotas,rate-limiting,token-budgets [P1]
- [ ] RAG-53: Red Teaming & Prompt Injection Vulnerability Testing (depends: RAG-23, RAG-51) #red-teaming,security,jailbreak,prompt-injection [P0]

## Cluster: 06-compliance-deploy
- [ ] RAG-60: Staging Deployment & Multi-Tenant Concurrency Benchmarking (depends: RAG-20, RAG-40) #staging,load-testing,benchmarks,devops [P0]
- [ ] RAG-61: Zero-Downtime Production Deployment & SLA Monitoring (depends: RAG-60, RAG-23, RAG-42) #production,launch,sre,zero-downtime [P0]
- [ ] RAG-62: GDPR Right-to-be-Forgotten & Vector Purge Engine (depends: RAG-01, RAG-12) #gdpr,privacy,dsar,compliance [P1]

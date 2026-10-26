# 🔍 InsightMiner

> AI-powered customer segmentation & intelligence platform using K-means clustering,
> Azure OpenAI embeddings, and a RAG-based agent interface — built on Azure's
> medallion data lake architecture.

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![Azure](https://img.shields.io/badge/cloud-Azure-0078D4?logo=microsoft-azure)
![License](https://img.shields.io/badge/license-Internal-red)
![Status](https://img.shields.io/badge/status-Draft-yellow)

---

## 📖 Overview

**InsightMiner** is an end-to-end AI-powered customer intelligence platform that
ingests raw customer data, segments it using unsupervised machine learning, enriches
profiles with Azure OpenAI embeddings, and surfaces actionable insights through a
natural language RAG interface orchestrated by Azure AI Agents.

The system is designed for enterprise-scale analytics workflows, supporting up to
**10 million customer records** with sub-500ms query latency and automated pipeline
orchestration.

---

## ✨ Key Features

- 🗂️ **Medallion Data Lake** — Bronze → Silver → Gold layered architecture on Azure Blob Storage
- 🤖 **K-Means Clustering** — Configurable segmentation (k = 2–20) with automated elbow/silhouette scoring
- 🧠 **AI Enrichment** — Embeddings via `text-embedding-3-large` (Azure OpenAI), batch-processed with retry logic
- 🔍 **Hybrid Search** — Keyword + vector search with semantic reranking via Azure AI Search
- 💬 **RAG Query Interface** — Natural language queries grounded in your customer segments
- 🤝 **AI Agent Orchestration** — Azure AI Agents with tool-calling (`search_customers`, `get_cluster_summary`, `compute_segment_stats`)
- 📊 **Reporting & Dashboards** — Cluster summaries, CSV/Excel exports, Power BI dataset push
- 🔐 **Enterprise Security** — Managed identity, private endpoints, AES-256 encryption, RBAC

---

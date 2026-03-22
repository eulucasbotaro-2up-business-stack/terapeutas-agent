"""
Módulo RAG (Retrieval-Augmented Generation) do Terapeutas Agent.

Responsável por:
- Processar PDFs e gerar embeddings (processor)
- Buscar chunks relevantes por similaridade vetorial (retriever)
- Gerar respostas com Claude usando contexto RAG (generator)
"""

from src.rag.generator import (
    classificar_intencao,
    gerar_resposta,
)
from src.rag.processor import processar_pdf
from src.rag.retriever import buscar_contexto

__all__ = [
    "processar_pdf",
    "buscar_contexto",
    "gerar_resposta",
    "classificar_intencao",
]

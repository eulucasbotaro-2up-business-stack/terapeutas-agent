"""
CRUD de terapeutas.
Gerencia cadastro, consulta, atualização e desativação de terapeutas na plataforma.
"""

import logging
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.core.auth import verificar_admin_token
from src.core.supabase_client import get_supabase
from src.core.niveis import MODULOS, obter_nome_modulo
from src.models.schemas import TerapeutaCreate, TerapeutaResponse
from src.rag.aprendizado import (
    registrar_feedback,
    gerar_relatorio_semanal,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/terapeutas",
    tags=["Terapeutas"],
    dependencies=[Depends(verificar_admin_token)],
)


# =============================================
# CRIAR TERAPEUTA
# =============================================

@router.post(
    "/",
    response_model=TerapeutaResponse,
    status_code=201,
    summary="Cadastrar novo terapeuta",
)
async def criar_terapeuta(dados: TerapeutaCreate):
    """
    Cria um novo terapeuta na plataforma.
    Gera um UUID único e salva no Supabase.
    """
    supabase = get_supabase()

    # Verificar se já existe terapeuta com este email
    existente = (
        supabase.table("terapeutas")
        .select("id")
        .eq("email", dados.email)
        .limit(1)
        .execute()
    )

    if existente.data and len(existente.data) > 0:
        raise HTTPException(
            status_code=409,
            detail=f"Já existe um terapeuta cadastrado com o email {dados.email}",
        )

    # Montar registro para inserção
    agora = datetime.now(timezone.utc).isoformat()
    novo_terapeuta = {
        "id": str(uuid4()),
        "nome": dados.nome,
        "email": dados.email,
        "telefone": dados.telefone,
        "especialidade": dados.especialidade,
        "nome_agente": dados.nome_agente,
        "tom_de_voz": dados.tom_de_voz,
        "whatsapp_conectado": False,
        "ativo": True,
        "criado_em": agora,
        "atualizado_em": agora,
    }

    try:
        resultado = supabase.table("terapeutas").insert(novo_terapeuta).execute()
    except Exception as e:
        logger.error(f"Erro ao criar terapeuta: {e}")
        raise HTTPException(status_code=500, detail="Erro interno ao criar terapeuta")

    if not resultado.data:
        raise HTTPException(status_code=500, detail="Falha ao inserir terapeuta no banco")

    logger.info(f"Terapeuta criado: {novo_terapeuta['id']} ({dados.nome})")

    return resultado.data[0]


# =============================================
# LISTAR TERAPEUTAS
# =============================================

@router.get(
    "/",
    response_model=list[TerapeutaResponse],
    summary="Listar todos os terapeutas ativos",
)
async def listar_terapeutas():
    """
    Retorna a lista de todos os terapeutas ativos cadastrados.
    Ordenados por data de criação (mais recentes primeiro).
    """
    supabase = get_supabase()

    try:
        resultado = (
            supabase.table("terapeutas")
            .select("*")
            .eq("ativo", True)
            .order("criado_em", desc=True)
            .execute()
        )
    except Exception as e:
        logger.error(f"Erro ao listar terapeutas: {e}")
        raise HTTPException(status_code=500, detail="Erro interno ao buscar terapeutas")

    return resultado.data or []


# =============================================
# DETALHE DO TERAPEUTA
# =============================================

@router.get(
    "/{terapeuta_id}",
    response_model=TerapeutaResponse,
    summary="Consultar terapeuta por ID",
)
async def obter_terapeuta(terapeuta_id: UUID):
    """
    Retorna os dados completos de um terapeuta pelo seu UUID.
    """
    supabase = get_supabase()

    try:
        resultado = (
            supabase.table("terapeutas")
            .select("*")
            .eq("id", str(terapeuta_id))
            .eq("ativo", True)
            .limit(1)
            .execute()
        )
    except Exception as e:
        logger.error(f"Erro ao buscar terapeuta {terapeuta_id}: {e}")
        raise HTTPException(status_code=500, detail="Erro interno ao buscar terapeuta")

    if not resultado.data or len(resultado.data) == 0:
        raise HTTPException(
            status_code=404,
            detail=f"Terapeuta {terapeuta_id} não encontrado",
        )

    return resultado.data[0]


# =============================================
# ATUALIZAR TERAPEUTA
# =============================================

@router.put(
    "/{terapeuta_id}",
    response_model=TerapeutaResponse,
    summary="Atualizar dados do terapeuta",
)
async def atualizar_terapeuta(terapeuta_id: UUID, dados: TerapeutaCreate):
    """
    Atualiza os dados de um terapeuta existente.
    Todos os campos de TerapeutaCreate podem ser atualizados.
    """
    supabase = get_supabase()

    # Verificar se o terapeuta existe e está ativo
    existente = (
        supabase.table("terapeutas")
        .select("id")
        .eq("id", str(terapeuta_id))
        .eq("ativo", True)
        .limit(1)
        .execute()
    )

    if not existente.data or len(existente.data) == 0:
        raise HTTPException(
            status_code=404,
            detail=f"Terapeuta {terapeuta_id} não encontrado",
        )

    # Verificar conflito de email (se mudou o email)
    conflito_email = (
        supabase.table("terapeutas")
        .select("id")
        .eq("email", dados.email)
        .neq("id", str(terapeuta_id))
        .limit(1)
        .execute()
    )

    if conflito_email.data and len(conflito_email.data) > 0:
        raise HTTPException(
            status_code=409,
            detail=f"O email {dados.email} já está sendo usado por outro terapeuta",
        )

    # Montar dados para atualização
    dados_atualizados = {
        "nome": dados.nome,
        "email": dados.email,
        "telefone": dados.telefone,
        "especialidade": dados.especialidade,
        "nome_agente": dados.nome_agente,
        "tom_de_voz": dados.tom_de_voz,
        "atualizado_em": datetime.now(timezone.utc).isoformat(),
    }

    try:
        resultado = (
            supabase.table("terapeutas")
            .update(dados_atualizados)
            .eq("id", str(terapeuta_id))
            .execute()
        )
    except Exception as e:
        logger.error(f"Erro ao atualizar terapeuta {terapeuta_id}: {e}")
        raise HTTPException(status_code=500, detail="Erro interno ao atualizar terapeuta")

    if not resultado.data:
        raise HTTPException(status_code=500, detail="Falha ao atualizar terapeuta no banco")

    logger.info(f"Terapeuta atualizado: {terapeuta_id}")

    return resultado.data[0]


# =============================================
# DESATIVAR TERAPEUTA (SOFT DELETE)
# =============================================

@router.delete(
    "/{terapeuta_id}",
    summary="Desativar terapeuta (soft delete)",
)
async def desativar_terapeuta(terapeuta_id: UUID):
    """
    Desativa um terapeuta (soft delete).
    Não apaga os dados — apenas marca ativo=False.
    O terapeuta deixa de receber mensagens e não aparece nas listagens.
    """
    supabase = get_supabase()

    # Verificar se o terapeuta existe e está ativo
    existente = (
        supabase.table("terapeutas")
        .select("id")
        .eq("id", str(terapeuta_id))
        .eq("ativo", True)
        .limit(1)
        .execute()
    )

    if not existente.data or len(existente.data) == 0:
        raise HTTPException(
            status_code=404,
            detail=f"Terapeuta {terapeuta_id} não encontrado ou já desativado",
        )

    try:
        supabase.table("terapeutas").update({
            "ativo": False,
            "atualizado_em": datetime.now(timezone.utc).isoformat(),
        }).eq("id", str(terapeuta_id)).execute()
    except Exception as e:
        logger.error(f"Erro ao desativar terapeuta {terapeuta_id}: {e}")
        raise HTTPException(status_code=500, detail="Erro interno ao desativar terapeuta")

    logger.info(f"Terapeuta desativado: {terapeuta_id}")

    return {
        "status": "desativado",
        "terapeuta_id": str(terapeuta_id),
        "mensagem": "Terapeuta desativado com sucesso",
    }


# =============================================
# ATUALIZAR NIVEL DE ACESSO
# =============================================

class NivelAcessoUpdate(BaseModel):
    """Dados para atualizar o nivel de acesso de um terapeuta."""
    nivel: int = Field(..., ge=1, le=6, description="Nivel de acesso (1-6)")


@router.put(
    "/{terapeuta_id}/nivel",
    summary="Atualizar nivel de acesso do terapeuta",
)
async def atualizar_nivel_acesso(terapeuta_id: UUID, dados: NivelAcessoUpdate):
    """
    Atualiza o nivel de acesso de um terapeuta nos modulos da Escola de Alquimia.
    Niveis de 1 (Fundamentos) a 6 (Protocolos e Aplicacao).
    """
    supabase = get_supabase()

    # Verificar se o terapeuta existe e esta ativo
    existente = (
        supabase.table("terapeutas")
        .select("id, nivel_acesso")
        .eq("id", str(terapeuta_id))
        .eq("ativo", True)
        .limit(1)
        .execute()
    )

    if not existente.data or len(existente.data) == 0:
        raise HTTPException(
            status_code=404,
            detail=f"Terapeuta {terapeuta_id} nao encontrado",
        )

    nivel_anterior = existente.data[0].get("nivel_acesso", 1) or 1

    try:
        resultado = (
            supabase.table("terapeutas")
            .update({
                "nivel_acesso": dados.nivel,
                "atualizado_em": datetime.now(timezone.utc).isoformat(),
            })
            .eq("id", str(terapeuta_id))
            .execute()
        )
    except Exception as e:
        logger.error(f"Erro ao atualizar nivel de acesso: {e}")
        raise HTTPException(status_code=500, detail="Erro interno ao atualizar nivel")

    if not resultado.data:
        raise HTTPException(status_code=500, detail="Falha ao atualizar nivel no banco")

    nome_modulo = obter_nome_modulo(dados.nivel)
    nome_anterior = obter_nome_modulo(nivel_anterior)

    logger.info(
        f"Nivel de acesso atualizado: terapeuta={terapeuta_id}, "
        f"{nivel_anterior} ({nome_anterior}) -> {dados.nivel} ({nome_modulo})"
    )

    return {
        "terapeuta_id": str(terapeuta_id),
        "nivel_anterior": nivel_anterior,
        "nivel_atual": dados.nivel,
        "modulo_anterior": nome_anterior,
        "modulo_atual": nome_modulo,
        "modulos_desbloqueados": [
            {"nivel": n, "nome": MODULOS[n]["nome"], "descricao": MODULOS[n]["descricao"]}
            for n in range(1, dados.nivel + 1)
        ],
        "mensagem": f"Nivel atualizado para {dados.nivel} - {nome_modulo}",
    }


# =============================================
# SCHEMAS DE APRENDIZADO
# =============================================

class FeedbackCreate(BaseModel):
    """Dados para registrar feedback sobre uma resposta do agente."""
    conversa_id: str = Field(..., description="UUID da conversa avaliada")
    avaliacao: int = Field(..., ge=1, le=5, description="Nota de 1 (ruim) a 5 (excelente)")
    comentario: str | None = Field(None, max_length=2000, description="Feedback livre da terapeuta")
    tipo: str = Field(
        default="consulta",
        description="Tipo da interacao: consulta, conteudo ou pesquisa",
    )


# =============================================
# FEEDBACK — Terapeuta avalia respostas do agente
# =============================================

@router.post(
    "/{terapeuta_id}/feedback",
    status_code=201,
    summary="Registrar feedback sobre resposta do agente",
)
async def criar_feedback(terapeuta_id: UUID, dados: FeedbackCreate):
    """
    Registra o feedback da terapeuta sobre uma resposta do agente.
    A avaliacao (1-5) e usada pelo sistema de aprendizado continuo
    para melhorar futuras respostas.
    """
    supabase = get_supabase()

    # Verificar se o terapeuta existe
    existente = (
        supabase.table("terapeutas")
        .select("id")
        .eq("id", str(terapeuta_id))
        .eq("ativo", True)
        .limit(1)
        .execute()
    )

    if not existente.data or len(existente.data) == 0:
        raise HTTPException(
            status_code=404,
            detail=f"Terapeuta {terapeuta_id} nao encontrado",
        )

    # Validar tipo
    tipos_validos = ("consulta", "conteudo", "pesquisa")
    if dados.tipo not in tipos_validos:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo invalido. Valores aceitos: {', '.join(tipos_validos)}",
        )

    try:
        resultado = await registrar_feedback(
            terapeuta_id=str(terapeuta_id),
            conversa_id=dados.conversa_id,
            avaliacao=dados.avaliacao,
            comentario=dados.comentario,
            tipo=dados.tipo,
        )

        logger.info(
            f"Feedback registrado: terapeuta={terapeuta_id}, "
            f"conversa={dados.conversa_id}, nota={dados.avaliacao}"
        )

        return {
            "status": "registrado",
            "terapeuta_id": str(terapeuta_id),
            "avaliacao": dados.avaliacao,
            "mensagem": "Feedback registrado com sucesso. O agente vai aprender com isso.",
        }

    except Exception as e:
        logger.error(f"Erro ao registrar feedback: {e}")
        raise HTTPException(status_code=500, detail="Erro interno ao registrar feedback")


# =============================================
# RELATORIO SEMANAL — Resumo de uso e evolucao
# =============================================

@router.get(
    "/{terapeuta_id}/relatorio",
    summary="Gerar relatorio semanal de uso e evolucao",
)
async def obter_relatorio(terapeuta_id: UUID):
    """
    Gera um relatorio semanal para a terapeuta com:
    - Total de consultas na semana
    - Temas mais abordados
    - Florais mais indicados
    - Nivel de maturidade estimado
    - Sugestao de materiais para aprofundamento
    - Media de satisfacao (baseada em feedbacks)
    """
    supabase = get_supabase()

    # Verificar se o terapeuta existe
    existente = (
        supabase.table("terapeutas")
        .select("id")
        .eq("id", str(terapeuta_id))
        .eq("ativo", True)
        .limit(1)
        .execute()
    )

    if not existente.data or len(existente.data) == 0:
        raise HTTPException(
            status_code=404,
            detail=f"Terapeuta {terapeuta_id} nao encontrado",
        )

    try:
        relatorio = await gerar_relatorio_semanal(str(terapeuta_id))
        return relatorio

    except Exception as e:
        logger.error(f"Erro ao gerar relatorio: {e}")
        raise HTTPException(status_code=500, detail="Erro interno ao gerar relatorio")


# =============================================
# PADROES — Ver padroes detectados pelo aprendizado
# =============================================

@router.get(
    "/{terapeuta_id}/padroes",
    summary="Ver padroes detectados pelo aprendizado continuo",
)
async def obter_padroes(terapeuta_id: UUID, tipo: str | None = None, limite: int = 50):
    """
    Retorna os padroes detectados pelo sistema de aprendizado continuo.
    Inclui temas recorrentes, florais mais indicados, nivel de maturidade, etc.

    Query params:
    - tipo: Filtrar por tipo de padrao (tema_recorrente, floral_mais_indicado, etc.)
    - limite: Quantidade maxima de padroes retornados (padrao: 50)
    """
    supabase = get_supabase()

    # Verificar se o terapeuta existe
    existente = (
        supabase.table("terapeutas")
        .select("id")
        .eq("id", str(terapeuta_id))
        .eq("ativo", True)
        .limit(1)
        .execute()
    )

    if not existente.data or len(existente.data) == 0:
        raise HTTPException(
            status_code=404,
            detail=f"Terapeuta {terapeuta_id} nao encontrado",
        )

    try:
        query = (
            supabase.table("padroes_terapeuta")
            .select("*")
            .eq("terapeuta_id", str(terapeuta_id))
            .order("frequencia", desc=True)
            .limit(limite)
        )

        # Filtrar por tipo se especificado
        if tipo:
            query = query.eq("tipo", tipo)

        resultado = query.execute()

        # Buscar tambem o contexto acumulado
        contexto = (
            supabase.table("contexto_terapeuta")
            .select("*")
            .eq("terapeuta_id", str(terapeuta_id))
            .execute()
        )

        return {
            "terapeuta_id": str(terapeuta_id),
            "total_padroes": len(resultado.data) if resultado.data else 0,
            "padroes": resultado.data or [],
            "contexto_acumulado": contexto.data or [],
        }

    except Exception as e:
        logger.error(f"Erro ao buscar padroes: {e}")
        raise HTTPException(status_code=500, detail="Erro interno ao buscar padroes")

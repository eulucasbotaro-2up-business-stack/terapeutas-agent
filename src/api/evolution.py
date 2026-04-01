"""
Endpoints administrativos para o Agente de Evolução.
Permite acionar análises e consultar aprendizados via HTTP.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from src.core.auth import verificar_admin_token
from src.rag.registro_erros import APRENDIZADOS, get_resumo_aprendizados, get_aprendizados_para_llm
from src.agents.evolution_agent import processar_feedback_erro, gerar_relatorio_evolucao

router = APIRouter(
    prefix="/admin/evolution",
    tags=["Evolução"],
    dependencies=[Depends(verificar_admin_token)],
)


class FeedbackErroRequest(BaseModel):
    erro: str
    contexto: Optional[str] = None
    salvar: bool = False


@router.get("/aprendizados", summary="Lista todos os aprendizados registrados")
async def listar_aprendizados():
    return {
        "total": len(APRENDIZADOS),
        "aprendizados": APRENDIZADOS,
    }


@router.get("/resumo", summary="Resumo legível dos aprendizados")
async def resumo_aprendizados():
    return {"resumo": get_resumo_aprendizados()}


@router.get("/regras-llm", summary="Regras injetadas no system prompt")
async def regras_para_llm():
    return {"regras": get_aprendizados_para_llm()}


@router.post("/analisar-erro", summary="Analisa um erro e gera aprendizado estruturado")
async def analisar_erro(req: FeedbackErroRequest):
    try:
        aprendizado = await processar_feedback_erro(
            erro=req.erro,
            contexto=req.contexto,
            salvar_automaticamente=req.salvar,
        )
        return {"aprendizado": aprendizado, "salvo": req.salvar}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/relatorio", summary="Relatório completo de evolução com sugestões")
async def relatorio_evolucao():
    try:
        relatorio = await gerar_relatorio_evolucao()
        return {"relatorio": relatorio}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

"""
Modulo de autenticacao centralizado.

Fornece dependencias FastAPI reutilizaveis para proteger endpoints.
Usa SECRET_KEY como token admin (header X-Admin-Token).

Em producao, substituir por JWT ou OAuth2 — este mecanismo e um
guard minimo para impedir acesso anonimo aos endpoints CRUD.
"""

import logging
from fastapi import Header, HTTPException, status

from src.core.config import get_settings

logger = logging.getLogger(__name__)


def verificar_admin_token(x_admin_token: str = Header(default="")) -> str:
    """
    Dependencia FastAPI que exige header X-Admin-Token valido.

    Valida contra SECRET_KEY. Se SECRET_KEY nao estiver configurada
    (valor padrao 'trocar-em-producao'), BLOQUEIA todos os requests
    para forcar o operador a configurar uma chave segura.

    Returns:
        O token validado (para uso em logging, se necessario).

    Raises:
        HTTPException 503: Se SECRET_KEY nao estiver configurada.
        HTTPException 401: Se o token for invalido ou ausente.
    """
    settings = get_settings()

    # Se SECRET_KEY nao foi configurada, bloqueia tudo
    if not settings.SECRET_KEY or settings.SECRET_KEY == "trocar-em-producao":
        logger.critical(
            "[AUTH] Tentativa de acesso a endpoint protegido sem SECRET_KEY configurada"
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SECRET_KEY nao configurada. Endpoints administrativos desabilitados.",
        )

    # Validar token
    if not x_admin_token or x_admin_token != settings.SECRET_KEY:
        logger.warning("[AUTH] Token admin invalido recebido")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token admin invalido ou ausente. Envie header X-Admin-Token.",
        )

    return x_admin_token

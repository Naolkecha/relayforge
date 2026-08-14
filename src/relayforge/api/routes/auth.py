from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from relayforge.api.dependencies import get_session, get_token_service
from relayforge.api.schemas import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    RegistrationResponse,
    TokenResponse,
)
from relayforge.application.auth import AuthService
from relayforge.security.tokens import TokenService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=RegistrationResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    session: AsyncSession = Depends(get_session),
    tokens: TokenService = Depends(get_token_service),
) -> RegistrationResponse:
    result = await AuthService(session, tokens).register(
        email=str(request.email),
        password=request.password,
        organization_name=request.organization_name,
    )
    return RegistrationResponse(
        user_id=result.user_id,
        organization_id=result.organization_id,
        access_token=result.tokens.access_token,
        refresh_token=result.tokens.refresh_token,
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    session: AsyncSession = Depends(get_session),
    tokens: TokenService = Depends(get_token_service),
) -> TokenResponse:
    pair = await AuthService(session, tokens).login(
        email=str(request.email),
        password=request.password,
        organization_id=request.organization_id,
    )
    return TokenResponse(access_token=pair.access_token, refresh_token=pair.refresh_token, token_type=pair.token_type)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: RefreshRequest,
    session: AsyncSession = Depends(get_session),
    tokens: TokenService = Depends(get_token_service),
) -> TokenResponse:
    pair = await AuthService(session, tokens).refresh(request.refresh_token)
    return TokenResponse(access_token=pair.access_token, refresh_token=pair.refresh_token, token_type=pair.token_type)

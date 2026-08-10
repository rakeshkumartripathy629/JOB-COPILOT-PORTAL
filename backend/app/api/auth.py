from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.middleware.rate_limit import limiter
from app.repositories.user_repo import UserRepository
from app.schemas.auth import (
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    ResetPasswordRequest,
    Token,
    UserLogin,
    UserResponse,
    UserSignup,
)
from app.services.auth_service import AuthService

router = APIRouter()


@router.post("/signup", response_model=UserResponse, status_code=201)
@limiter.limit("10/minute")
async def signup(request: Request, data: UserSignup, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    user = await service.create_user(data.email, data.password, data.full_name)
    return UserResponse.model_validate(user)


@router.post("/login", response_model=Token)
@limiter.limit("20/minute")
async def login(request: Request, data: UserLogin, response: Response, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    user = await service.authenticate(data.email, data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    access = service.create_access_token(user.id)
    refresh = await service.create_refresh_token(user.id)
    response.set_cookie(
        key="refresh_token",
        value=refresh,
        httponly=True,
        secure=False,
        samesite="strict",
        max_age=7 * 24 * 60 * 60,
    )
    return Token(access_token=access)


@router.post("/refresh", response_model=Token)
@limiter.limit("20/minute")
async def refresh(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="No refresh token")
    service = AuthService(db)
    db_token = await service.verify_refresh_token(token)
    user = await UserRepository(db).get(db_token.user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    access = service.create_access_token(user.id)
    new_refresh = await service.create_refresh_token(user.id)
    await service.revoke_refresh_token(token)
    response.set_cookie(
        key="refresh_token",
        value=new_refresh,
        httponly=True,
        secure=False,
        samesite="strict",
        max_age=7 * 24 * 60 * 60,
    )
    return Token(access_token=access)


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
@limiter.limit("10/minute")
async def forgot_password(request: Request, data: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    code = await service.request_password_reset(data.email)
    return ForgotPasswordResponse(
        message="Reset code generated. Enter it along with your new password to reset.",
        reset_code=code,
    )


@router.post("/reset-password")
@limiter.limit("10/minute")
async def reset_password(request: Request, data: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    await service.reset_password(data.email, data.code, data.new_password)
    return {"detail": "Password reset successfully. You can now log in."}


@router.post("/logout")
async def logout(response: Response, request: Request, db: AsyncSession = Depends(get_db)):
    token = request.cookies.get("refresh_token")
    if token:
        service = AuthService(db)
        await service.revoke_refresh_token(token)
    response.delete_cookie("refresh_token")
    return {"detail": "Logged out"}


@router.get("/google")
async def google_oauth():
    return {"detail": "Google OAuth not implemented yet"}

import logging
import random
import secrets
from datetime import datetime, timedelta

import bcrypt
from jose import JWTError, jwt
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models.password_reset import PasswordResetToken
from app.db.models.refresh_token import RefreshToken
from app.db.models.user import User
from app.middleware.error_handler import AppException
from app.repositories.refresh_token import RefreshTokenRepository
from app.repositories.user_repo import UserRepository

logger = logging.getLogger(__name__)


def _hash_code(code: str) -> str:
    return bcrypt.hashpw(code.encode(), bcrypt.gensalt()).decode()


class AuthService:
    def __init__(self, db: AsyncSession):
        self.user_repo = UserRepository(db)
        self.db = db
        self.refresh_repo = RefreshTokenRepository(db)

    @staticmethod
    def hash_password(password: str) -> str:
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    @staticmethod
    def verify_password(plain: str, hashed: str) -> bool:
        return bcrypt.checkpw(plain.encode(), hashed.encode())

    def create_access_token(self, user_id: int) -> str:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        payload = {"sub": str(user_id), "exp": expire}
        token: str = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        return token

    async def create_refresh_token(self, user_id: int) -> str:
        token = secrets.token_urlsafe(64)
        expires = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        hashed: str = jwt.encode(
            {"sub": str(user_id), "jti": token, "exp": expires},
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )
        db_token = RefreshToken(
            user_id=user_id,
            token=hashed,
            expires_at=expires,
        )
        self.db.add(db_token)
        await self.db.commit()
        return hashed

    async def verify_refresh_token(self, token: str) -> RefreshToken:
        try:
            jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        except JWTError:
            raise AppException(401, "Invalid refresh token") from None

        db_token = await self.refresh_repo.get_by_token(token)
        if not db_token or db_token.revoked:
            raise AppException(401, "Refresh token revoked")

        if db_token.expires_at < datetime.utcnow():
            raise AppException(401, "Refresh token expired")

        return db_token

    async def revoke_refresh_token(self, token: str):
        db_token = await self.refresh_repo.get_by_token(token)
        if db_token:
            db_token.revoked = True
            db_token.revoked_at = datetime.utcnow()
            await self.db.commit()

    async def authenticate(self, email: str, password: str) -> User | None:
        user = await self.user_repo.get_by_email(email)
        if not user or not user.hashed_password:
            return None
        if not self.verify_password(password, user.hashed_password):  # type: ignore[arg-type]
            return None
        return user

    async def create_user(self, email: str, password: str, full_name: str):
        existing = await self.user_repo.get_by_email(email)
        if existing:
            raise AppException(400, "Email already registered")
        user = await self.user_repo.create(
            {
                "email": email,
                "hashed_password": self.hash_password(password),
                "full_name": full_name,
            }
        )
        return user

    async def request_password_reset(self, email: str) -> str:
        """Create a 6-digit reset code. Returns the plaintext code (dev delivery)."""
        user = await self.user_repo.get_by_email(email)
        if not user:
            raise AppException(404, "No account found with this email")

        await self.db.execute(
            delete(PasswordResetToken).where(
                PasswordResetToken.user_id == user.id, PasswordResetToken.used.is_(False)
            )
        )

        code = f"{random.randint(0, 999999):06d}"
        self.db.add(
            PasswordResetToken(
                user_id=user.id,
                code_hash=_hash_code(code),
                expires_at=datetime.utcnow() + timedelta(minutes=10),
            )
        )
        await self.db.commit()

        # Email delivery is attempted when SMTP credentials are configured.
        await self._send_reset_email(email, code)
        return code

    async def reset_password(self, email: str, code: str, new_password: str) -> None:
        user = await self.user_repo.get_by_email(email)
        if not user:
            raise AppException(404, "No account found with this email")

        result = await self.db.execute(
            select(PasswordResetToken)
            .where(
                PasswordResetToken.user_id == user.id,
                PasswordResetToken.used.is_(False),
            )
            .order_by(PasswordResetToken.created_at.desc())
        )
        token = result.scalars().first()
        if not token:
            raise AppException(400, "No active reset request. Request a new code.")
        if token.expires_at < datetime.utcnow():
            raise AppException(400, "Reset code expired. Request a new code.")
        if not bcrypt.checkpw(code.encode(), token.code_hash.encode()):
            raise AppException(400, "Invalid reset code")

        user.hashed_password = self.hash_password(new_password)
        token.used = True
        await self.db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user.id)
            .values(revoked=True)
        )
        await self.db.commit()

    async def _send_reset_email(self, email: str, code: str) -> None:
        if not settings.EMAIL_SENDER or not settings.EMAIL_PASSWORD:
            logger.info("SMTP not configured; reset code %s delivered in API response for %s", code, email)
            return
        try:
            from email.message import EmailMessage

            import aiosmtplib

            msg = EmailMessage()
            msg["From"] = settings.EMAIL_SENDER
            msg["To"] = email
            msg["Subject"] = "AI Job Copilot - Password Reset Code"
            msg.set_content(f"Your password reset code is {code}. It expires in 10 minutes.")
            await aiosmtplib.send(msg, hostname=settings.EMAIL_HOST, port=settings.EMAIL_PORT or 587)
        except Exception as exc:
            logger.warning("Reset email send failed: %s", exc)

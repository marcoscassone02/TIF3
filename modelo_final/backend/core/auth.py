"""Autenticación JWT y permisos por bodega."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated
import os
import secrets

import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash
from pydantic import BaseModel

from .base_datos import connect, initialize
from .multiempresa import initialize_multitenancy

BACKEND_ROOT = Path(__file__).resolve().parents[1]
SECRET_FILE = BACKEND_ROOT / ".grapesense_secret"
ALGORITHM = "HS256"
TOKEN_HOURS = 12
password_hash = PasswordHash.recommended()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


class CurrentUser(BaseModel):
    usuario_id: int
    bodega_id: int
    nombre: str
    email: str
    rol: str
    bodega_nombre: str


def secret_key():
    configured = os.getenv("GRAPESENSE_SECRET_KEY")
    if configured:
        return configured
    if not SECRET_FILE.exists():
        SECRET_FILE.write_text(secrets.token_hex(32))
        SECRET_FILE.chmod(0o600)
    return SECRET_FILE.read_text().strip()


def create_token(user):
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user["usuario_id"]),
        "bodega_id": user["bodega_id"],
        "rol": user["rol"],
        "iat": now,
        "exp": now + timedelta(hours=TOKEN_HOURS),
    }
    return jwt.encode(payload, secret_key(), algorithm=ALGORITHM)


def authenticate(email, password):
    with connect() as connection:
        initialize(connection)
        initialize_multitenancy(connection)
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT u.usuario_id, u.bodega_id, u.nombre, u.email, u.rol,
                       u.password_hash, b.nombre
                FROM usuarios u JOIN bodegas b ON b.bodega_id = u.bodega_id
                WHERE LOWER(u.email) = LOWER(%s) AND u.activo AND b.activa
            """, (email.strip(),))
            row = cursor.fetchone()
    if row is None or not password_hash.verify(password, row[5]):
        return None
    return {
        "usuario_id": row[0], "bodega_id": row[1], "nombre": row[2],
        "email": row[3], "rol": row[4], "bodega_nombre": row[6],
    }


def get_current_user(
    token: Annotated[str | None, Depends(oauth2_scheme)],
    selected_winery: Annotated[int | None, Header(alias="X-Bodega-ID")] = None,
):
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="La sesión no es válida o venció",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_error
    try:
        payload = jwt.decode(token, secret_key(), algorithms=[ALGORITHM])
        user_id = int(payload.get("sub"))
    except (InvalidTokenError, TypeError, ValueError):
        raise credentials_error
    with connect() as connection:
        initialize(connection)
        initialize_multitenancy(connection)
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT u.usuario_id, u.bodega_id, u.nombre, u.email, u.rol, b.nombre
                FROM usuarios u JOIN bodegas b ON b.bodega_id = u.bodega_id
                WHERE u.usuario_id = %s AND u.activo AND b.activa
            """, (user_id,))
            row = cursor.fetchone()
    if row is None:
        raise credentials_error
    bodega_id, bodega_name = row[1], row[5]
    if row[4] == "superadmin" and selected_winery is not None:
        with connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT bodega_id, nombre FROM bodegas WHERE bodega_id = %s AND activa",
                    (selected_winery,),
                )
                selected = cursor.fetchone()
        if selected is None:
            raise HTTPException(status_code=404, detail="La organización seleccionada no existe")
        bodega_id, bodega_name = selected
    return CurrentUser(
        usuario_id=row[0], bodega_id=bodega_id, nombre=row[2], email=row[3],
        rol=row[4], bodega_nombre=bodega_name,
    )


def require_roles(*roles):
    def dependency(user: Annotated[CurrentUser, Depends(get_current_user)]):
        if user.rol not in roles:
            raise HTTPException(status_code=403, detail="No tienes permisos para esta operación")
        return user
    return dependency

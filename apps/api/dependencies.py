"""
Zentrale Admin-Auth Dependency.
Akzeptiert NUR: Authorization: Bearer <key>
Query-Parameter admin_key ist ENTFERNT (CRIT-01).
Fail-closed wenn ADMIN_KEY nicht konfiguriert in Production.
"""
import os
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional

security = HTTPBearer(auto_error=False)


def verify_admin_key(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
) -> bool:
    configured_key = os.getenv("ADMIN_KEY", "")

    # Fail-closed: kein Key konfiguriert oder Default in Production
    if not configured_key or configured_key == "dev-admin-key":
        env = os.getenv("ENVIRONMENT", "production")
        if env == "production":
            raise HTTPException(status_code=403, detail="Admin-Zugang nicht konfiguriert")
        # Development: dev-admin-key erlaubt
        configured_key = configured_key or "dev-admin-key"

    # NUR Bearer Token
    if credentials and credentials.credentials == configured_key:
        return True

    raise HTTPException(status_code=403, detail="Ungueltiger Admin-Key")

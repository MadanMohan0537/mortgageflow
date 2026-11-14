from dataclasses import dataclass
from secrets import compare_digest
from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import identities

bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Actor:
    id: str
    role: str

    def require(self, role: str) -> None:
        if self.role != role:
            raise HTTPException(403, f"{role.capitalize()} access required")


def authenticate(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> Actor:
    if credentials and credentials.credentials.isascii():
        result = None
        for token, identity in identities().items():
            if compare_digest(token, credentials.credentials):
                result = Actor(*identity)
        if result:
            return result
    raise HTTPException(401, "Valid bearer token required", headers={"WWW-Authenticate": "Bearer"})

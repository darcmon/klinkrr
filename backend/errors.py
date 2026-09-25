from fastapi import HTTPException


def api_error(status_code: int, code: str, message: str, **extra) -> HTTPException:
    """An error the frontend can branch on: `detail` is
    `{"code": ..., "message": ..., **extra}` instead of a plain string."""
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message, **extra},
    )

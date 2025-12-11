from typing import Optional, Any
from fastapi import status
from fastapi.responses import JSONResponse


def response(status_code: int = status.HTTP_400_BAD_REQUEST, message: Optional[str] = None, data: Any = None):
    if data and isinstance(data, dict) and data.get("error_text"):
        message = data.get("error_text")

    body = {
        'status': status_code,
        'message': message,
        'data': data
    }
    return JSONResponse(content=body, status_code=status.HTTP_200_OK, headers={'Cache-Control': 'no-cache'})
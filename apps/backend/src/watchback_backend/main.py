from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from watchback_backend.api.routes import router as review_cases_router


app = FastAPI(
    title="Watchback API",
    version="0.1.0",
    description="Dependabot Alert의 위험 변화 재검토 계약 API",
)
app.include_router(review_cases_router)


@app.exception_handler(RequestValidationError)
async def request_validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    del request
    return JSONResponse(
        status_code=422,
        content={
            "code": "validation_error",
            "message": "요청 값이 API 계약에 맞지 않습니다.",
            "details": jsonable_encoder(exc.errors()),
        },
    )

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.routers import contacts, health, me, push, sos, sos_ws

logger = logging.getLogger("app")

app = FastAPI(title="Women Safety SOS App API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.frontend_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # A handler registered for the bare `Exception` class is treated specially
    # by Starlette: it becomes ServerErrorMiddleware's handler, which sits
    # OUTSIDE CORSMiddleware in the stack (see Starlette's
    # Starlette.build_middleware_stack — only Exception/500 handlers are
    # pulled out this way; handlers for specific exception types stay inside
    # CORSMiddleware and don't need this). That means CORSMiddleware never
    # gets a chance to stamp this response, so the browser sees a
    # same-origin-policy violation and reports it to JS as a generic
    # "Failed to fetch" — the real 500 and its message are invisible.
    # Adding the header ourselves, rather than relying on CORSMiddleware,
    # is what actually fixes it.
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    response = JSONResponse(
        status_code=500,
        content={"detail": "Something went wrong on our end. Please try again in a moment."},
    )
    origin = request.headers.get("origin")
    if origin in settings.frontend_origins_list:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
    return response


app.include_router(health.router)
app.include_router(me.router)
app.include_router(sos.router)
app.include_router(sos_ws.router)
app.include_router(push.router)
app.include_router(contacts.router)

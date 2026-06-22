"""FastAPI entrypoint for the PDF redaction auditor."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .config import get_cors_origins, get_limits
from .routes import scan, vectors
from .schemas import ErrorResponse, HealthResponse
from .services.scanner import PDFCorruptError, PDFEncryptedError

logger = logging.getLogger("pdf-auditor")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

# Slack above the file-size cap to allow for multipart framing (boundaries, part
# headers) so a file at exactly the limit is not rejected for a few framing bytes.
_MULTIPART_OVERHEAD = 4096


# Module-level readiness flag. Set to a tuple (status, detail, vectors_ready)
# by the lifespan handler before the first request is served. The /health
# endpoint reads this on every call so it reflects the true warmup state, not
# just "the port is bound".
#
# Starting value is ("warming", "starting up", 0) so a /health hit that races
# the lifespan handler still reports "warming" instead of falsely "ok".
_READINESS: tuple[str, str, int] = ("warming", "starting up", 0)


def _set_readiness(status: str, detail: str = "", vectors_ready: int = 0) -> None:
    global _READINESS
    _READINESS = (status, detail, vectors_ready)
    logger.info("readiness=%s detail=%r vectors_ready=%d", status, detail, vectors_ready)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Warm the detector engine at startup so /health can answer truthfully.

    On free-tier hosts (Render) the process gets restarted on cold start. The
    FastAPI port binds almost immediately, but the first scan would otherwise
    pay the full pdfaudit / pikepdf / pdfminer import cost — and a status pill
    that said "live" during that window would lie. We do that import work
    here, once, and only then flip readiness to "ok".
    """
    _set_readiness("warming", "loading detector engine")
    try:
        # Importing pdfaudit + constructing Engine() forces the pikepdf,
        # pdfminer.six, and defusedxml modules to load. Anything that would
        # otherwise happen on the first /scan request, happens here instead.
        from pdfaudit import Engine  # noqa: WPS433 (intentional startup import)

        engine = Engine()
        ready_vectors = len(engine.available_vectors())
        _set_readiness("ok", "", ready_vectors)
        logger.info("detector engine warmed: %d vectors ready", ready_vectors)
    except Exception as exc:  # pragma: no cover — surface a real failure
        logger.exception("detector warmup failed")
        _set_readiness("degraded", f"{type(exc).__name__}: {exc}", 0)
    yield
    # Shutdown hook (nothing to do — Engine() is stateless and pikepdf closes
    # the BytesIO it was opened from on its own).


def create_app() -> FastAPI:
    _ = get_limits()  # resolved per-request inside routes; called here to surface bad env at boot
    app = FastAPI(
        title="PDF Redaction Auditor",
        version="0.1.0",
        docs_url="/docs",
        redoc_url=None,
        lifespan=_lifespan,
    )

    # CORS — explicit allow-list from env (defaults to localhost dev origins),
    # never a hardcoded wildcard. See config.get_cors_origins.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_cors_origins(),
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition"],
    )

    # Reject oversized uploads up front (on Content-Length) so a huge body is not
    # fully received/spooled before the route can check its size. The per-file size
    # is still enforced exactly in the route; this is the cheap early gate.
    @app.middleware("http")
    async def _limit_body_size(request: Request, call_next):
        cl = request.headers.get("content-length")
        if cl is not None:
            try:
                length = int(cl)
            except ValueError:
                length = None
            if length is not None and length > get_limits().max_file_bytes + _MULTIPART_OVERHEAD:
                return JSONResponse(
                    status_code=413,
                    content=ErrorResponse(error="request body too large").model_dump(),
                )
        return await call_next(request)

    @app.exception_handler(StarletteHTTPException)
    async def _http_exc(_req: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(error=str(exc.detail)).model_dump(),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_exc(_req: Request, exc: RequestValidationError) -> JSONResponse:
        # Normalise FastAPI's default {"detail": [...]} into our {"error": "..."}
        # envelope so every error response shares one shape (matches the OpenAPI
        # 422 ErrorResponse and the frontend's error parsing).
        parts = [
            f"{'.'.join(str(p) for p in e.get('loc', []))}: {e.get('msg', '')}".strip(": ")
            for e in exc.errors()
        ]
        message = "; ".join(p for p in parts if p) or "invalid request"
        return JSONResponse(
            status_code=422,
            content=ErrorResponse(error=message).model_dump(),
        )

    @app.exception_handler(PDFEncryptedError)
    async def _enc(_req: Request, exc: PDFEncryptedError) -> JSONResponse:
        return JSONResponse(
            status_code=415,
            content=ErrorResponse(error=str(exc)).model_dump(),
        )

    @app.exception_handler(PDFCorruptError)
    async def _corrupt(_req: Request, exc: PDFCorruptError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=ErrorResponse(error=str(exc)).model_dump(),
        )

    @app.exception_handler(Exception)
    async def _unhandled(_req: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled error")
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(error="internal server error").model_dump(),
        )

    @app.get("/api/v1/health", response_model=HealthResponse, tags=["meta"])
    async def health() -> JSONResponse:
        """Readiness probe. Returns 200 only when the engine is truly warm.

        A cold start returns 503 + "warming" so the frontend status pill can
        render "LAUNCHING…" instead of falsely advertising "LIVE". The body
        carries the vectors_ready count so the UI can show progress if it
        wants to.
        """
        status, detail, vectors_ready = _READINESS
        body = HealthResponse(
            status=status,  # type: ignore[arg-type]
            detail=detail,
            vectors_ready=vectors_ready,
        ).model_dump()
        http_status = 200 if status == "ok" else 503
        return JSONResponse(status_code=http_status, content=body)

    app.include_router(vectors.router, prefix="/api/v1", tags=["meta"])
    app.include_router(scan.router, prefix="/api/v1", tags=["scan"])

    return app


app = create_app()
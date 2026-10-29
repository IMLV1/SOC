"""Bound API bodies before authentication and JSON parsing allocate more memory."""

from urllib.parse import unquote_to_bytes
from uuid import uuid4

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

MAX_API_BODY_BYTES = 1024 * 1024


class ApiBodyLimit:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope["path"].startswith("/api/v1/"):
            await self.app(scope, receive, send)
            return
        if "\x00" in scope["path"] or b"\x00" in unquote_to_bytes(scope["query_string"]):
            await self.reject(scope, receive, send, 422)
            return
        lengths = [value for key, value in scope["headers"] if key == b"content-length"]
        if lengths and (len(lengths) != 1 or not lengths[0].isdigit()):
            await self.reject(scope, receive, send, 400)
            return
        if lengths and len(lengths[0]) > 20:
            await self.reject(scope, receive, send, 413)
            return
        declared = int(lengths[0]) if lengths else None
        if declared is not None and declared > MAX_API_BODY_BYTES:
            await self.reject(scope, receive, send, 413)
            return
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            if len(body) + len(chunk) > MAX_API_BODY_BYTES:
                await self.reject(scope, receive, send, 413)
                return
            body.extend(chunk)
            if not message.get("more_body", False):
                break
        if declared is not None and len(body) != declared:
            await self.reject(scope, receive, send, 400)
            return
        delivered = False

        async def replay() -> Message:
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, replay, send)

    @staticmethod
    async def reject(scope: Scope, receive: Receive, send: Send, status: int) -> None:
        request_id = str(uuid4())
        response = JSONResponse(
            status_code=status,
            content={
                "error": {
                    "code": {400: "BAD_REQUEST", 413: "PAYLOAD_TOO_LARGE", 422: "VALIDATION_ERROR"}[
                        status
                    ],
                    "message": "Request could not be processed.",
                },
                "meta": {"request_id": request_id},
            },
            headers={"Cache-Control": "no-store", "X-Request-ID": request_id},
        )
        await response(scope, receive, send)

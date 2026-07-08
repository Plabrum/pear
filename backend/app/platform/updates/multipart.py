from __future__ import annotations

import uuid
from typing import Literal

import msgspec

PartName = Literal["manifest", "directive"]


class MultipartPart(msgspec.Struct, frozen=True):
    """One MIME part of a hand-assembled `multipart/mixed` response body.

    Litestar has no response-side multipart support — `litestar.params.MultipartBody`
    only covers *parsing* incoming `multipart/form-data` request bodies, not building
    outgoing multipart responses. This struct is the typed shape `encode_multipart_mixed`
    consumes, so callers can't pass a header dict with the wrong keys or forget a field.
    """

    name: PartName
    body: bytes
    content_type: str = "application/json; charset=utf-8"
    extra_headers: dict[str, str] = msgspec.field(default_factory=dict)


def encode_multipart_mixed(parts: list[MultipartPart]) -> tuple[bytes, str]:
    """Encode `parts` as a `multipart/mixed` body. Returns `(body_bytes, content_type)`.

    Mirrors how `media/local_routes.py` builds raw `Response(...)` for other non-JSON
    content types in this codebase — there's no framework helper for this direction.
    """
    boundary = uuid.uuid4().hex
    chunks: list[bytes] = []
    for part in parts:
        headers = [
            f'Content-Disposition: form-data; name="{part.name}"'.encode(),
            f"Content-Type: {part.content_type}".encode(),
        ]
        headers.extend(f"{key}: {value}".encode() for key, value in part.extra_headers.items())
        chunks.append(f"--{boundary}".encode())
        chunks.extend(headers)
        chunks.append(b"")
        chunks.append(part.body)
    chunks.append(f"--{boundary}--".encode())
    # Trailing empty chunk forces a final \r\n after the closing boundary.
    # expo-updates' native parser (UpdatesMultipartStreamReader.swift) requires
    # the exact byte sequence "\r\n--{boundary}--\r\n" to recognize the close
    # delimiter - without this, it never matches and the client hangs waiting
    # for more stream data that never comes ("Could not read multipart remote
    # update response"). This never showed up in our own tests because our test
    # helper hand-parses the same way this encoder writes, so it never validated
    # against the real (stricter) native parser's expectations.
    chunks.append(b"")
    return b"\r\n".join(chunks), f"multipart/mixed; boundary={boundary}"

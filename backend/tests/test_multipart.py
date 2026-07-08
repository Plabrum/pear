from __future__ import annotations

from app.platform.updates.multipart import MultipartPart, encode_multipart_mixed

# expo-updates' native parser (UpdatesMultipartStreamReader.swift) requires these
# exact byte sequences to recognize the opening and closing boundary delimiters -
# not just "reasonably close" multipart formatting. A body missing the trailing
# CRLF after the closing boundary parses fine under a lenient hand-rolled test
# parser but hangs forever against the real client ("Could not read multipart
# remote update response"). These tests check the literal bytes the real parser
# scans for, not a re-implementation of this module's own parsing assumptions.


def test_single_part_matches_native_parser_delimiters() -> None:
    part = MultipartPart(name="directive", body=b'{"type":"noUpdateAvailable"}')
    body, content_type = encode_multipart_mixed([part])
    boundary = content_type.split("boundary=")[1]

    assert body.startswith(f"--{boundary}\r\n".encode())
    assert body.endswith(f"\r\n--{boundary}--\r\n".encode())


def test_multiple_parts_match_native_parser_delimiters() -> None:
    parts = [
        MultipartPart(name="manifest", body=b'{"id":"abc"}'),
        MultipartPart(name="directive", body=b'{"type":"noUpdateAvailable"}'),
    ]
    body, content_type = encode_multipart_mixed(parts)
    boundary = content_type.split("boundary=")[1]

    assert body.startswith(f"--{boundary}\r\n".encode())
    assert body.endswith(f"\r\n--{boundary}--\r\n".encode())
    # Every part after the first must be preceded by "\r\n--{boundary}\r\n"
    # (UpdatesMultipartStreamReader's restDelimiter), not just "--{boundary}\r\n".
    assert f"\r\n--{boundary}\r\n".encode() in body


def test_headers_separated_from_body_by_blank_line() -> None:
    part = MultipartPart(
        name="manifest",
        body=b'{"id":"abc"}',
        extra_headers={"expo-signature": 'sig="xyz", keyid="main"'},
    )
    body, _content_type = encode_multipart_mixed([part])

    assert b'Content-Disposition: form-data; name="manifest"\r\n' in body
    assert b"expo-signature:" in body
    # UpdatesMultipartStreamReader.parseHeadersIfFound scans for "\r\n\r\n" to
    # split headers from body content.
    assert b"\r\n\r\n" in body

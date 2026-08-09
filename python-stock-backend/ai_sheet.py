"""URL content to editable spreadsheet data.

The crawler deliberately accepts only public HTTP(S) endpoints.  It is not a
general purpose proxy: local/private addresses and non-HTML responses are
rejected to keep this endpoint safe to expose to browsers.
"""
import ipaddress
import socket
from html.parser import HTMLParser
from urllib.parse import urlparse

import requests
from flask import Blueprint, jsonify, request


ai_sheet_bp = Blueprint("ai_sheet", __name__, url_prefix="/api/ai-sheet")
MAX_BYTES = 2_000_000
MAX_ROWS = 100
MAX_COLUMNS = 20


def _is_public_url(value):
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return False
    try:
        port = parsed.port
    except ValueError:
        return False
    if parsed.username or parsed.password or (port is not None and port not in (80, 443)):
        return False
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(parsed.hostname, None)}
        return bool(addresses) and all(ipaddress.ip_address(address).is_global for address in addresses)
    except (socket.gaierror, ValueError):
        return False


class _TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables, self._table, self._row = [], None, None
        self._cell, self._cell_tag = None, None
        self.title, self._in_title = "", False
        self.paragraphs, self._paragraph = [], None

    def handle_starttag(self, tag, attrs):
        if tag == "title": self._in_title = True
        if tag == "table":
            self._table = []
        elif tag == "tr" and self._table is not None:
            self._row = []
        elif tag in ("th", "td") and self._row is not None:
            self._cell, self._cell_tag = [], tag
        elif tag == "p":
            self._paragraph = []

    def handle_data(self, data):
        if self._in_title: self.title += data
        if self._cell is not None: self._cell.append(data)
        if self._paragraph is not None: self._paragraph.append(data)

    def handle_endtag(self, tag):
        if tag == "title": self._in_title = False
        elif tag in ("th", "td") and self._cell is not None:
            self._row.append(" ".join("".join(self._cell).split())[:500])
            self._cell, self._cell_tag = None, None
        elif tag == "tr" and self._row is not None:
            if any(self._row): self._table.append(self._row)
            self._row = None
        elif tag == "table" and self._table is not None:
            if self._table: self.tables.append(self._table)
            self._table = None
        elif tag == "p" and self._paragraph is not None:
            text = " ".join("".join(self._paragraph).split())
            if len(text) >= 20: self.paragraphs.append(text[:1000])
            self._paragraph = None


def _to_sheet(parser):
    # Prefer the table with the most populated cells.  A header row becomes
    # spreadsheet columns; otherwise A, B, C ... are generated.
    table = max(parser.tables, key=lambda rows: sum(len(row) for row in rows), default=[])
    if table:
        width = min(MAX_COLUMNS, max(len(row) for row in table))
        first_row = table[0]
        headers = [(first_row[index] if index < len(first_row) and first_row[index] else f"열 {index + 1}")
                   for index in range(width)]
        rows = [[row[index] if index < len(row) else "" for index in range(width)]
                for row in table[1:MAX_ROWS + 1]]
        return headers, rows, "표"
    headers = ["순번", "본문"]
    rows = [[str(index + 1), paragraph] for index, paragraph in enumerate(parser.paragraphs[:MAX_ROWS])]
    return headers, rows, "본문"


@ai_sheet_bp.post("/crawl")
def crawl_to_sheet():
    body = request.get_json(silent=True) or {}
    url = (body.get("url") or "").strip()
    if not _is_public_url(url):
        return jsonify({"message": "공개 HTTP(S) 주소만 입력할 수 있습니다."}), 400
    try:
        with requests.get(url, headers={"User-Agent": "EDUMGT-AISheet/1.0 (+educational)"},
                          timeout=(4, 12), allow_redirects=True, stream=True) as response:
            if not _is_public_url(response.url):
                return jsonify({"message": "안전하지 않은 리디렉션 주소입니다."}), 400
            response.raise_for_status()
            content_type = response.headers.get("Content-Type", "").lower()
            if "html" not in content_type:
                return jsonify({"message": "HTML 웹페이지만 시트로 가져올 수 있습니다."}), 415
            response.raw.decode_content = True
            payload = response.raw.read(MAX_BYTES + 1)
            if len(payload) > MAX_BYTES:
                return jsonify({"message": "페이지가 너무 큽니다. 2MB 이하의 페이지를 사용해주세요."}), 413
            parser = _TableParser()
            parser.feed(payload.decode(response.encoding or "utf-8", errors="replace"))
            columns, rows, source_type = _to_sheet(parser)
            if not rows:
                return jsonify({"message": "가져올 표 또는 본문을 찾지 못했습니다."}), 422
            return jsonify({"title": " ".join(parser.title.split()) or urlparse(response.url).hostname,
                            "sourceUrl": response.url, "sourceType": source_type,
                            "columns": columns, "rows": rows,
                            "notice": "공개 페이지에서 추출한 결과입니다. 숫자와 원문은 저장 전 확인하세요."})
    except requests.RequestException as exc:
        return jsonify({"message": f"페이지를 가져오지 못했습니다: {exc}"}), 502

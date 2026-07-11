"""Локальный приёмник для выгрузок из OLAP census.belstat.gov.by.

Сервер Белстата принимает модифицированные запросы только из браузерного
контекста (комбинация сессии/заголовков, недоступная вне браузера), поэтому
выгрузка выполняется fetch-ами в браузерной вкладке, а результаты
отправляются сюда: POST http://localhost:8765/save?name=<файл>.

Запуск: python -m etl.olap_receiver [--dir data/raw/census_olap]
"""
from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from .common import ROOT


class Handler(BaseHTTPRequestHandler):
    out_dir: Path

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):  # noqa: N802
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_POST(self):  # noqa: N802
        from urllib.parse import parse_qs, urlparse
        q = parse_qs(urlparse(self.path).query)
        name = q.get("name", ["dump"])[0]
        # только безопасные имена файлов
        name = "".join(c for c in name if c.isalnum() or c in "-_.") or "dump"
        size = int(self.headers.get("Content-Length", 0))
        data = self.rfile.read(size)
        try:
            json.loads(data)  # валидация: принимаем только JSON
        except Exception:
            self.send_response(400)
            self._cors()
            self.end_headers()
            self.wfile.write(b"not json")
            return
        dest = self.out_dir / f"{name}.json"
        dest.write_bytes(data)
        print(f"saved {dest} ({size} bytes)")
        self.send_response(200)
        self._cors()
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *a):  # тишина
        pass


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=str(ROOT / "data" / "raw" / "census_olap"))
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()
    Handler.out_dir = Path(args.dir)
    Handler.out_dir.mkdir(parents=True, exist_ok=True)
    print(f"receiver on :{args.port} -> {Handler.out_dir}")
    HTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()

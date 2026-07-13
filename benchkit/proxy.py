from __future__ import annotations
import argparse
import http.client
import json
import ssl
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from .security import safe_headers
from .usage import extract

HOP = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailer", "transfer-encoding", "upgrade"}

class Proxy(BaseHTTPRequestHandler):
    upstream = ""
    outdir = Path("results/proxy")

    def do_GET(self): self.forward()
    def do_POST(self): self.forward()
    def do_PUT(self): self.forward()
    def do_DELETE(self): self.forward()

    def forward(self):
        started = time.monotonic()
        target = urllib.parse.urlparse(self.upstream)
        connection_class = http.client.HTTPSConnection if target.scheme == "https" else http.client.HTTPConnection
        connection = connection_class(target.hostname, target.port, timeout=120, context=ssl.create_default_context() if target.scheme == "https" else None)
        length = int(self.headers.get("content-length", "0") or "0")
        body = self.rfile.read(length) if length else None
        headers = {k: v for k, v in self.headers.items() if k.lower() not in HOP and k.lower() != "host"}
        path = (target.path.rstrip("/") + "/" + self.path.lstrip("/")) or "/"
        if target.query:
            path += "?" + target.query
        connection.request(self.command, path, body=body, headers=headers)
        response = connection.getresponse()
        self.send_response(response.status)
        for key, value in response.getheaders():
            if key.lower() not in HOP:
                self.send_header(key, value)
        self.end_headers()
        captured = bytearray()
        while True:
            chunk = response.read(16384)
            if not chunk:
                break
            if len(captured) < 8 * 1024 * 1024:
                captured.extend(chunk[: 8 * 1024 * 1024 - len(captured)])
            self.wfile.write(chunk)
            self.wfile.flush()
        connection.close()
        parsed = []
        try:
            text = captured.decode("utf-8")
            if "text/event-stream" in (response.getheader("content-type") or ""):
                for line in text.splitlines():
                    if line.startswith("data:") and line[5:].strip() not in {"", "[DONE]"}:
                        parsed.append(json.loads(line[5:].strip()))
            else:
                parsed.append(json.loads(text))
        except (UnicodeDecodeError, json.JSONDecodeError):
            pass
        protocol = "anthropic-messages" if self.path.rstrip("/").endswith("/messages") else ("openai-responses" if self.path.rstrip("/").endswith("/responses") else "openai-compatible")
        event = {
            "method": self.command,
            "path": self.path,
            "request_headers": safe_headers(dict(self.headers)),
            "protocol": protocol,
            "status": response.status,
            "latency_ms": round((time.monotonic() - started) * 1000),
            "usage": extract(parsed),
            "model": next((obj.get("model") for obj in parsed if isinstance(obj, dict) and isinstance(obj.get("model"), str)), None),
        }
        self.outdir.mkdir(parents=True, exist_ok=True)
        with (self.outdir / "events.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event) + "\n")
        events = [json.loads(line) for line in (self.outdir / "events.jsonl").read_text(encoding="utf-8").splitlines() if line]
        aggregate = {key: None for key in ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_tokens")}
        for item in events:
            for key, value in item["usage"].items():
                if isinstance(value, int):
                    aggregate[key] = (aggregate[key] or 0) + value
        (self.outdir / "usage.json").write_text(json.dumps({"requests": len(events), "usage": aggregate, "events": events}, indent=2) + "\n", encoding="utf-8")

    def log_message(self, format, *args):
        return

def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--listen", default="0.0.0.0:8080")
    parser.add_argument("--upstream", required=True)
    parser.add_argument("--outdir", required=True)
    args = parser.parse_args(argv)
    host, port = args.listen.rsplit(":", 1)
    Proxy.upstream = args.upstream
    Proxy.outdir = Path(args.outdir)
    ThreadingHTTPServer((host, int(port)), Proxy).serve_forever()

if __name__ == "__main__":
    main()

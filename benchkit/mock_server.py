from __future__ import annotations
import argparse
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from .security import safe_headers

MODEL = "gpt-5.6-sol"
USAGE = {
    "input_tokens": 41,
    "input_tokens_details": {"cached_tokens": 7},
    "output_tokens": 5,
    "output_tokens_details": {"reasoning_tokens": 2},
}

class Handler(BaseHTTPRequestHandler):
    events: Path | None = None

    def _record(self, body: dict | None = None):
        if not self.events:
            return
        self.events.parent.mkdir(parents=True, exist_ok=True)
        event = {"method": self.command, "path": self.path, "headers": safe_headers(dict(self.headers)), "body_keys": sorted(body) if isinstance(body, dict) else []}
        with self.events.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event) + "\n")

    def _json(self, status: int, payload: dict):
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _sse(self, events: list[tuple[str, dict]]):
        self.send_response(200)
        self.send_header("content-type", "text/event-stream")
        self.send_header("cache-control", "no-cache")
        self.end_headers()
        for name, payload in events:
            self.wfile.write(f"event: {name}\ndata: {json.dumps(payload)}\n\n".encode())
            self.wfile.flush()

    def do_GET(self):
        self._record()
        if self.path.rstrip("/").endswith("/models"):
            self._json(200, {"object": "list", "data": [{"id": MODEL, "object": "model", "owned_by": "benchmark"}]})
        else:
            self._json(200, {"status": "ok"})

    def do_POST(self):
        length = int(self.headers.get("content-length", "0") or "0")
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            body = {}
        self._record(body)
        if self.path.rstrip("/").endswith("/responses"):
            self._responses(body)
        elif self.path.rstrip("/").endswith("/messages"):
            self._anthropic(body)
        else:
            self._chat(body)

    def _responses(self, body: dict):
        response = {
            "id": "resp_benchmark",
            "object": "response",
            "created_at": int(time.time()),
            "status": "completed",
            "model": MODEL,
            "output": [{"id": "msg_benchmark", "type": "message", "status": "completed", "role": "assistant", "content": [{"type": "output_text", "text": "benchmark-ok", "annotations": []}]}],
            "usage": USAGE,
        }
        if body.get("stream"):
            self._sse([
                ("response.created", {"type": "response.created", "response": {**response, "status": "in_progress", "output": []}}),
                ("response.output_text.delta", {"type": "response.output_text.delta", "item_id": "msg_benchmark", "output_index": 0, "content_index": 0, "delta": "benchmark-ok"}),
                ("response.completed", {"type": "response.completed", "response": response}),
            ])
        else:
            self._json(200, response)

    def _chat(self, body: dict):
        if body.get("stream"):
            self._sse([
                ("message", {"id": "chat_benchmark", "object": "chat.completion.chunk", "model": MODEL, "choices": [{"index": 0, "delta": {"role": "assistant", "content": "benchmark-ok"}, "finish_reason": None}]}),
                ("message", {"id": "chat_benchmark", "object": "chat.completion.chunk", "model": MODEL, "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}], "usage": USAGE}),
            ])
            self.wfile.write(b"data: [DONE]\n\n")
        else:
            self._json(200, {"id": "chat_benchmark", "object": "chat.completion", "model": MODEL, "choices": [{"index": 0, "message": {"role": "assistant", "content": "benchmark-ok"}, "finish_reason": "stop"}], "usage": USAGE})

    def _anthropic(self, body: dict):
        usage = {"input_tokens": 41, "cache_read_input_tokens": 7, "output_tokens": 5}
        if body.get("stream"):
            self._sse([
                ("message_start", {"type": "message_start", "message": {"id": "msg_benchmark", "type": "message", "role": "assistant", "model": MODEL, "content": [], "stop_reason": None, "usage": {"input_tokens": 41, "cache_read_input_tokens": 7, "output_tokens": 0}}}),
                ("content_block_start", {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}}),
                ("content_block_delta", {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "benchmark-ok"}}),
                ("content_block_stop", {"type": "content_block_stop", "index": 0}),
                ("message_delta", {"type": "message_delta", "delta": {"stop_reason": "end_turn", "stop_sequence": None}, "usage": usage}),
                ("message_stop", {"type": "message_stop"}),
            ])
        else:
            self._json(200, {"id": "msg_benchmark", "type": "message", "role": "assistant", "model": MODEL, "content": [{"type": "text", "text": "benchmark-ok"}], "stop_reason": "end_turn", "usage": usage})

    def log_message(self, format, *args):
        return

def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--listen", default="0.0.0.0:8081")
    parser.add_argument("--events")
    args = parser.parse_args(argv)
    host, port = args.listen.rsplit(":", 1)
    Handler.events = Path(args.events) if args.events else None
    ThreadingHTTPServer((host, int(port)), Handler).serve_forever()

if __name__ == "__main__":
    main()

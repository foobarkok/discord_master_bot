import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer


class _HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        pass


def start_health_check_server(default_port: int = 8080) -> None:
    port = int(os.environ.get("PORT", default_port))

    def _run():
        server = HTTPServer(("0.0.0.0", port), _HealthCheckHandler)
        server.serve_forever()

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

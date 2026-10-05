import functools
import http.server
import os
import webbrowser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = int(os.environ.get("SWAGGER_PORT", "8200"))

handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=os.path.join(ROOT, "swagger"))
with http.server.ThreadingHTTPServer(("127.0.0.1", PORT), handler) as server:
    url = f"http://127.0.0.1:{PORT}/"
    print(f"Swagger UI at {url} (Ctrl+C to stop)")
    webbrowser.open(url)
    server.serve_forever()

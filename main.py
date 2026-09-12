import json
import mimetypes
import socket
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HTTP_HOST = "localhost"
HTTP_PORT = 3000

SOCKET_HOST = "localhost"
SOCKET_PORT = 5000

BASE_DIR = Path(__file__).parent
STORAGE_DIR = BASE_DIR / "storage"
STORAGE_FILE = STORAGE_DIR / "data.json"


def socket_server():
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((SOCKET_HOST, SOCKET_PORT))

    print(f"Socket server started on {SOCKET_HOST}:{SOCKET_PORT}")

    while True:
        data, address = sock.recvfrom(4096)

        try:
            # Перетворюємо байти у словник
            message = json.loads(data.decode("utf-8"))

            # Читаємо існуючі дані
            messages = {}

            if STORAGE_FILE.exists():
                try:
                    with open(STORAGE_FILE, "r", encoding="utf-8") as file:
                        messages = json.load(file)
                except json.JSONDecodeError:
                    messages = {}

            # Додаємо нове повідомлення
            timestamp = str(datetime.now())
            messages[timestamp] = message

            # Зберігаємо дані у data.json
            with open(STORAGE_FILE, "w", encoding="utf-8") as file:
                json.dump(
                    messages,
                    file,
                    indent=2,
                    ensure_ascii=False
                )

            print(f"[{timestamp}] Message saved: {message}")

        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            print(f"Error processing socket message: {error}")


class HttpHandler(BaseHTTPRequestHandler):

    def send_file(self, file_path, status_code=200):
        try:
            with open(file_path, "rb") as file:
                content = file.read()

            # Визначаємо MIME-тип файлу
            mimetype, _ = mimetypes.guess_type(file_path)

            if not mimetype:
                mimetype = "text/plain"

            self.send_response(status_code)
            self.send_header("Content-Type", mimetype)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        except FileNotFoundError:
            self.send_error_page()

    def send_error_page(self):
        error_file = BASE_DIR / "error.html"

        if error_file.exists():
            self.send_file(error_file, status_code=404)
        else:
            self.send_error(404, "Page Not Found")

    def do_GET(self):
        # Беремо тільки шлях без query-параметрів
        url_path = Path(urlparse(self.path).path.lstrip("/"))

        if self.path == "/" or url_path == Path("index.html"):
            self.send_file(BASE_DIR / "index.html")

        elif url_path == Path("message.html"):
            self.send_file(BASE_DIR / "message.html")

        else:
            # Обробка статичних файлів:
            # style.css, logo.png тощо
            file_to_send = BASE_DIR / url_path

            if file_to_send.exists() and file_to_send.is_file():
                self.send_file(file_to_send)
            else:
                self.send_error_page()

    def do_POST(self):
        # Обробка форми
        if urlparse(self.path).path == "/message":
            content_length = int(
                self.headers.get("Content-Length", 0)
            )

            body = self.rfile.read(content_length).decode("utf-8")

            # Отримуємо дані з HTML-форми
            form_data = parse_qs(body)

            username = form_data.get("username", [""])[0]
            message = form_data.get("message", [""])[0]

            data = {
                "username": username,
                "message": message
            }

            # Перетворюємо словник у JSON
            json_data = json.dumps(
                data,
                ensure_ascii=False
            )

            # Відправляємо дані Socket UDP серверу
            sock = socket.socket(
                socket.AF_INET,
                socket.SOCK_DGRAM
            )

            sock.sendto(
                json_data.encode("utf-8"),
                (SOCKET_HOST, SOCKET_PORT)
            )

            sock.close()

            # Перенаправлення на message.html
            self.send_response(302)
            self.send_header("Location", "/message.html")
            self.end_headers()

        else:
            self.send_error_page()


def http_server():
    server = HTTPServer(
        (HTTP_HOST, HTTP_PORT),
        HttpHandler
    )

    print(
        f"HTTP server started on "
        f"{HTTP_HOST}:{HTTP_PORT}"
    )

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()

if __name__ == "__main__":
    socket_thread = threading.Thread(
        target=socket_server,
        daemon=True
    )

    http_thread = threading.Thread(
        target=http_server,
        daemon=True
    )

    socket_thread.start()
    http_thread.start()

    print("Both servers are running successfully.")
    print(
        f"Open http://{HTTP_HOST}:{HTTP_PORT} "
        "in your browser."
    )

    try:
        socket_thread.join()
        http_thread.join()

    except KeyboardInterrupt:
        print("\nStopping servers...")
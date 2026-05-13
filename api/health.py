from http.server import BaseHTTPRequestHandler

from logo_bot.webhook import WebhookHandler


class handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        WebhookHandler.do_GET(self)

    def do_POST(self) -> None:
        WebhookHandler.do_POST(self)

from asyncio import Lock
import json
import logging
from logging import getLogger
import os
import re
from time import monotonic_ns
from typing import *

from aiohttp import ClientSession, web
from aiohttp.web import Application, Request, Response

ECS_LOGGING_ENV = "ECS_LOGGING"

logger = getLogger(__name__)


# https://datatracker.ietf.org/doc/html/rfc6750#section-2.1
BEARER_TOKEN_RE = re.compile("^Bearer +([a-zA-Z0-9-._~+\/]+=*)$")


class Server:
    def __init__(
        self,
        home_server_url: str,
        access_token: str,
        default_room: str,
        relay_token: str | None,
        app: Application,
    ):
        self.home_server_url = home_server_url
        self.access_token = access_token
        self.default_room = default_room

        self.relay_token = relay_token
        if relay_token:
            logger.info("Relay authenticated with token.")
        else:
            logger.warning(
                "You did not specify a relay_token, anyone with network access can "
                "send messages!"
            )

        self.app = app

        self._msg_id_lock = Lock()
        self._last_time: int = 0
        self._last_counter: int = 1

        app.add_routes([web.put("/alert", self.handle_alert)])

    async def get_message_id(self):
        async with self._msg_id_lock:
            now = monotonic_ns()
            if now == self._last_time:
                self._last_counter += 1
            else:
                self._last_counter = 1
            return f"{now}{self._last_counter}"

    def parse_alert(self, alert: Dict[str, Any]) -> str:
        # TODO: Parse ROOM from message?
        labels = alert["labels"]
        name = labels.pop("alertname")
        as_string = f"{name} is {alert['status']}:\n  "
        as_string += "\n  ".join(f"{k}: {v}" for k, v in labels.items())
        return as_string

    def make_message(self, webhook_data: Dict[str, Any]) -> str:
        try:
            alerts = webhook_data["alerts"]
            msg = ""
            if len(alerts) > 1:
                msg = f"{len(alerts)} alerts are {webhook_data['status']}!\n"

            msg += "\n".join(self.parse_alert(al) for al in alerts)

            return msg
        except KeyError:
            return (
                "Alerts failed to parse in relay!\n"
                f"{json.dumps(webhook_data, indent=2)}"
            )

    def check_auth(self, request: Request) -> bool:
        token: str | None = None
        header = request.headers.get("Authorization")
        if header and (match := BEARER_TOKEN_RE.fullmatch(header)):
            token = match.group(1)

        return token == self.relay_token

    async def handle_alert(self, request: Request) -> Response:

        if self.relay_token and not self.check_auth(request):
            logger.warning("Authentication failed")
            return Response(text="Authentication failed", status=401)

        body = await request.json()
        message_text = self.make_message(body)
        try:
            await self.send_message(message_text)
        except:
            logger.exception("Failed to send message to matrix")
            return Response(text="Error", status=500)

        return Response(text="Ok")

    async def send_message(self, message: str) -> None:
        mid = await self.get_message_id()

        async with ClientSession() as http:
            res = await http.put(
                f"{self.home_server_url}/_matrix/client/v3/rooms/{self.default_room}"
                f"/send/m.room.message/{mid}",
                headers={"Authorization": f"Bearer {self.access_token}"},
                json={
                    "msgtype": "m.text",
                    "body": message,
                },
            )
            res.raise_for_status()


class ConfigurationMissing(Exception):
    ...


_MATRIX_SERVER_ARGS = ["home_server_url", "access_token", "default_room"]

if __name__ == "__main__":
    from argparse import ArgumentParser

    parser = ArgumentParser()
    for arg in _MATRIX_SERVER_ARGS:
        parser.add_argument(f"--{arg}", type=str, default=None)
    parser.add_argument("--relay_token", type=str, default=None)
    parser.add_argument("--host", type=str)
    parser.add_argument("--port", type=int)

    args = parser.parse_args()

    from dotenv import load_dotenv

    load_dotenv()

    # Optionally set up ecs logging
    if (ecs_val := os.environ.get(ECS_LOGGING_ENV, "false")).lower() == "true":
        try:
            import ecs_logging
            import sys

            handler = logging.StreamHandler(stream=sys.stdout)
            handler.setFormatter(ecs_logging.StdlibFormatter())

            root_logger = getLogger()
            root_logger.setLevel(logging.INFO)
            root_logger.addHandler(handler)

        except ImportError:
            logger.critical(
                f"Tried to set up ECS logging, because the {ECS_LOGGING_ENV} is {ecs_val}, "
                "but importing ecs_logging failed. Did you install "
                "grafana_matrix_alerting[ecs]?"
            )
            raise

    # Parse args and env vars for the server
    instance_args = {}
    for arg in _MATRIX_SERVER_ARGS:
        if from_args := getattr(args, arg):
            instance_args[arg] = from_args
        else:
            if not (from_env := os.environ.get(f"MATRIX_{arg.upper()}")):
                raise ConfigurationMissing(
                    f"No {arg} provided. You must pass --{arg} or set "
                    f"MATRIX_{arg.upper()} in the env vars."
                )
            instance_args[arg] = from_env

    relay_token = args.relay_token or os.environ.get("RELAY_TOKEN")

    app = Application()
    Server(
        **instance_args,
        relay_token=relay_token,
        app=app,
    )

    host = args.host or os.environ.get("RELAY_HOST", "127.0.0.1")
    port = args.port or int(os.environ.get("RELAY_PORT", 9024))
    logger.info(f"Relay will listen on http://{host}:{port}")
    web.run_app(app, host=host, port=port)

# Yet another Grafana ➡ Matrix alert relay

This repo contains a very small webserver (called relay) that accepts webhook requests
from Grafana and forwards (relays) the alerts to a matrix server.

Key features:

- What you are reading right now: _Documentation_ 🥳
- `Dockerfile` to build a container image 🐳
- `docker-compose.yml` file to help you run the container
- Optional: Authentication on the relay
- Optional: Logging with Elastic Common Schema

## Why?

Grafana alerting offers no integration with the matrix messaging protocol.
There are several open issues and declined merge requests on the matter.
It appears that Grafana wants future alert integrations to be plugins, but at the same
time, the plugin interface does not support alerting yet. 🤷

## Prerequisites

You need:

- The URL of your matrix homeserver
- A matrix token. I strongly suggest you use an account separate from your "normal" one
- A matrix room **without** E2EE, with the "alerting" user in it
- The ID of that room
- Your grafana needs to be able to make http requests to the relay

### What is my matrix homeserver url?

This is not as obvious as it sounds! You might think that if your username is
`@foobar:example.com`, your home server must be `example.com`, but that is not
necessarily the case. To find your homeserver address, you can go to:
`example.com/.well-known/matrix/client` and check the `"m.homeserver"` property in
the returned json.

### How do I create a room without E2EE?

That depends on your client, in Element, you need to un-toggle a switch when creating
the room. Note that you **can not** downgrade an existing, encrypted room.

### How do I get the room ID?

Again: Depends on your client. In Element: `Open room` -> `Dropdown at the Top` ->
`Settings` -> `Advanced`. They seem to always start with `!` and end with
`:example.com`.

### Why should I use a separate user?

As of writing there is no way to "restrict" the capabilities of an access token [1], so
this token can be used to perform any action against the matrix API. If someone manages
to steal the token, he can't read E2EE messages that you sent with other devices, but
there are still enough other opportunities to cause damage.

### Where do I get an access token?

You can try to obtain a new one by doing a login procedure against the matrix API,
You _might_ be able to get a token with the curl command below **BUT** your home
server might have disabled password login. I suggest to first it with an incorrect
password, so you avoid unnecessarily exposing it.

```sh
curl --request POST \
--url https://example.homeserver/_matrix/client/r0/login \
--header 'Content-Type: application/json' \
--data '{
"type": "m.login.password",
"user": "my.username",
"password": "totallymypassword",
"initial_device_display_name": "Grafana Alerts"
}'
```

If you get an error message: `"Password login has been disabled."` you can either:
Figure out what authentication your homeserver allows and try to go through the entire
flow (the correct way).  
Or you take the token from an existing session with your client (the layz way).
Notice that if you choose the lazy route, logging out with that client will also
disable the relay. What's worse, if your client automatically refreshes tokens, it
effectively "kicks" the relay out. That being said, in element you can click:  
`Your profile` -> `All Settings` -> `Help & About` -> `scroll down` -> `Access token`

[1] https://matrix.org/blog/2023/09/better-auth/

## Installation

If you want to run the python relay directly, install the dependencies using `poetry`.

```sh
cd relay
poetry install
```

Activate the venv with `poetry shell`

## Configuration

### The relay

All config options can be set via:

- Command line args: Run `python -m grafana_matrix_alerting --help`
- Environment variables (Check the file `.env.example`)
- Directly in a file `.env` (Just copy .env.example and fill in the variables!)

`RELAY_TOKEN`/`relay_token` **can** be set to force requests to the relay to
authenticate via the `Authorization: Bearer <relay_token>` header.

`RELAY_HOST`/`host` and `RELAY_PORT`/`port` are the host & port the relay server
will run on.

`ECS_LOGGING` turns on elastic common schema logging via `ecs-logging`.

The remaining options should be self-explanatory.

### Configuring Docker

Copy `docker/.env.example` to `docker/.env` and fill in the values.
If you run grafana in a container as well, uncomment the network-related options and
place the relay on the same network as grafana.

### Grafana contact point

In Grafana configure the contact point like so:

- **Integration:** Webhook
- **URL:** http://hostname-of-the-relay:9042/alert
- **HTTP Method:** PUT
- **Authorization Header - Credentials:** `relay_token` (optional)


# AI FAQ Assistant

A lightweight web application that answers customer questions using an LLM via
[OpenRouter](https://openrouter.ai), grounded strictly in company knowledge stored in local
Markdown/text files.

This is **not** a RAG project — there are no vector databases, embeddings, or external
retrieval frameworks. The entire knowledge base is loaded into memory once at startup and
injected directly into the prompt.

## Project Structure

```
project/
├── app/
│   ├── main.py              # FastAPI app, startup hook, error handlers
│   ├── routes.py            # HTTP routes: /, /health, /chat
│   ├── ai.py                # All LLM API calls live here (answer())
│   ├── knowledge_loader.py  # Loads & caches knowledge/ files in memory
│   ├── prompts.py           # System prompt template
│   ├── config.py            # Settings loaded from .env
│   ├── rate_limit.py        # Shared slowapi Limiter instance
│   ├── email_sender.py      # Contact-form email (SMTP)
│   └── chat_log.py          # Stores chat exchanges in a SQLite file
├── knowledge/                # Company knowledge (.md / .txt files)
│   ├── company.md
│   ├── faq.md
│   ├── services.md
│   └── contacts.md
├── templates/
│   ├── index.html           # Standalone chat page
│   └── widget.html          # Embeddable widget (launcher + chat panel)
├── static/
│   ├── style.css
│   ├── app.js                # Chat logic, shared by index.html and widget.html
│   ├── widget.css            # Layout for the embedded widget
│   ├── widget-toggle.js      # Open/close + postMessage to the parent page
│   └── widget.js             # Loader script that other websites embed
├── .env                      # Your local secrets (not committed)
├── .env.example               # Template for .env
├── requirements.txt
├── Dockerfile
├── docker-compose.yml         # Local dev (app only, published on :8000)
├── docker-compose.prod.yml   # Production (app + Caddy reverse proxy w/ HTTPS)
├── Caddyfile                  # Reverse proxy config (domain + upstream)
└── README.md
```

## How It Works

1. On startup, every `.md` and `.txt` file in `knowledge/` is read once and merged into a
   single in-memory string. It is never re-read unless the server restarts.
2. Every request to `/chat` builds a prompt made of: system instructions + company
   knowledge + conversation history + the current user message.
3. The system prompt instructs the model to answer only from the provided knowledge, never
   invent facts, admit when it doesn't know, stay concise, and reply in the user's language.
4. The browser keeps conversation history in `sessionStorage` and sends it with every
   request so the assistant has context. "Clear Chat" only clears this local history.

## Running Locally

1. Copy the example environment file and add your LLM API key:

   ```
   cp .env.example .env
   ```

   Edit `.env` and set `LLM_API_KEY`.

2. Install dependencies:

   ```
   pip install -r requirements.txt
   ```

3. Start the server:

   ```
   uvicorn app.main:app --reload
   ```

4. Open [http://localhost:8000](http://localhost:8000) in your browser.

## Running With Docker

```
docker compose up --build
```

The app will be available at [http://localhost:8000](http://localhost:8000). Make sure a
`.env` file with your `LLM_API_KEY` exists in the project root before starting — it is
picked up automatically via `env_file` in `docker-compose.yml`.

## Deploying to a Public Server

`docker-compose.prod.yml` adds a [Caddy](https://caddyserver.com) reverse proxy in front of
the app, which automatically obtains and renews a Let's Encrypt HTTPS certificate — no manual
certbot/nginx setup needed. The domain is hardcoded in `Caddyfile` (currently
`simas.private-search.online`; change it there if the domain changes).

1. **Point DNS** — at your DNS provider for the domain, add an `A` record for the subdomain
   (e.g. `simas`) pointing to the server's public IP.
2. **Open firewall ports 80 and 443** (and 22 for SSH) on the server — e.g. in the Hetzner
   Cloud Firewall settings. Caddy needs 80/443 reachable from the internet to issue the
   certificate and serve traffic.
3. **On the server**: install Docker + the Docker Compose plugin, then clone this repo.
4. **Create `.env` on the server** — it's gitignored, so it won't come from `git clone`.
   Copy your local `.env` (or `.env.example`) and fill in real values. Critically, set
   `WIDGET_FRAME_ANCESTORS` to include every site that will actually embed the widget
   (your test page's origin, eventual VU domains, etc.) — see the comment in `.env.example`.
5. **Start the stack**:
   ```
   docker compose -f docker-compose.prod.yml up -d --build
   ```
6. Visit `https://simas.private-search.online/widget` to confirm it's live, then embed it
   anywhere with:
   ```html
   <script src="https://simas.private-search.online/static/widget.js" async></script>
   ```

To redeploy after a code change: `git pull` then re-run step 5 (`docker compose -f
docker-compose.prod.yml up -d --build`).

## Configuration (`.env`)

| Variable          | Description                                                        | Default                          |
|--------------------|---------------------------------------------------------------------|-----------------------------------|
| `LLM_API_KEY`      | Your OpenRouter API key                                              | (none)                            |
| `LLM_BASE_URL`     | OpenRouter API base URL                                              | `https://openrouter.ai/api/v1`    |
| `MODEL`            | Chat model to use (OpenRouter `provider/model` slug)                | `google/gemini-3.1-flash-lite`    |
| `TEMPERATURE`      | Sampling temperature                                                 | `0.2`                             |
| `MAX_TOKENS`       | Max tokens in the generated reply                                    | `1000`                            |
| `REQUEST_TIMEOUT`  | Timeout (seconds) for LLM API requests                               | `30`                              |
| `WIDGET_FRAME_ANCESTORS` | CSP `frame-ancestors` source list — which origins may `<iframe>` `/widget` | `'self'` |
| `CHAT_RATE_LIMIT` | Per-IP limit on `POST /chat` (slowapi syntax, e.g. `10/minute`) | `10/minute` |
| `CONTACT_TO_EMAIL` | Where "Contact staff" messages are delivered | (none) |
| `CONTACT_FROM_EMAIL` | From address for those emails (use one the SMTP server may send for) | (none) |
| `CONTACT_RATE_LIMIT` | Per-IP limit on `POST /contact` | `5/hour` |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USERNAME` / `SMTP_PASSWORD` / `SMTP_USE_TLS` | SMTP relay used to send the contact emails | `-` / `587` / `-` / `-` / `true` |
| `CHAT_LOG_DB` | SQLite filename for chat logs (under `data/`) | `chat_logs.db` |
| `CHAT_LOG_RETENTION_DAYS` | Auto-delete logs older than this at startup (`0` = keep forever) | `90` |

## Contact Form (email to staff)

The chat header has a **"Contact staff"** button that opens a form where a visitor can send
their email + message, with the chat transcript attached, to library staff. The message is
sent by `app/email_sender.py` through a plain **SMTP relay** — a mailbox provider's SMTP now,
or an institutional `@vu.lt` mail server in production. Point it at a different server by
changing the `SMTP_*` variables; no code change is needed.

Set `CONTACT_TO_EMAIL` (staff inbox), `CONTACT_FROM_EMAIL` (an address the SMTP server is
allowed to send for — usually the mailbox's own domain), and the `SMTP_*` connection details
(`SMTP_USERNAME` is normally the full email address). If email isn't configured, the
button/form still render but sending returns a friendly error. The endpoint is rate-limited
(`CONTACT_RATE_LIMIT`) and requires an explicit consent checkbox before it forwards anything.

## Chat Logs (SQLite)

Every successful `POST /chat` exchange (user message + assistant reply, a per-browser-session
id, and a UTC timestamp) is stored in a **SQLite** file at `data/chat_logs.db` by
`app/chat_log.py`. SQLite needs no separate database server — it is just a file — but the
`data/` directory is mounted as a Docker volume so the database survives container rebuilds.
Logging never blocks or breaks a chat: failures are only logged.

Logs older than `CHAT_LOG_RETENTION_DAYS` (default 90) are pruned automatically at startup —
keep this in mind for GDPR/data-retention purposes. Set it to `0` to keep logs indefinitely.

Read the logs with any SQLite tool, e.g. inside the running container:

```
docker compose exec faq-assistant \
  python -c "import sqlite3; [print(r) for r in sqlite3.connect('/app/data/chat_logs.db').execute('SELECT created_at, user_message, assistant_reply FROM chat_logs ORDER BY id DESC LIMIT 20')]"
```

or copy `data/chat_logs.db` off the server and open it in a GUI like DB Browser for SQLite.

## Embedding on Other Websites (e.g. VU Faculty Pages)

The assistant can be dropped into any Vilnius University webpage as a floating chat widget
that looks identical everywhere, since it always renders inside an isolated `<iframe>`
served from this app — the host page's CSS never touches it.

1. Set `WIDGET_FRAME_ANCESTORS` in `.env` to the domains allowed to embed it, e.g.:

   ```
   WIDGET_FRAME_ANCESTORS='self' https://*.vu.lt https://vu.lt
   ```

2. On the target website, add one line before `</body>`:

   ```html
   <script src="https://YOUR-DOMAIN/static/widget.js" async></script>
   ```

That's it — the script injects a small floating launcher button in the bottom-right corner;
clicking it expands into the full chat panel (full-screen on mobile). No other CSS or markup
is required on the host page, and no CORS setup is needed since the widget's chat requests go
to `/chat` on this same server, from inside the iframe.

## Updating the Knowledge Base

Edit or add `.md`/`.txt` files inside `knowledge/`, then restart the server (or container)
for the changes to take effect. Files are only read at startup.

## API Reference

### `GET /`
Returns the standalone chat HTML page.

### `GET /widget`
Returns the embeddable widget (launcher button + chat panel), meant to be loaded inside an
`<iframe>` by `static/widget.js`. Sends a `Content-Security-Policy: frame-ancestors ...`
header controlled by `WIDGET_FRAME_ANCESTORS`.

### `GET /health`
```json
{ "status": "ok" }
```

### `POST /chat`

Request:
```json
{
  "message": "What are your office hours?",
  "history": [
    { "role": "user", "content": "Hi" },
    { "role": "assistant", "content": "Hello! How can I help?" }
  ]
}
```

Response:
```json
{ "reply": "Our office hours are Monday to Friday, 09:00-18:00 EET." }
```

Errors are returned as JSON with an `error` field and an appropriate HTTP status code
(`422` for invalid input, `429` if the caller's IP exceeds `CHAT_RATE_LIMIT`, `500` for
configuration/unexpected errors, `502` for upstream LLM API failures).

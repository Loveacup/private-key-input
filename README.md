# Private Key Input

A temporary HTML input page for agent workflows. Your local handler uses the value; the agent receives only an outcome.

[简体中文](README.zh-CN.md) · [Agent instructions](SKILL.md) · [Implementation](scripts/private_input.py)

## Why this exists

When an agent needs a credential, pasting it into chat puts it into conversation history and potentially model context. This skill provides a smaller alternative: a short-lived page and a task-specific Python callback. No daemon, database, plugin, or credential platform is required.

```text
User -> temporary page -> local callback -> authorized destination
                              |
                         outcome only -> agent continues
```

This is not an OS sandbox or a password vault. The handler and destination necessarily receive plaintext. The workflow keeps that value out of agent-visible output only if the task wrapper also handles it correctly.

## Install as a skill

Requires Python 3.9+ and a client supporting `SKILL.md` skills. No third-party Python packages are needed. Python execution has been exercised on macOS and Windows; client-specific discovery must be verified separately.

Clone this repository into your client's skill directory, or link a shared copy there. For example, with the default Hermes profile:

```bash
git clone https://github.com/Loveacup/private-key-input.git ~/.hermes/skills/private-key-input
python3 -B -m unittest discover -s ~/.hermes/skills/private-key-input/scripts -p 'test_*.py'
```

The example requires an absent target directory. For other clients, use their actual supported skill location rather than assuming Hermes paths. Installation does not start a listener, store credentials, or change client settings.

Ask your agent:

> Use private-key-input for the credential required by this task. Resolve the destination first, provide a temporary page, keep the value out of chat and tool output, and continue automatically after submission using an existing host mechanism. Do not add a callback service or store the secret somewhere new without authorization.

## First run: safe smoke test

From the repository root:

```bash
python3 -B -m unittest discover -s scripts -p 'test_*.py'
python3 -B examples/discard_demo.py
```

On Windows use `py -B` if `python3` is unavailable. The demo prints a loopback URL and waits for up to ten minutes. Open it in a browser on that machine and enter **test text only**. The callback discards the value; the final output is `Outcome: submitted`. No real credential is needed or appropriate for this demo.

The page is currently in Simplified Chinese. It includes standard password-manager hints, not a tested 1Password integration.

## Use in an authorized task

Import `InputServer` or `serve` from `scripts/private_input.py`. Supply a callback that uses the credential directly for the already-authorized destination and returns `None`. Do not return or print the value, request bodies, headers, response bodies, or raw exception details. Use timeouts and reject redirects for credential-bearing requests.

`serve(callback, purpose, **options)` prints the page URL, waits, then prints its outcome. `InputServer(callback, purpose, **options)` exposes `url` and `run()` for hosts that need to publish the link separately.

### Link delivery and automatic continuation

- A human must receive the URL **before** the waiting call blocks. A terminal can display flushed output; an agent tool may buffer it until the command exits. Verify the actual host behavior first.
- For buffered tools, start the task-owned temporary process, obtain and deliver its URL, then wait through an existing host mechanism. Do not add a new service merely to resume the task.
- Hermes can reuse its existing background-process completion notification. OMP short synchronous calls have been exercised with a delayed synthetic client; this does **not** prove human link delivery or long waits.
- Return only a nonsecret outcome to the original conversation. Do not require a separate “done” message when native continuation works, and do not redirect results to a different conversation if the origin closes.

### Options and outcomes

- Defaults: `host="127.0.0.1"`, `port=0` (random available port), `ttl=600` seconds.
- Optional TLS: pass a configured `ssl.SSLContext` as `tls_context`, and a matching bare HTTPS `public_origin`.
- LAN: specify the reachable `public_origin`. Without TLS, `allow_plain_lan=True` requires explicit informed consent: HTTP is plaintext, including on a private network. Loopback URLs do not work from a phone.
- Lifecycle: one accepted submission ends the listener. Outcomes are `submitted`, `expired`, or `handler_failed`; a failed handler may have partially completed its operation, so inspect destination status before retrying.

The helper validates the route, Host, Origin, and submission token, disables request access logging, and sends no-store headers. These measures are not a security audit or a guarantee against a compromised host. It does not guarantee memory zeroization, enforce callback deadlines, or replace protected browser-vault login flows.

## Verification scope

The six bundled tests cover normal submission, one-use closure, expiration, wrong origin/token/route, explicit LAN opt-in, and handler failure. Cross-device OMP experiments also exercised short synchronous continuation on macOS and Windows with independent loopback HTTP clients, followed by same-conversation report writing. Those host experiments are not reproduced by the bundled unit suite.

Not established: browser JavaScript/rendering end-to-end, human-facing URL delivery in each CLI, password-manager filling, real downstream authentication, LAN/TLS integration, long waits, background OMP wake-up, or recovery after session replacement. Windows closed-port probes must distinguish timeout/10035 from explicit refusal/10061; a one-second timeout was insufficient in the observed environment.

## Project layout

- `SKILL.md`: portable agent workflow and boundaries.
- `scripts/private_input.py`: Python standard-library HTTP helper.
- `scripts/test_private_input.py`: six unit tests.
- `examples/discard_demo.py`: runnable, test-text-only browser demo.

## License

[MIT](LICENSE).

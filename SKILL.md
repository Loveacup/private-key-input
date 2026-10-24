---
name: private-key-input
description: Use when safely entering a secret outside chat.
version: 1.0.1
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [credentials, private-input, html]
    related_skills: []
---

# Private Key Input

## When to Use

Use after a task needs a credential or secret that the user should not send through chat. Do not trigger for ordinary forms, generated TOTP codes, or browser logins that the host credential vault already handles.

Make credential entry fast from terminal-based agents or Telegram: provide a temporary HTML form, let a local handler consume the secret, and report only a nonsecret outcome. Prefer this lightweight, extensible workflow over a new credential platform.

## Continue without a second user message

After submission, continue the original authorized task without asking the user to say "done". Reuse the host's existing background-process completion notification when supported, as observed in the current Hermes Telegram test. Emit only a nonsecret outcome; never include the entered value. No call-cli worker, new callback service or custom session injection is needed for this path.

Other CLI hosts may instead support keeping the original tool call pending and returning its result after submission; verify how the user receives the page link and how the caller resumes before claiming support. Do not assume Hermes notifications exist on other hosts. A closed or replaced origin does not authorize continuation in a different conversation. Keep automatic continuation within the original task and authorization.

## Use the smallest complete path

Resolve the purpose, target service and intended storage from the current task. If these are already clear, do not ask again. If they are missing, ask only for the missing destination/purpose; never open a generic secret collection page with nowhere authorized to send it.

Use the bundled `scripts/private_input.py` as an importable standard-library helper. A short task wrapper supplies `on_submit(secret)` and calls `serve(...)`. The callback uses the key directly for the authorized operation or writes it through the destination's existing credential API. Return `None`; never return or print the secret, request headers, response bodies or exception details. Use explicit network timeouts and reject redirects when sending credentials. Do not request arbitrary scripts or destinations from the browser.

```python
# Load from the resolved skill directory, not a guessed installation path.
from private_input import serve

# Implement this handler for the already authorized destination.
def accept(secret):
    destination.save(secret)

serve(accept, purpose="Save the configured service API key")
```

- Terminal on the host: use the printed loopback URL in a normal browser. A hidden local terminal prompt is an alternative when a browser is inconvenient.
- Telegram: send a clickable URL, not an HTML attachment that has no live receiver. Phone access needs a verified reachable LAN address and an appropriate transport.
- Default to loopback. LAN use should reuse existing trusted HTTPS where available; otherwise explain that HTTP is plaintext and obtain explicit consent before using `allow_plain_lan=True`. Do not silently claim private-network HTTP is encrypted or secure. TLS is supported by passing a configured `ssl.SSLContext` and the matching `public_origin`.
- The helper exposes an unguessable page route, validates Host/Origin/submission token, avoids browser storage and access logs, and expires after 10 minutes by default. One successful submission closes the server. A failed callback closes it too: the operation may have partially succeeded, so inspect the destination without reading out credentials before retrying.
- Start only a task-owned temporary process, verify page reachability without submitting real credentials, and give the URL, purpose, expiry and where the key goes. Do not advertise unrelated listeners or reuse another task's page.
- Check the callback's nonsecret result or destination status after submission. Page acceptance is not proof of downstream authentication. Stop the owned process after cancellation or expiry; do not add launch agents, hooks or permanent services.

## Language and password-manager hints

Visible page text and submission feedback default to Simplified Chinese. The password field uses `name="password"` and `autocomplete="current-password"` as standard autofill hints, not a guarantee of 1Password support. Do not auto-submit a password-manager-filled value: the user reviews the purpose and clicks Submit. A generic LAN origin cannot select the correct service credential reliably, particularly when several services share that origin. Prefer manual selection in 1Password or the actual destination's supported vault flow; do not spoof another site's origin or claim tested integration from HTML hints alone. Telegram's in-app browser may not expose the extension; suggest an external supported browser. Never use a real credential to test a discard-only demo.

Treat the page URL as a temporary access credential; deliver it only to a trusted conversation. For real cross-device credentials use trusted HTTPS; reserve plaintext LAN demos for synthetic text. The waiting deadline covers incomplete HTTP requests and is checked again before callback execution. Callback execution itself still needs destination-specific timeouts.

## Boundaries

A masked HTML field prevents casual display, not host access. The local handler and destination necessarily receive plaintext; this is not OS isolation or a universal secret broker. Keep credentials out of model/tool output, shell arguments/history, chat, source code, status files and browser storage. Do not claim the agent cannot read a credential merely because the UI masks it. Never retrieve a saved secret just to verify it.

Browser login/password/2FA tasks should use the host's credential-vault tool when available rather than replacing its protected input flow. New storage, provider changes and downstream external actions still need their normal authorization; permission to open an input page is not permission to change all client configurations.

No key is needed merely to create or test this skill. Use synthetic test values only. No active page should be opened until a real task identifies the destination.

## Verification and extension

Run `python3 -m unittest discover -s <skill-dir>/scripts -p 'test_*.py'` after changing the helper. Add storage/network behavior in a task wrapper, not the generic form. Keep client-specific integration optional: the same helper can be started by Hermes, OMP or other local executors without a host plugin.

OMP portability was verified with disposable copies on macOS (Mac mini and MacBook Pro) and Windows: all three ran the six original tests, blocked one ordinary tool call until an independent loopback client submitted a synthetic value, then continued in the same OMP conversation and wrote the report without a second user message. Windows should select the working `py` launcher when `python` is unavailable and allow enough time for a definitive closed-port refusal; do not treat socket timeout/10035 as proof of closure. This verifies short synchronous continuation only, not human browser interaction, password-manager filling, LAN/HTTPS, real credentials, long waits, detached execution or background session wake-up.

Initial release: temporary HTML input and callback, one-use/expiry behavior, optional TLS, explicit plaintext-LAN opt-in. Install this directory through your client's supported skill directory. Installing files does not start a listener or configure a credential destination.

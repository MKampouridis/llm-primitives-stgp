# Frozen LLM-authored operators (WP3)

Files here are written by the authoring sessions (`scripts/author_operators.py`) and copied
**verbatim** by the freeze step (`scripts/freeze_authored.py`): `<arm>/<domain>/<name>__v1.py`.
Do not edit, format or lint them; their sha256, domain and provenance are locked in
`../<arm>.lock.toml`, and `lpstgp.authoring.registry.load_library` refuses any file that differs.
They sit outside `lpstgp.operators`, so the WP1 registry (`discover()`, arm 6) never loads them.
A change needs a new version file and a recorded decision.

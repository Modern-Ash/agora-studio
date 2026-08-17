# Agora Studio

Agora Studio is a local, read-only foundation for opening an Agora project. It binds only to
`127.0.0.1`, keeps the selected project in memory, and routes Agora reads through an allowlisted CLI
boundary.

Run it without installing dependencies:

```sh
python3 -m agora_studio --port 7357
```

The server exposes:

- `GET /` for readiness and the current selection;
- `POST /api/projects/select` with `{"path":"/absolute/project/path"}`; and
- `GET /api/project` for the current selection.

Run the offline test suite with:

```sh
python3 -m unittest discover -s tests -v
```

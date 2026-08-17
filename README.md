# Agora Studio

Agora Studio is a local, read-only operations console for Agora projects. It binds only to
`127.0.0.1`, keeps the selected project in memory, and visualizes durable project state through an
explicit allowlist of structured Agora CLI reads.

Run it without installing dependencies:

```sh
python3 -m agora_studio --port 7357
```

Open the printed URL to select a local project and browse its overview, actors, swarms, work, and
sessions. The server exposes:

- `GET /` for the visual console;
- `POST /api/projects/select` with `{"path":"/absolute/project/path"}`; and
- `GET /api/project` for the current selection;
- `GET /api/overview` for the selected project's allowlisted read-only snapshot; and
- `GET /assets/<allowlisted-file>` for local interface assets.

Run the offline test suite with:

```sh
python3 -m unittest discover -s tests -v
```

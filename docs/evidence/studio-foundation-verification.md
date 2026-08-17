# Agora Studio foundation verification

## Automated command

```text
python3 -m unittest discover -s tests -v
```

Result: 11 tests passed with no failures. The suite is dependency-free and makes no external network
requests.

## Acceptance coverage

| Requirement | Reproducible check |
| --- | --- |
| F1 startup | The server-construction test asserts the exact bind tuple is `127.0.0.1:7357`; the occupied-port test injects the operating-system bind failure and verifies a failing, actionable diagnostic. |
| F2 selection | Tests cover canonical selection, repeated selection, and atomic replacement after full validation. |
| F3 invalid project | Tests cover nonexistent paths, regular files, directories without `.agora/project.md`, CLI rejection, and preservation of the prior valid selection. |
| F4 read-only boundary | Tests assert the exact argument vector, structured exit/data/diagnostic result, invalid-output handling, and pre-process rejection of an unlisted operation. |
| F5 no mutation | The end-to-end application-path test records SHA-256 hashes for every non-Git project file and `git status --porcelain=v1` before selection and reading, then asserts both snapshots are identical afterward. |

## Environment note

The execution sandbox denies creation of all sockets with `EPERM`, including loopback sockets. The
test therefore verifies the effective bind address at the server-construction boundary and models an
OS-level occupied-port failure deterministically. A live socket smoke test remains appropriate in a
runtime that grants local networking; Agora Studio itself always constructs the server with the
literal IPv4 loopback address and offers no host override.

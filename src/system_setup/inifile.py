"""
Minimal, comment-preserving INI editor for pg_service.conf and my.cnf.

configparser rewrites the whole file (dropping comments and odd formatting),
so instead we keep the raw lines and only replace the sections we touch.
"""
import os


class IniFile:
    def __init__(self, path: str):
        self.path = path
        self.preamble: list[str] = []          # lines before the first [section]
        self.sections: list[tuple[str, list[str]]] = []  # (name, body lines)
        self._load()

    # ---- load / save -----------------------------------------------------

    def _load(self) -> None:
        try:
            with open(self.path, encoding="utf-8", errors="replace") as f:
                lines = f.read().splitlines()
        except FileNotFoundError:
            lines = []
        current: list[str] = self.preamble
        for line in lines:
            s = line.strip()
            if s.startswith("[") and s.endswith("]") and len(s) > 2:
                body: list[str] = []
                self.sections.append((s[1:-1].strip(), body))
                current = body
            else:
                current.append(line)

    def save(self, private: bool = False) -> None:
        out: list[str] = list(self.preamble)
        for name, body in self.sections:
            # keep one blank line between sections
            while out and not out[-1].strip():
                out.pop()
            if out:
                out.append("")
            out.append(f"[{name}]")
            out.extend(l for l in body)
        while out and not out[-1].strip():
            out.pop()
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        # LF endings: libpq and mysql both accept them on Windows
        with open(self.path, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(out) + "\n")
        if private and os.name != "nt":
            os.chmod(self.path, 0o600)

    # ---- queries ---------------------------------------------------------

    def names(self) -> list[str]:
        return [n for n, _ in self.sections]

    def has(self, name: str) -> bool:
        return any(n == name for n, _ in self.sections)

    def get(self, name: str) -> dict[str, str] | None:
        for n, body in self.sections:
            if n == name:
                return parse_body(body)
        return None

    # ---- edits -----------------------------------------------------------

    def set(self, name: str, values: dict[str, str], old_name: str | None = None) -> None:
        """
        Write `values` into section `name`. Keys not in `values` that already
        existed in the section are preserved (so hand-added options survive).
        A value of None/"" removes that key. If old_name is given and differs,
        the section is renamed in place.
        """
        target = old_name if old_name and self.has(old_name) else name
        if target != name and self.has(name):
            raise ValueError(f"'{name}' already exists")
        for i, (n, body) in enumerate(self.sections):
            if n == target:
                self.sections[i] = (name, _merge_body(body, values))
                return
        self.sections.append((name, _merge_body([], values)))

    def remove(self, name: str) -> bool:
        before = len(self.sections)
        self.sections = [(n, b) for n, b in self.sections if n != name]
        return len(self.sections) != before


def _split(line: str) -> tuple[str, str] | None:
    s = line.strip()
    if not s or s[0] in "#;" or "=" not in s:
        return None
    k, v = s.split("=", 1)
    return k.strip(), v.strip()


def parse_body(body: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in body:
        kv = _split(line)
        if kv:
            out[kv[0]] = kv[1]
    return out


def _merge_body(body: list[str], values: dict[str, str]) -> list[str]:
    pending = dict(values)
    result: list[str] = []
    for line in body:
        kv = _split(line)
        if kv and kv[0] in pending:
            v = pending.pop(kv[0])
            if v not in (None, ""):
                result.append(f"{kv[0]}={v}")
            continue
        result.append(line)
    # drop trailing blanks, then append new keys
    while result and not result[-1].strip():
        result.pop()
    for k, v in pending.items():
        if v not in (None, ""):
            result.append(f"{k}={v}")
    return result

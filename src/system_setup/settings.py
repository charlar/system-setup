"""
User settings shared by system-setup (CLI) and system-setupg (GUI).

  Windows: %APPDATA%\\system-setup\\settings.ini
  Linux:   ~/.config/system-setup/settings.ini
"""
import configparser
import os
import platform

IS_WINDOWS = platform.system() == "Windows"
LANGUAGES = ("en", "es")


def settings_file() -> str:
    if IS_WINDOWS:
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    else:
        base = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    return os.path.join(base, "system-setup", "settings.ini")


def _load() -> configparser.ConfigParser:
    cp = configparser.ConfigParser()
    cp.read(settings_file(), encoding="utf-8")
    if not cp.has_section("general"):
        cp.add_section("general")
    return cp


def get(key: str, default: str = "") -> str:
    return _load().get("general", key, fallback=default)


def set(key: str, value: str) -> None:
    cp = _load()
    cp.set("general", key, value)
    path = settings_file()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        cp.write(f)


def system_language() -> str:
    """'es' if the Windows display language (or $LANG) is Spanish, else 'en'."""
    try:
        if IS_WINDOWS:
            import ctypes
            langid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            return "es" if (langid & 0x3FF) == 0x0A else "en"   # LANG_SPANISH primary id
        return "es" if os.environ.get("LANG", "").lower().startswith("es") else "en"
    except Exception:
        return "en"


def get_language() -> str | None:
    """The saved language, or None if the user hasn't chosen one yet."""
    lang = get("language")
    return lang if lang in LANGUAGES else None


def set_language(lang: str) -> None:
    if lang not in LANGUAGES:
        raise ValueError(f"Unsupported language: {lang}")
    set("language", lang)

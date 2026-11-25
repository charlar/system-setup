"""
Messages shown by the GUI that come from Python (errors, install-log notes,
tool descriptions). Page text lives in gui/web/i18n.js.

Usage:  t("key", name="x")   — falls back to English, then to the key itself.
"""
from . import settings

LANG = settings.get_language() or settings.system_language()


def set_lang(lang: str) -> None:
    global LANG
    LANG = lang if lang in MESSAGES else "en"


def t(key: str, **kw) -> str:
    text = MESSAGES.get(LANG, {}).get(key) or MESSAGES["en"].get(key) or key
    return text.format(**kw) if kw else text


MESSAGES: dict[str, dict[str, str]] = {
    "en": {
        # tool catalog
        "tool.git.desc": "Version control.",
        "tool.node.desc": "JavaScript runtime and npm. Needed for Codex.",
        "tool.postgresql.desc": "Database server + psql.",
        "tool.postgresql.note": "The password for the 'postgres' user is saved as psql service 'root' (psql service=root).",
        "tool.mysql.desc": "Database server + mysql client.",
        "tool.mysql.note": "The root password is saved as MySQL login 'root' (mysql --defaults-group-suffix=root).",
        "tool.vscode.desc": "Code editor.",
        "tool.gh.desc": "GitHub from the command line (gh).",
        "tool.claude.desc": "Anthropic's coding agent CLI (native installer, auto-updates).",
        "tool.codex.desc": "OpenAI's coding agent CLI (installed with npm).",

        # job titles
        "job.install": "Install {name}",
        "job.remove": "Remove {name}",
        "job.docker_install": "Install Docker Engine in {distro}",
        "job.docker_remove": "Remove Docker from {distro}",
        "job.apt": "apt {action} {packages} ({distro})",

        # job runner
        "job.busy": "Another install is still running — wait for it to finish.",
        "job.ok": "=== Finished successfully ===",
        "job.failed": "=== Failed ===",
        "job.reboot": "A reboot is required to finish this install.",
        "job.not_found": "[error] command not found: {cmd}",

        # tools
        "err.password_required": "A password is required.",
        "err.choco_password": "For the installer, the password can't contain spaces, / or quotes.",
        "err.not_choco": "{name} wasn't installed with Chocolatey, so it can't be removed here.",
        "log.choco_installing": "Chocolatey isn't installed — installing it first.",
        "log.choco_failed": "[error] Chocolatey could not be installed.",
        "log.npm_missing": "[error] npm not found — install Node.js first.",
        "log.psql_missing": "[warn] psql not found after install — a reboot or new session may be needed.",
        "log.pg_root_saved": "Saved psql service 'root' in {path} (psql service=root).",
        "log.pg_unverified": "[warn] Couldn't connect with the new password yet — saved it as psql service '{name}'. Test it on the PostgreSQL tab.",
        "log.pg_kept_root": "[warn] Couldn't connect with the new password, so the existing 'root' service was left as it is. If PostgreSQL was already installed, it kept its old password. Password used for this install: {password}",
        "log.pw_generated_pg": "A random password was generated. Reveal it or change it on the PostgreSQL tab.",
        "log.mysql_missing": "[error] mysql not found after install.",
        "log.mysql_pw_failed": "[warn] Couldn't set the root password (it may already have one), so no login was saved. Add one on the MySQL tab with the current root password.",
        "log.my_root_saved": "Saved MySQL login 'root' in {path} (mysql --defaults-group-suffix=root).",
        "log.pw_generated_my": "A random password was generated. Reveal it or change it on the MySQL tab.",
        "log.claude_remove": "Remove claude.exe and %USERPROFILE%\\.local\\share\\claude (settings in ~/.claude are kept)",

        # wsl
        "wsl.not_installed": "WSL is not installed.",
        "wsl.no_distros": "WSL has no distros installed.",
        "log.wsl_start_failed": "[error] Couldn't start {distro}: {error}",
        "log.wsl_user": "Default Linux user: {user}",
        "log.wsl_restart": "Restarting {distro} so systemd starts (open WSL terminals for it will close)...",
        "log.docker_ok": "Docker is working. Open a NEW {distro} terminal to use `docker` without sudo.",
        "log.docker_data_kept": "Images, containers and volumes were kept in /var/lib/docker.",
        "log.docker_data_deleted": "Deleted images, containers and volumes.",
        "err.apt_empty": "Enter at least one package name.",
        "err.apt_bad": "Not a valid package name: {names}",

        # pg / mysql
        "err.pg_name": "Service name is required and can't contain [ ] =",
        "err.user_required": "User is required",
        "err.exists": "'{name}' already exists",
        "err.psql_missing": "psql not found — install PostgreSQL first.",
        "err.my_name": "Name can't contain spaces or [ ] =",
        "err.my_quotes": "Password can't contain both ' and \" characters",
        "err.mysql_missing": "mysql not found — install MySQL first.",
        "err.timeout": "Timed out.",
        "err.no_such_conn": "'{name}' not found.",

        # app
        "err.elevation_cancelled": "Elevation was cancelled.",
        "err.wait_for_job": "Wait for the running install to finish first.",
        "err.pull_failed": "git pull failed:\n{out}",
        "err.standard_account": "This is a standard Windows account — installs ask for an administrator's password one at a time instead.",
        "log.elevating": "Asking for administrator permission (check for a Windows prompt)...",
        "log.elevation_cancelled": "[error] Administrator permission was not given.",

        # config files tab
        "file.pg_services": "PostgreSQL services",
        "file.pg_passwords": "PostgreSQL passwords",
        "file.mysql": "MySQL logins",
        "file.git": "Git config",
        "file.ssh": "SSH config",
        "file.npm": "npm config",
        "file.wsl": "WSL settings (Windows side)",
        "file.wsl.hint": "memory, CPUs, networking for all distros",
        "file.claude_settings": "Claude Code settings",
        "file.claude_md": "Claude Code instructions",
        "file.codex": "Codex config",
        "file.vscode": "VS Code settings",
    },
    "es": {
        "tool.git.desc": "Control de versiones.",
        "tool.node.desc": "Entorno de JavaScript y npm. Necesario para Codex.",
        "tool.postgresql.desc": "Servidor de base de datos + psql.",
        "tool.postgresql.note": "La contraseña del usuario 'postgres' se guarda como servicio psql 'root' (psql service=root).",
        "tool.mysql.desc": "Servidor de base de datos + cliente mysql.",
        "tool.mysql.note": "La contraseña de root se guarda como inicio de sesión MySQL 'root' (mysql --defaults-group-suffix=root).",
        "tool.vscode.desc": "Editor de código.",
        "tool.gh.desc": "GitHub desde la línea de comandos (gh).",
        "tool.claude.desc": "Agente de programación de Anthropic (instalador nativo, se actualiza solo).",
        "tool.codex.desc": "Agente de programación de OpenAI (se instala con npm).",

        "job.install": "Instalar {name}",
        "job.remove": "Quitar {name}",
        "job.docker_install": "Instalar Docker Engine en {distro}",
        "job.docker_remove": "Quitar Docker de {distro}",
        "job.apt": "apt {action} {packages} ({distro})",

        "job.busy": "Otra instalación sigue en curso — espere a que termine.",
        "job.ok": "=== Terminado correctamente ===",
        "job.failed": "=== Falló ===",
        "job.reboot": "Hay que reiniciar Windows para terminar esta instalación.",
        "job.not_found": "[error] comando no encontrado: {cmd}",

        "err.password_required": "Se requiere una contraseña.",
        "err.choco_password": "Para el instalador, la contraseña no puede contener espacios, / ni comillas.",
        "err.not_choco": "{name} no se instaló con Chocolatey, así que no se puede quitar desde aquí.",
        "log.choco_installing": "Chocolatey no está instalado — instalándolo primero.",
        "log.choco_failed": "[error] No se pudo instalar Chocolatey.",
        "log.npm_missing": "[error] No se encontró npm — instale Node.js primero.",
        "log.psql_missing": "[aviso] No se encontró psql después de instalar — puede requerir reiniciar o abrir una nueva sesión.",
        "log.pg_root_saved": "Se guardó el servicio psql 'root' en {path} (psql service=root).",
        "log.pg_unverified": "[aviso] Todavía no se pudo conectar con la nueva contraseña — se guardó como servicio psql '{name}'. Pruébelo en la pestaña PostgreSQL.",
        "log.pg_kept_root": "[aviso] No se pudo conectar con la nueva contraseña, así que el servicio 'root' existente no se modificó. Si PostgreSQL ya estaba instalado, conservó su contraseña anterior. Contraseña usada en esta instalación: {password}",
        "log.pw_generated_pg": "Se generó una contraseña aleatoria. Puede verla o cambiarla en la pestaña PostgreSQL.",
        "log.mysql_missing": "[error] No se encontró mysql después de instalar.",
        "log.mysql_pw_failed": "[aviso] No se pudo definir la contraseña de root (puede que ya tenga una), así que no se guardó ningún inicio de sesión. Agregue uno en la pestaña MySQL con la contraseña actual de root.",
        "log.my_root_saved": "Se guardó el inicio de sesión MySQL 'root' en {path} (mysql --defaults-group-suffix=root).",
        "log.pw_generated_my": "Se generó una contraseña aleatoria. Puede verla o cambiarla en la pestaña MySQL.",
        "log.claude_remove": "Quitar claude.exe y %USERPROFILE%\\.local\\share\\claude (la configuración en ~/.claude se conserva)",

        "wsl.not_installed": "WSL no está instalado.",
        "wsl.no_distros": "WSL no tiene distribuciones instaladas.",
        "log.wsl_start_failed": "[error] No se pudo iniciar {distro}: {error}",
        "log.wsl_user": "Usuario de Linux predeterminado: {user}",
        "log.wsl_restart": "Reiniciando {distro} para que arranque systemd (las terminales WSL abiertas de esta distribución se cerrarán)...",
        "log.docker_ok": "Docker funciona. Abra una NUEVA terminal de {distro} para usar `docker` sin sudo.",
        "log.docker_data_kept": "Las imágenes, contenedores y volúmenes se conservaron en /var/lib/docker.",
        "log.docker_data_deleted": "Se eliminaron las imágenes, contenedores y volúmenes.",
        "err.apt_empty": "Escriba al menos un nombre de paquete.",
        "err.apt_bad": "Nombre de paquete no válido: {names}",

        "err.pg_name": "El nombre del servicio es obligatorio y no puede contener [ ] =",
        "err.user_required": "El usuario es obligatorio",
        "err.exists": "'{name}' ya existe",
        "err.psql_missing": "No se encontró psql — instale PostgreSQL primero.",
        "err.my_name": "El nombre no puede contener espacios ni [ ] =",
        "err.my_quotes": "La contraseña no puede contener comillas simples ' y dobles \" a la vez",
        "err.mysql_missing": "No se encontró mysql — instale MySQL primero.",
        "err.timeout": "Se agotó el tiempo de espera.",
        "err.no_such_conn": "No se encontró '{name}'.",

        "err.elevation_cancelled": "Se canceló la solicitud de permisos de administrador.",
        "err.wait_for_job": "Espere a que termine la instalación en curso.",
        "err.pull_failed": "git pull falló:\n{out}",
        "err.standard_account": "Esta es una cuenta estándar de Windows — cada instalación pide la contraseña de un administrador por separado.",
        "log.elevating": "Solicitando permiso de administrador (busque la ventana de Windows)...",
        "log.elevation_cancelled": "[error] No se concedió el permiso de administrador.",

        "file.pg_services": "Servicios de PostgreSQL",
        "file.pg_passwords": "Contraseñas de PostgreSQL",
        "file.mysql": "Inicios de sesión de MySQL",
        "file.git": "Configuración de Git",
        "file.ssh": "Configuración de SSH",
        "file.npm": "Configuración de npm",
        "file.wsl": "Configuración de WSL (lado Windows)",
        "file.wsl.hint": "memoria, CPU y red para todas las distribuciones",
        "file.claude_settings": "Configuración de Claude Code",
        "file.claude_md": "Instrucciones de Claude Code",
        "file.codex": "Configuración de Codex",
        "file.vscode": "Configuración de VS Code",
    },
}

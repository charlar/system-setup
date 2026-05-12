# Configuración del Sistema

> For instructions in English, see [README.md](README.md)

Configuración de máquina en un solo comando para Windows (CMD) y WSL. Instala **uv**, **git** y Python, registra los comandos `system-setup`, `psql` y `mysql`, y luego ofrece instalar de forma interactiva:

- Node.js / npm
- MySQL
- PostgreSQL
- Claude Code CLI
- OpenAI Codex CLI
- VS Code

---

## Inicio rápido

### Windows (CMD) — ejecutar como Administrador

Abra el **Símbolo del sistema como Administrador** y ejecute:

```cmd
curl -fsSL https://raw.githubusercontent.com/charlar/system-setup/master/bootstrap.cmd -o bootstrap.cmd && bootstrap.cmd
```

O descargue `bootstrap.cmd` del repositorio y haga clic derecho → **Ejecutar como administrador**.

### WSL (Ubuntu / Debian)

Abra una **terminal WSL** y ejecute:

```bash
curl -fsSL https://raw.githubusercontent.com/charlar/system-setup/master/bootstrap.sh | bash
```

---

## Qué hace el bootstrap

1. Instala **Chocolatey** (Windows) o usa **apt** (WSL) como gestor de paquetes.
2. Instala **git** si no está disponible.
3. Instala **uv** (gestor de paquetes Python rápido) si no está disponible.
4. Clona este repositorio en `~/system-setup` (o actualiza si ya existe).
5. Usa `uv` para instalar la versión requerida de Python.
6. Ejecuta `uv tool install . --reinstall` para registrar los comandos `system-setup`, `psql` y `mysql`.
7. Ejecuta `system-setup`, que verifica cada herramienta opcional y pregunta si desea instalarla.

---

## Volver a ejecutar la configuración

Tras el bootstrap inicial, ejecute desde cualquier terminal:

```cmd
system-setup
```

---

## Wrappers de psql y mysql

Los comandos `psql` y `mysql` se instalan como wrappers que encuentran el binario real aunque no esté en el PATH (habitual en Windows tras una instalación con interfaz gráfica). Todos los argumentos de la línea de comandos se pasan sin cambios:

```cmd
psql service="root"
mysql --defaults-group-suffix=root
```

---

## Requisitos previos

| Plataforma | Requisito |
|------------|-----------|
| Windows    | Windows 10 / 11, privilegios de **Administrador** |
| WSL        | Ubuntu 20.04+ o cualquier distribución basada en Debian |

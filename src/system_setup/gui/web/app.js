"use strict";

// ---------------------------------------------------------------------------
// Basics
// ---------------------------------------------------------------------------

const $ = (sel, root = document) => root.querySelector(sel);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => (
  { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

let api = null;
let state = { admin: false, update: null };
const loaded = {};

window.addEventListener("error", (e) => api && api.js_error(`${e.message} @ ${e.filename}:${e.lineno}`));
window.addEventListener("unhandledrejection", (e) => api && api.js_error(String(e.reason && e.reason.stack || e.reason)));

async function call(method, ...args) {
  const res = await api[method](...args);
  if (!res || !res.ok) throw new Error((res && res.error) || `${method} failed`);
  return res;
}

function flash(message, kind = "warn") {
  const div = document.createElement("div");
  div.className = `banner ${kind}`;
  div.innerHTML = `<span class="grow">${esc(message)}</span><button class="btn small">Dismiss</button>`;
  div.querySelector("button").onclick = () => div.remove();
  $("#banners").prepend(div);
}

async function guard(fn) {
  try { return await fn(); } catch (e) { flash(e.message, "warn"); }
}

// ---------------------------------------------------------------------------
// Tabs
// ---------------------------------------------------------------------------

const loaders = {
  tools: loadTools,
  wsl: loadWsl,
  pg: loadPg,
  mysql: loadMy,
  files: loadFiles,
};
let currentTab = "tools";

function showTab(name) {
  currentTab = name;
  document.querySelectorAll(".nav").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("hidden", t.id !== `tab-${name}`));
  if (!loaded[name]) { loaded[name] = true; return loaders[name](); }
}

document.querySelectorAll(".nav").forEach((b) => (b.onclick = () => showTab(b.dataset.tab)));

// ---------------------------------------------------------------------------
// Modal
// ---------------------------------------------------------------------------

function openModal({ title, fields, okText = "Save", onSubmit, intro = "" }) {
  $("#modal-title").textContent = title;
  $("#modal-ok").textContent = okText;
  $("#modal-error").textContent = "";
  const body = $("#modal-body");
  body.innerHTML = intro ? `<p class="sub" style="margin-bottom:12px">${intro}</p>` : "";
  const groups = [];
  for (const f of fields) {
    if (f.row) { (groups.at(-1)?.row === f.row ? groups.at(-1).items : (groups.push({ row: f.row, items: [] }), groups.at(-1).items)).push(f); }
    else groups.push({ items: [f] });
  }
  for (const g of groups) {
    const wrap = document.createElement("div");
    if (g.row) wrap.className = "field-row";
    for (const f of g.items) {
      const div = document.createElement("div");
      div.className = "field";
      if (f.type === "checkbox") {
        div.innerHTML = `<label style="color:var(--text)"><input type="checkbox" name="${f.name}" ${f.value ? "checked" : ""}> ${esc(f.label)}</label>`;
      } else {
        div.innerHTML = `<label>${esc(f.label)}</label>
          <div style="display:flex;gap:6px"><input type="${f.type || "text"}" name="${f.name}" value="${esc(f.value)}"
            placeholder="${esc(f.placeholder || "")}" ${f.required ? "required" : ""} spellcheck="false">
          ${f.type === "password" ? '<button type="button" class="btn small reveal">Show</button>' : ""}</div>
          ${f.hint ? `<div class="hint">${f.hint}</div>` : ""}`;
        const rv = div.querySelector(".reveal");
        if (rv) rv.onclick = () => {
          const inp = div.querySelector("input");
          inp.type = inp.type === "password" ? "text" : "password";
          rv.textContent = inp.type === "password" ? "Show" : "Hide";
        };
      }
      wrap.appendChild(div);
    }
    body.appendChild(wrap);
  }
  $("#modal-bg").classList.remove("hidden");
  setTimeout(() => body.querySelector("input")?.focus(), 30);

  return new Promise((resolve) => {
    const close = (v) => { $("#modal-bg").classList.add("hidden"); $("#modal").onsubmit = null; resolve(v); };
    $("#modal-cancel").onclick = () => close(null);
    $("#modal").onsubmit = async (ev) => {
      ev.preventDefault();
      const values = {};
      for (const f of fields) {
        const inp = body.querySelector(`[name="${f.name}"]`);
        values[f.name] = f.type === "checkbox" ? inp.checked : inp.value;
      }
      $("#modal-ok").disabled = true;
      try {
        const out = await onSubmit(values);
        close(out ?? true);
      } catch (e) {
        $("#modal-error").textContent = e.message;
      } finally {
        $("#modal-ok").disabled = false;
      }
    };
  });
}

// ---------------------------------------------------------------------------
// Jobs (install/remove output)
// ---------------------------------------------------------------------------

let jobRefresh = null;

async function runJob(promise, refresh) {
  let res;
  try { res = await promise; } catch (e) { flash(e.message); return; }
  const id = res.job;
  jobRefresh = refresh;
  const log = $("#job-log");
  log.textContent = "";
  $("#drawer").classList.remove("hidden");
  $("#job-dot").className = "dot running";
  setBusy(true);
  let offset = 0;
  const tick = async () => {
    let st;
    try { st = await call("job_status", id, offset); } catch (e) { flash(e.message); return; }
    const d = st.data;
    $("#job-title").textContent = d.title;
    if (d.lines.length) {
      const atBottom = log.scrollTop + log.clientHeight >= log.scrollHeight - 30;
      log.textContent += d.lines.join("\n") + "\n";
      if (atBottom) log.scrollTop = log.scrollHeight;
    }
    offset = d.next;
    if (d.state === "running") { setTimeout(tick, 400); return; }
    $("#job-dot").className = `dot ${d.state}`;
    setBusy(false);
    if (d.reboot) flash("Restart Windows to finish that install.", "info");
    if (jobRefresh) jobRefresh();
  };
  tick();
}

function setBusy(busy) {
  document.body.classList.toggle("busy", busy);
  document.querySelectorAll("[data-job]").forEach((b) => (b.disabled = busy || b.dataset.locked === "1"));
}

$("#job-close").onclick = () => $("#drawer").classList.add("hidden");
$("#job-copy").onclick = () => {
  const ta = document.createElement("textarea");
  ta.value = $("#job-log").textContent;
  document.body.appendChild(ta); ta.select(); document.execCommand("copy"); ta.remove();
  $("#job-copy").textContent = "Copied"; setTimeout(() => ($("#job-copy").textContent = "Copy log"), 1200);
};

// ---------------------------------------------------------------------------
// Windows tools
// ---------------------------------------------------------------------------

async function loadTools() {
  const list = $("#tools-list");
  list.innerHTML = `<div class="empty">Checking what's installed…</div>`;
  let tools;
  try { tools = (await call("get_tools")).data; } catch (e) { list.innerHTML = `<div class="empty">${esc(e.message)}</div>`; return; }
  list.innerHTML = "";
  for (const t of tools) {
    const row = document.createElement("div");
    row.className = "row";
    const pill = t.installed
      ? `<span class="pill ok">Installed${t.source === "other" ? " (not via choco)" : ""}</span>`
      : `<span class="pill no">Not installed</span>`;
    const locked = t.needs_admin && !state.admin;
    row.innerHTML = `
      <div class="main">
        <div class="title">${esc(t.name)} ${pill}</div>
        <div class="desc">${esc(t.description)}</div>
        ${t.installed ? `<div class="detail" title="${esc(t.path)}">${esc(t.version)}${t.path ? " — " + esc(t.path) : ""}</div>` : ""}
      </div>
      <div class="actions"></div>`;
    const actions = row.querySelector(".actions");
    const lockTitle = locked ? "Needs administrator rights" : "";
    if (!t.installed) {
      const b = button("Install", "btn primary", () => installTool(t), locked, lockTitle);
      actions.appendChild(b);
    } else if (t.can_remove) {
      actions.appendChild(button("Remove", "btn danger", () => removeTool(t), locked, lockTitle));
    }
    list.appendChild(row);
  }
  setBusy(document.body.classList.contains("busy"));
}

function button(label, cls, onclick, locked = false, title = "") {
  const b = document.createElement("button");
  b.className = cls;
  b.textContent = label;
  b.dataset.job = "1";
  b.dataset.locked = locked ? "1" : "0";
  b.disabled = locked;
  if (title) b.title = title;
  b.onclick = onclick;
  return b;
}

async function installTool(t) {
  if (t.needs_password) {
    const pw = await openModal({
      title: `Install ${t.name}`,
      okText: "Install",
      intro: esc(t.note),
      fields: [
        { name: "password", label: t.id === "mysql" ? "Root password" : "Password for the 'postgres' user", type: "password", required: true,
          hint: "Saved to your config so psql/mysql connect without asking. No spaces, / or quotes." },
        { name: "confirm", label: "Confirm password", type: "password", required: true },
      ],
      onSubmit: async (v) => {
        if (v.password !== v.confirm) throw new Error("Passwords don't match.");
        return v.password;
      },
    });
    if (!pw) return;
    runJob(call("install_tool", t.id, pw), loadTools);
  } else {
    runJob(call("install_tool", t.id, ""), loadTools);
  }
}

function removeTool(t) {
  if (!confirm(`Remove ${t.name}?`)) return;
  runJob(call("remove_tool", t.id), loadTools);
}

$("#tools-refresh").onclick = loadTools;

// ---------------------------------------------------------------------------
// WSL & Docker
// ---------------------------------------------------------------------------

let wslDistro = null;

async function loadWsl() {
  const body = $("#wsl-body");
  body.innerHTML = `<div class="empty">Checking WSL…</div>`;
  let info;
  try { info = (await call("wsl_distros")).data; } catch (e) { body.innerHTML = `<div class="empty">${esc(e.message)}</div>`; return; }

  if (!info.installed || !info.distros.length) {
    body.innerHTML = `<div class="card"><h3>WSL isn't set up</h3>
      <p class="sub">${esc(info.message)}</p>
      <p class="sub">Installing opens a console window. Windows usually needs a restart afterwards, then Ubuntu asks you to create a Linux username and password.</p>
      <div class="inline"></div></div>`;
    body.querySelector(".inline").appendChild(button("Install WSL + Ubuntu", "btn primary", async () => {
      await guard(async () => { await call("wsl_install"); flash("WSL install started in a separate window. Restart Windows when it finishes.", "info"); });
    }, !state.admin, state.admin ? "" : "Needs administrator rights"));
    return;
  }

  if (!wslDistro || !info.distros.some((d) => d.name === wslDistro)) {
    wslDistro = (info.distros.find((d) => d.default) || info.distros[0]).name;
  }
  body.innerHTML = `
    <div class="inline" style="margin:0 0 14px">
      <label class="sub">Distro</label>
      <select id="distro">${info.distros.map((d) =>
        `<option ${d.name === wslDistro ? "selected" : ""} value="${esc(d.name)}">${esc(d.name)}${d.default ? " (default)" : ""} — WSL${esc(d.version)}, ${esc(d.state)}</option>`).join("")}</select>
    </div>
    <div id="distro-body"><div class="empty">Starting ${esc(wslDistro)} and checking Docker…</div></div>`;
  $("#distro").onchange = (e) => { wslDistro = e.target.value; loadWsl(); };
  return loadDistro(wslDistro);
}

async function loadDistro(name) {
  const box = $("#distro-body");
  let d;
  try { d = (await call("wsl_info", name)).data; } catch (e) { box.innerHTML = `<div class="empty">${esc(e.message)}</div>`; return; }
  if (!d.ok) { box.innerHTML = `<div class="empty">Couldn't start ${esc(name)}: ${esc(d.error)}</div>`; return; }

  let pill;
  if (d.desktop === "yes") pill = `<span class="pill warn">Docker Desktop integration</span>`;
  else if (d.docker && d.active === "active") pill = `<span class="pill ok">Running</span>`;
  else if (d.docker) pill = `<span class="pill warn">Installed, not running</span>`;
  else pill = `<span class="pill no">Not installed</span>`;

  box.innerHTML = `
    <div class="card">
      <h3>Docker Engine ${pill}</h3>
      <div class="kv">
        <span>System</span><span>${esc(d.os)}</span>
        <span>Linux user</span><span>${esc(d.user)}</span>
        <span>systemd</span><span>${d.systemd === "yes" ? "enabled" : "off (will be enabled — needed for Docker)"}</span>
        <span>Docker</span><span>${esc(d.docker || "—")}</span>
        <span>Package</span><span>${esc(d.pkg || "—")}</span>
        <span>Compose</span><span>${esc(d.compose || "—")}</span>
        <span>Docker without sudo</span><span>${d.ingroup === "yes" ? "yes" : "no — install adds you to the docker group"}</span>
      </div>
      ${d.desktop === "yes" ? `<p class="sub">This distro is using Docker Desktop's integration. Turn that off in Docker Desktop before installing Docker Engine here.</p>` : ""}
      <div class="inline" id="docker-actions"></div>
    </div>
    <div class="card">
      <h3>apt packages</h3>
      <p class="sub">Install or remove Linux packages in ${esc(name)} (space separated), e.g. <code>build-essential postgresql-client</code>.</p>
      <div class="inline">
        <input type="text" id="apt-pkgs" placeholder="package names" spellcheck="false">
        <span id="apt-actions" style="display:flex;gap:6px"></span>
      </div>
    </div>`;

  const da = $("#docker-actions");
  if (!d.docker || d.active !== "active") {
    da.appendChild(button(d.docker ? "Repair / reinstall Docker" : "Install Docker Engine", "btn primary", () => {
      if (d.systemd !== "yes" && !confirm(`This will enable systemd and restart ${name}. Open terminals for ${name} will close. Continue?`)) return;
      runJob(call("docker_install", name), () => loadDistro(name));
    }, d.desktop === "yes"));
  }
  if (d.docker && d.active === "active" && (d.pkg || "").startsWith("docker.io")) {
    da.appendChild(button("Switch to Docker's official packages (adds Compose)", "btn", () => {
      if (!confirm(`Replace Ubuntu's docker.io with Docker's official docker-ce packages in ${name}? Images and volumes are kept.`)) return;
      runJob(call("docker_install", name), () => loadDistro(name));
    }));
  }
  if (d.docker && d.desktop !== "yes") {
    da.appendChild(button("Remove Docker", "btn danger", async () => {
      const v = await openModal({
        title: `Remove Docker from ${name}`, okText: "Remove",
        fields: [{ name: "purge", label: "Also delete all images, containers and volumes", type: "checkbox", value: false }],
        onSubmit: async (v) => v,
      });
      if (v) runJob(call("docker_remove", name, v.purge), () => loadDistro(name));
    }));
  }

  const aa = $("#apt-actions");
  for (const action of ["install", "remove"]) {
    aa.appendChild(button(action === "install" ? "Install" : "Remove", action === "install" ? "btn" : "btn danger", () => {
      const pkgs = $("#apt-pkgs").value.trim();
      if (!pkgs) return;
      if (action === "remove" && !confirm(`Remove ${pkgs} from ${name}?`)) return;
      runJob(call("apt", name, action, pkgs), null);
    }));
  }
  setBusy(document.body.classList.contains("busy"));
}

$("#wsl-refresh").onclick = loadWsl;

// ---------------------------------------------------------------------------
// Saved connections (shared by PostgreSQL and MySQL)
// ---------------------------------------------------------------------------

function secretSpan(pw, has) {
  if (!has) return `<span class="pill warn">no password saved</span>`;
  const span = `<span class="secret" data-pw="${esc(pw)}" title="Click to show">••••••••</span>`;
  return span;
}

function wireSecrets(root) {
  root.querySelectorAll(".secret").forEach((s) => (s.onclick = () => {
    const shown = s.dataset.shown === "1";
    s.textContent = shown ? "••••••••" : s.dataset.pw;
    s.dataset.shown = shown ? "0" : "1";
  }));
}

function connList({ listEl, filesEl, items, files, missingTool, describe, usage, onTest, onEdit, onDelete, emptyText }) {
  listEl.innerHTML = "";
  filesEl.innerHTML = files.map((f) => `<div>File: <code>${esc(f)}</code></div>`).join("") +
    (missingTool ? `<div style="color:var(--warn)">${esc(missingTool)}</div>` : "");
  if (!items.length) { listEl.innerHTML = `<div class="empty">${emptyText}</div>`; return; }
  for (const it of items) {
    const row = document.createElement("div");
    row.className = "row";
    row.innerHTML = `
      <div class="main">
        <div class="title">${esc(it.name || "(default)")} ${secretSpan(it.password, it.has_password)}</div>
        <div class="desc">${esc(describe(it))}</div>
        <div class="detail"><code>${esc(usage(it))}</code></div>
        <div class="test-out hidden"></div>
      </div>
      <div class="actions"></div>`;
    const actions = row.querySelector(".actions");
    const out = row.querySelector(".test-out");
    const test = button("Test", "btn", async () => {
      out.className = "test-out"; out.textContent = "Connecting…";
      try {
        const r = await onTest(it);
        out.className = `test-out ${r.success ? "ok" : "bad"}`;
        out.textContent = (r.success ? "✓ " : "✗ ") + (r.output || (r.success ? "Connected" : "Failed"));
      } catch (e) { out.className = "test-out bad"; out.textContent = e.message; }
    });
    actions.append(test, button("Edit", "btn", () => onEdit(it)), button("Delete", "btn danger", () => onDelete(it)));
    actions.querySelectorAll("button").forEach((b) => { delete b.dataset.job; b.disabled = false; });
    listEl.appendChild(row);
  }
  wireSecrets(listEl);
}

// ---- PostgreSQL ------------------------------------------------------------

async function loadPg() {
  let r;
  try { r = await call("pg_list"); } catch (e) { $("#pg-list").innerHTML = `<div class="empty">${esc(e.message)}</div>`; return; }
  connList({
    listEl: $("#pg-list"), filesEl: $("#pg-files"), items: r.data, files: r.files,
    missingTool: r.psql ? "" : "psql isn't installed, so Test won't work until PostgreSQL is installed.",
    emptyText: "No services yet. Add one to connect with <code>psql service=name</code>.",
    describe: (s) => `${s.user || "?"} @ ${s.host || "localhost"}:${s.port || "5432"} / ${s.dbname || s.user}`,
    usage: (s) => `psql service=${s.name}`,
    onTest: async (s) => (await call("pg_test", s.name)),
    onEdit: (s) => editPg(s),
    onDelete: async (s) => {
      if (!confirm(`Delete service '${s.name}'? Its saved password is removed too unless another service uses it.`)) return;
      await guard(async () => { await call("pg_delete", s.name); loadPg(); });
    },
  });
}

async function editPg(s) {
  const isNew = !s;
  s = s || { name: "", host: "localhost", port: "5432", dbname: "postgres", user: "postgres" };
  const ok = await openModal({
    title: isNew ? "Add PostgreSQL service" : `Edit service '${s.name}'`,
    fields: [
      { name: "name", label: "Service name", value: s.name, required: true, hint: "Used as psql service=<i>name</i>" },
      { name: "host", label: "Host", value: s.host, row: "a" },
      { name: "port", label: "Port", value: s.port, row: "a" },
      { name: "dbname", label: "Database", value: s.dbname, row: "b" },
      { name: "user", label: "User", value: s.user, required: true, row: "b" },
      { name: "password", label: "Password", type: "password", value: "",
        placeholder: isNew ? "" : (s.has_password ? "leave blank to keep the saved password" : "none saved"),
        hint: "Stored in pgpass so psql never prompts." },
    ],
    onSubmit: async (v) => {
      const data = { ...v, password: v.password === "" ? null : v.password };
      await call("pg_save", data, isNew ? null : s.name);
    },
  });
  if (ok) loadPg();
}

$("#pg-add").onclick = () => editPg(null);

// ---- MySQL -------------------------------------------------------------------

async function loadMy() {
  let r;
  try { r = await call("my_list"); } catch (e) { $("#my-list").innerHTML = `<div class="empty">${esc(e.message)}</div>`; return; }
  connList({
    listEl: $("#my-list"), filesEl: $("#my-files"), items: r.data, files: r.files,
    missingTool: r.mysql ? "" : "mysql isn't installed, so Test won't work until MySQL is installed.",
    emptyText: "No logins yet. Add one to connect with <code>mysql --defaults-group-suffix=name</code>.",
    describe: (l) => `${l.user || "?"} @ ${l.host || "localhost"}${l.port ? ":" + l.port : ""}${l.database ? " / " + l.database : ""}`,
    usage: (l) => l.name ? `mysql --defaults-group-suffix=${l.name}` : "mysql   (default [client] login)",
    onTest: async (l) => (await call("my_test", l.name)),
    onEdit: (l) => editMy(l),
    onDelete: async (l) => {
      if (!confirm(`Delete login '${l.name || "(default)"}'?`)) return;
      await guard(async () => { await call("my_delete", l.name); loadMy(); });
    },
  });
}

async function editMy(l) {
  const isNew = !l;
  l = l || { name: "", host: "localhost", port: "", user: "root", database: "" };
  const ok = await openModal({
    title: isNew ? "Add MySQL login" : `Edit login '${l.name || "(default)"}'`,
    fields: [
      { name: "name", label: "Login name", value: l.name, hint: "Used as --defaults-group-suffix=<i>name</i>. Leave blank for the default login used by plain <code>mysql</code>." },
      { name: "host", label: "Host", value: l.host, row: "a" },
      { name: "port", label: "Port", value: l.port, placeholder: "3306", row: "a" },
      { name: "user", label: "User", value: l.user, required: true, row: "b" },
      { name: "database", label: "Database (optional)", value: l.database, row: "b" },
      { name: "password", label: "Password", type: "password", value: "",
        placeholder: isNew ? "" : (l.has_password ? "leave blank to keep the saved password" : "none saved") },
    ],
    onSubmit: async (v) => {
      const data = { ...v, password: v.password === "" ? null : v.password };
      await call("my_save", data, isNew ? null : l.name);
    },
  });
  if (ok) loadMy();
}

$("#my-add").onclick = () => editMy(null);

// ---------------------------------------------------------------------------
// Config files
// ---------------------------------------------------------------------------

async function loadFiles() {
  const list = $("#files-list");
  let files;
  try { files = (await call("get_files")).data; } catch (e) { list.innerHTML = `<div class="empty">${esc(e.message)}</div>`; return; }
  list.innerHTML = "";
  for (const f of files) {
    const row = document.createElement("div");
    row.className = "row";
    row.innerHTML = `
      <div class="main">
        <div class="title">${esc(f.label)} ${f.exists ? "" : '<span class="pill no">not created yet</span>'}</div>
        <div class="detail" title="${esc(f.path)}"><code>${esc(f.path)}</code></div>
        ${f.hint ? `<div class="desc">${esc(f.hint)}</div>` : ""}
      </div>
      <div class="actions"></div>`;
    const a = row.querySelector(".actions");
    const edit = document.createElement("button");
    edit.className = "btn"; edit.textContent = f.exists ? "Edit" : "Create";
    edit.onclick = () => guard(async () => { await call("edit_file", f.path); if (!f.exists) loadFiles(); });
    const show = document.createElement("button");
    show.className = "btn"; show.textContent = "Show in folder";
    show.onclick = () => guard(() => call("show_file", f.path));
    a.append(edit, show);
    list.appendChild(row);
  }
}

// ---------------------------------------------------------------------------
// Banners: admin + update
// ---------------------------------------------------------------------------

function renderBanners() {
  $("#banners").querySelectorAll(".sticky").forEach((b) => b.remove());
  if (state.windows && !state.admin) {
    const b = document.createElement("div");
    b.className = "banner warn sticky";
    b.innerHTML = `<span class="grow">Running without administrator rights — Chocolatey installs are disabled. Saved connections and WSL still work.</span>`;
    b.appendChild(button("Restart as administrator", "btn", () => guard(() => call("restart_as_admin"))));
    $("#banners").appendChild(b);
  }
  if (state.update) {
    const b = document.createElement("div");
    b.className = "banner info sticky";
    b.innerHTML = `<span class="grow">A new version of System Setup is available.</span>`;
    b.appendChild(button("Update and restart", "btn primary", async () => {
      if (!confirm("Download the update and restart System Setup?")) return;
      await guard(async () => {
        await call("apply_update");
        b.querySelector(".grow").textContent = "Updating… System Setup will reopen in a few seconds.";
      });
    }));
    $("#banners").appendChild(b);
  }
}

async function pollState() {
  try {
    state = (await call("get_state")).data;
    $("#meta").innerHTML = `v${esc(state.version)}${state.admin ? " · admin" : ""}`;
    renderBanners();
  } catch (e) { /* ignore */ }
  if (state.update === null) setTimeout(pollState, 2000);
}

// ---------------------------------------------------------------------------
// Start
// ---------------------------------------------------------------------------

window.addEventListener("pywebviewready", async () => {
  api = window.pywebview.api;
  await pollState();
  loaded.tools = true;
  await loadTools();
  if (state.selftest) {
    // walk every tab so any rendering error gets reported
    try {
      for (const tab of ["wsl", "pg", "mysql", "files", "tools"]) {
        await showTab(tab);
        await new Promise((r) => setTimeout(r, 2500));
      }
    } catch (e) { api.js_error(String(e && e.stack || e)); }
  }
  api.ready();
});

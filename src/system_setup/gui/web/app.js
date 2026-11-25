"use strict";
// All visible text goes through tr() from i18n.js.

// ---------------------------------------------------------------------------
// Basics
// ---------------------------------------------------------------------------

const $ = (sel, root = document) => root.querySelector(sel);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => (
  { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

let api = null;
let state = { admin: false, update: null };
let loaded = {};

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
  div.innerHTML = `<span class="grow">${esc(message)}</span><button class="btn small">${tr("btn.dismiss")}</button>`;
  div.querySelector("button").onclick = () => div.remove();
  $("#banners").prepend(div);
}

async function guard(fn) {
  try { return await fn(); } catch (e) { flash(e.message, "warn"); }
}

const empty = (html) => `<div class="empty">${html}</div>`;

function button(label, cls, onclick, locked = false, title = "") {
  const b = document.createElement("button");
  b.className = cls;
  b.textContent = label;
  b.dataset.job = "1";            // disabled while an install is running
  b.dataset.locked = locked ? "1" : "0";
  b.disabled = locked;
  if (title) b.title = title;
  b.onclick = onclick;
  return b;
}

// ---------------------------------------------------------------------------
// Language
// ---------------------------------------------------------------------------

function renderLangSwitch() {
  document.querySelectorAll(".lang-switch button").forEach((b) => b.classList.toggle("active", b.dataset.lang === LANG));
}

async function switchLanguage(lang) {
  if (lang === LANG) return;
  await guard(async () => {
    await call("set_language", lang);
    LANG = lang;
    applyStaticText();
    renderLangSwitch();
    renderMeta();
    renderBanners();
    // re-render tabs (tool descriptions etc. come from Python in the new language)
    loaded = {};
    showTab(currentTab);
  });
}

document.querySelectorAll(".lang-switch button").forEach((b) => (b.onclick = () => switchLanguage(b.dataset.lang)));

// ---------------------------------------------------------------------------
// Tabs
// ---------------------------------------------------------------------------

const loaders = { tools: loadTools, wsl: loadWsl, pg: loadPg, mysql: loadMy, files: loadFiles };
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

function openModal({ title, fields, okText, onSubmit, intro = "" }) {
  $("#modal-title").textContent = title;
  $("#modal-ok").textContent = okText || tr("btn.save");
  $("#modal-error").textContent = "";
  const body = $("#modal-body");
  body.innerHTML = intro ? `<p class="sub" style="margin-bottom:12px">${intro}</p>` : "";
  const groups = [];
  for (const f of fields) {
    const last = groups[groups.length - 1];
    if (f.row && last && last.row === f.row) last.items.push(f);
    else groups.push({ row: f.row, items: [f] });
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
          ${f.type === "password" ? `<button type="button" class="btn small reveal">${tr("btn.show")}</button>` : ""}</div>
          ${f.hint ? `<div class="hint">${f.hint}</div>` : ""}`;
        const rv = div.querySelector(".reveal");
        if (rv) rv.onclick = () => {
          const inp = div.querySelector("input");
          inp.type = inp.type === "password" ? "text" : "password";
          rv.textContent = inp.type === "password" ? tr("btn.show") : tr("btn.hide");
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

async function runJob(promise, refresh) {
  let res;
  try { res = await promise; } catch (e) { flash(e.message); return; }
  const id = res.job;
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
    if (d.reboot) flash(tr("banner.reboot"), "info");
    if (refresh) refresh();
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
  $("#job-copy").textContent = tr("btn.copied");
  setTimeout(() => ($("#job-copy").textContent = tr("btn.copy_log")), 1200);
};

// ---------------------------------------------------------------------------
// Windows tools
// ---------------------------------------------------------------------------

async function loadTools() {
  const list = $("#tools-list");
  list.innerHTML = empty(tr("tools.checking"));
  let tools;
  try { tools = (await call("get_tools")).data; } catch (e) { list.innerHTML = empty(esc(e.message)); return; }
  list.innerHTML = "";
  for (const tool of tools) {
    const row = document.createElement("div");
    row.className = "row";
    const pill = tool.installed
      ? `<span class="pill ok">${tr("tools.installed")}${tool.source === "other" ? tr("tools.not_choco") : ""}</span>`
      : `<span class="pill no">${tr("tools.not_installed")}</span>`;
    const uac = tool.needs_admin && !state.admin;   // will show a Windows admin prompt
    row.innerHTML = `
      <div class="main">
        <div class="title">${esc(tool.name)} ${pill}</div>
        <div class="desc">${esc(tool.description)}</div>
        ${tool.installed ? `<div class="detail" title="${esc(tool.path)}">${esc(tool.version)}${tool.path ? " — " + esc(tool.path) : ""}</div>` : ""}
      </div>
      <div class="actions"></div>`;
    const actions = row.querySelector(".actions");
    const shield = uac ? " 🛡" : "";
    const uacTitle = uac ? tr("tools.uac") : "";
    if (!tool.installed) {
      actions.appendChild(button(tr("btn.install") + shield, "btn primary", () => installTool(tool), false, uacTitle));
    } else if (tool.can_remove) {
      actions.appendChild(button(tr("btn.remove") + shield, "btn danger", () => removeTool(tool), false, uacTitle));
    }
    list.appendChild(row);
  }
  setBusy(document.body.classList.contains("busy"));
}

async function installTool(tool) {
  let pw = "";
  if (tool.needs_password) {
    pw = await openModal({
      title: tr("tools.install_title", { name: tool.name }),
      okText: tr("btn.install"),
      intro: esc(tool.note),
      fields: [
        { name: "password", label: tool.id === "mysql" ? tr("tools.pw_mysql") : tr("tools.pw_pg"),
          type: "password", required: true, hint: tr("tools.pw_hint") },
        { name: "confirm", label: tr("tools.pw_confirm"), type: "password", required: true },
      ],
      onSubmit: async (v) => {
        if (v.password !== v.confirm) throw new Error(tr("tools.pw_mismatch"));
        return v.password;
      },
    });
    if (!pw) return;
  }
  runJob(call("install_tool", tool.id, pw), loadTools);
}

function removeTool(tool) {
  if (!confirm(tr("tools.remove_confirm", { name: tool.name }))) return;
  runJob(call("remove_tool", tool.id), loadTools);
}

$("#tools-refresh").onclick = loadTools;

// ---------------------------------------------------------------------------
// WSL & Docker
// ---------------------------------------------------------------------------

let wslDistro = null;

async function loadWsl() {
  const body = $("#wsl-body");
  body.innerHTML = empty(tr("wsl.checking"));
  let info;
  try { info = (await call("wsl_distros")).data; } catch (e) { body.innerHTML = empty(esc(e.message)); return; }

  if (!info.installed || !info.distros.length) {
    body.innerHTML = `<div class="card"><h3>${tr("wsl.not_setup")}</h3>
      <p class="sub">${esc(info.message)}</p>
      <p class="sub">${tr("wsl.install_help")}</p>
      <div class="inline"></div></div>`;
    body.querySelector(".inline").appendChild(button(tr("wsl.install_btn"), "btn primary", async () => {
      await guard(async () => { await call("wsl_install"); flash(tr("wsl.install_started"), "info"); });
    }));
    return;
  }

  if (!wslDistro || !info.distros.some((d) => d.name === wslDistro)) {
    wslDistro = (info.distros.find((d) => d.default) || info.distros[0]).name;
  }
  body.innerHTML = `
    <div class="inline" style="margin:0 0 14px">
      <label class="sub">${tr("wsl.distro")}</label>
      <select id="distro">${info.distros.map((d) =>
        `<option ${d.name === wslDistro ? "selected" : ""} value="${esc(d.name)}">${esc(d.name)}${d.default ? tr("wsl.default") : ""} — WSL${esc(d.version)}</option>`).join("")}</select>
    </div>
    <div id="distro-body">${empty(tr("wsl.starting", { name: esc(wslDistro) }))}</div>`;
  $("#distro").onchange = (e) => { wslDistro = e.target.value; loadWsl(); };
  return loadDistro(wslDistro);
}

async function loadDistro(name) {
  const box = $("#distro-body");
  let d;
  try { d = (await call("wsl_info", name)).data; } catch (e) { box.innerHTML = empty(esc(e.message)); return; }
  if (!d.ok) { box.innerHTML = empty(tr("wsl.start_failed", { name: esc(name), error: esc(d.error) })); return; }

  let pill;
  if (d.desktop === "yes") pill = `<span class="pill warn">${tr("docker.desktop")}</span>`;
  else if (d.docker && d.active === "active") pill = `<span class="pill ok">${tr("docker.running")}</span>`;
  else if (d.docker) pill = `<span class="pill warn">${tr("docker.stopped")}</span>`;
  else pill = `<span class="pill no">${tr("docker.none")}</span>`;

  box.innerHTML = `
    <div class="card">
      <h3>Docker Engine ${pill}</h3>
      <div class="kv">
        <span>${tr("docker.system")}</span><span>${esc(d.os)}</span>
        <span>${tr("docker.user")}</span><span>${esc(d.user)}</span>
        <span>systemd</span><span>${d.systemd === "yes" ? tr("docker.systemd_on") : tr("docker.systemd_off")}</span>
        <span>Docker</span><span>${esc(d.docker || "—")}</span>
        <span>${tr("docker.package")}</span><span>${esc(d.pkg || "—")}</span>
        <span>Compose</span><span>${esc(d.compose || (d.compose_v1 ? tr("docker.compose_v1", { version: d.compose_v1 }) : "—"))}</span>
        <span>${tr("docker.nosudo")}</span><span>${d.ingroup === "yes" ? tr("docker.yes") : tr("docker.nosudo_no")}</span>
      </div>
      ${d.desktop === "yes" ? `<p class="sub">${tr("docker.desktop_note")}</p>` : ""}
      <div class="inline" id="docker-actions" style="flex-wrap:wrap"></div>
    </div>
    <div class="card">
      <h3>${tr("apt.title")}</h3>
      <p class="sub">${tr("apt.sub", { name: esc(name) })}</p>
      <div class="inline">
        <input type="text" id="apt-pkgs" placeholder="${esc(tr("apt.placeholder"))}" spellcheck="false">
        <span id="apt-actions" style="display:flex;gap:6px"></span>
      </div>
    </div>`;

  const da = $("#docker-actions");
  if (!d.docker || d.active !== "active") {
    da.appendChild(button(d.docker ? tr("docker.repair") : tr("docker.install"), "btn primary", () => {
      if (d.systemd !== "yes" && !confirm(tr("docker.systemd_confirm", { name }))) return;
      runJob(call("docker_install", name), () => loadDistro(name));
    }, d.desktop === "yes"));
  }
  if (d.docker && d.active === "active" && ((d.pkg || "").startsWith("docker.io") || (!d.compose && d.compose_v1))) {
    da.appendChild(button(tr("docker.switch"), "btn", () => {
      if (!confirm(tr("docker.switch_confirm", { name }))) return;
      runJob(call("docker_install", name), () => loadDistro(name));
    }));
  }
  if (d.docker && d.desktop !== "yes") {
    da.appendChild(button(tr("docker.remove"), "btn danger", async () => {
      const v = await openModal({
        title: tr("docker.remove_title", { name }), okText: tr("btn.remove"),
        fields: [{ name: "purge", label: tr("docker.purge"), type: "checkbox", value: false }],
        onSubmit: async (v) => v,
      });
      if (v) runJob(call("docker_remove", name, v.purge), () => loadDistro(name));
    }));
  }

  const aa = $("#apt-actions");
  for (const action of ["install", "remove"]) {
    aa.appendChild(button(tr(`btn.${action}`), action === "install" ? "btn" : "btn danger", () => {
      const pkgs = $("#apt-pkgs").value.trim();
      if (!pkgs) return;
      if (action === "remove" && !confirm(tr("apt.remove_confirm", { pkgs, name }))) return;
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
  if (!has) return `<span class="pill warn">${tr("conn.no_password")}</span>`;
  return `<span class="secret" data-pw="${esc(pw)}" title="${esc(tr("conn.click_show"))}">••••••••</span>`;
}

function wireSecrets(root) {
  root.querySelectorAll(".secret").forEach((s) => (s.onclick = () => {
    const shown = s.dataset.shown === "1";
    s.textContent = shown ? "••••••••" : s.dataset.pw;
    s.dataset.shown = shown ? "0" : "1";
  }));
}

function plainButton(label, cls, onclick) {
  const b = document.createElement("button");
  b.className = cls;
  b.textContent = label;
  b.onclick = onclick;
  return b;
}

function connList({ listEl, filesEl, items, files, missingTool, describe, usage, onTest, onEdit, onDelete, onChangePw, emptyText }) {
  listEl.innerHTML = "";
  filesEl.innerHTML = files.map((f) => `<div>${tr("conn.file")} <code>${esc(f)}</code></div>`).join("") +
    (missingTool ? `<div style="color:var(--warn)">${esc(missingTool)}</div>` : "");
  if (!items.length) { listEl.innerHTML = empty(emptyText); return; }
  for (const it of items) {
    const row = document.createElement("div");
    row.className = "row";
    row.innerHTML = `
      <div class="main">
        <div class="title">${esc(it.name || tr("conn.default"))} ${secretSpan(it.password, it.has_password)}</div>
        <div class="desc">${esc(describe(it))}</div>
        <div class="detail"><code>${esc(usage(it))}</code></div>
        <div class="test-out hidden"></div>
      </div>
      <div class="actions"></div>`;
    const out = row.querySelector(".test-out");
    const test = plainButton(tr("btn.test"), "btn", async () => {
      out.className = "test-out"; out.textContent = tr("conn.connecting");
      try {
        const r = await onTest(it);
        out.className = `test-out ${r.success ? "ok" : "bad"}`;
        out.textContent = (r.success ? "✓ " : "✗ ") + (r.output || (r.success ? tr("conn.connected") : tr("conn.failed")));
      } catch (e) { out.className = "test-out bad"; out.textContent = e.message; }
    });
    const changePw = plainButton(tr("btn.change_pw"), "btn", async () => {
      const r = await onChangePw(it);
      if (!r) return;
      out.className = `test-out ${r.success ? "ok" : "bad"}`;
      out.textContent = r.success ? `✓ ${tr("pw.done")}` : `✗ ${tr("pw.failed")} ${r.output}`;
    });
    row.querySelector(".actions").append(
      test,
      changePw,
      plainButton(tr("btn.edit"), "btn", () => onEdit(it)),
      plainButton(tr("btn.delete"), "btn danger", () => onDelete(it)),
    );
    listEl.appendChild(row);
  }
  wireSecrets(listEl);
}

// Change the password on the server, then in the saved config. Returns the result or null if cancelled.
async function changePassword(method, name, user, host) {
  return openModal({
    title: tr("pw.title", { name: name || tr("conn.default") }),
    okText: tr("pw.ok_btn"),
    intro: tr("pw.intro", { user: esc(user), host: esc(host) }),
    fields: [
      { name: "password", label: tr("pw.new"), type: "password", required: true },
      { name: "confirm", label: tr("tools.pw_confirm"), type: "password", required: true },
    ],
    onSubmit: async (v) => {
      if (v.password !== v.confirm) throw new Error(tr("tools.pw_mismatch"));
      const r = (await call(method, name, v.password));
      if (!r.success) throw new Error(`${tr("pw.failed")} ${r.output}`);   // keep the dialog open
      return r;
    },
  });
}

function pwPlaceholder(isNew, item) {
  if (isNew) return "";
  return item.has_password ? tr("conn.keep_pw") : tr("conn.none_saved");
}

// ---- PostgreSQL ------------------------------------------------------------

async function loadPg() {
  let r;
  try { r = await call("pg_list"); } catch (e) { $("#pg-list").innerHTML = empty(esc(e.message)); return; }
  connList({
    listEl: $("#pg-list"), filesEl: $("#pg-files"), items: r.data, files: r.files,
    missingTool: r.psql ? "" : tr("pg.missing"),
    emptyText: tr("pg.empty"),
    describe: (s) => `${s.user || "?"} @ ${s.host || "localhost"}:${s.port || "5432"} / ${s.dbname || s.user}`,
    usage: (s) => `psql service=${s.name}`,
    onTest: (s) => call("pg_test", s.name),
    onChangePw: (s) => changePassword("pg_change_password", s.name, s.user || "postgres", s.host || "localhost"),
    onEdit: (s) => editPg(s),
    onDelete: async (s) => {
      if (!confirm(tr("pg.delete_confirm", { name: s.name }))) return;
      await guard(async () => { await call("pg_delete", s.name); loadPg(); });
    },
  });
}

async function editPg(s) {
  const isNew = !s;
  s = s || { name: "", host: "localhost", port: "5432", dbname: "postgres", user: "postgres" };
  const ok = await openModal({
    title: isNew ? tr("pg.add_title") : tr("pg.edit_title", { name: s.name }),
    fields: [
      { name: "name", label: tr("pg.name"), value: s.name, required: true, hint: tr("pg.name_hint") },
      { name: "host", label: tr("conn.host"), value: s.host, row: "a" },
      { name: "port", label: tr("conn.port"), value: s.port, row: "a" },
      { name: "dbname", label: tr("pg.database"), value: s.dbname, row: "b" },
      { name: "user", label: tr("conn.user"), value: s.user, required: true, row: "b" },
      { name: "password", label: tr("conn.password"), type: "password", value: "",
        placeholder: pwPlaceholder(isNew, s), hint: tr("pg.pw_hint") },
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
  try { r = await call("my_list"); } catch (e) { $("#my-list").innerHTML = empty(esc(e.message)); return; }
  connList({
    listEl: $("#my-list"), filesEl: $("#my-files"), items: r.data, files: r.files,
    missingTool: r.mysql ? "" : tr("my.missing"),
    emptyText: tr("my.empty"),
    describe: (l) => `${l.user || "?"} @ ${l.host || "localhost"}${l.port ? ":" + l.port : ""}${l.database ? " / " + l.database : ""}`,
    usage: (l) => l.name ? `mysql --defaults-group-suffix=${l.name}` : tr("my.default_usage"),
    onTest: (l) => call("my_test", l.name),
    onChangePw: (l) => changePassword("my_change_password", l.name, l.user, l.host || "localhost"),
    onEdit: (l) => editMy(l),
    onDelete: async (l) => {
      if (!confirm(tr("my.delete_confirm", { name: l.name || tr("conn.default") }))) return;
      await guard(async () => { await call("my_delete", l.name); loadMy(); });
    },
  });
}

async function editMy(l) {
  const isNew = !l;
  l = l || { name: "", host: "localhost", port: "", user: "root", database: "" };
  const ok = await openModal({
    title: isNew ? tr("my.add_title") : tr("my.edit_title", { name: l.name || tr("conn.default") }),
    fields: [
      { name: "name", label: tr("my.name"), value: l.name, hint: tr("my.name_hint") },
      { name: "host", label: tr("conn.host"), value: l.host, row: "a" },
      { name: "port", label: tr("conn.port"), value: l.port, placeholder: "3306", row: "a" },
      { name: "user", label: tr("conn.user"), value: l.user, required: true, row: "b" },
      { name: "database", label: tr("my.database"), value: l.database, row: "b" },
      { name: "password", label: tr("conn.password"), type: "password", value: "", placeholder: pwPlaceholder(isNew, l) },
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
  try { files = (await call("get_files")).data; } catch (e) { list.innerHTML = empty(esc(e.message)); return; }
  list.innerHTML = "";
  for (const f of files) {
    const row = document.createElement("div");
    row.className = "row";
    row.innerHTML = `
      <div class="main">
        <div class="title">${esc(f.label)} ${f.exists ? "" : `<span class="pill no">${tr("files.not_created")}</span>`}</div>
        <div class="detail" title="${esc(f.path)}"><code>${esc(f.path)}</code></div>
        ${f.hint ? `<div class="desc">${esc(f.hint)}</div>` : ""}
      </div>
      <div class="actions"></div>`;
    row.querySelector(".actions").append(
      plainButton(f.exists ? tr("btn.edit") : tr("btn.create"), "btn",
        () => guard(async () => { await call("edit_file", f.path); if (!f.exists) loadFiles(); })),
      plainButton(tr("btn.show_folder"), "btn", () => guard(() => call("show_file", f.path))),
    );
    list.appendChild(row);
  }
}

// ---------------------------------------------------------------------------
// Banners: admin + update
// ---------------------------------------------------------------------------

let updating = false;

function renderBanners() {
  $("#banners").querySelectorAll(".sticky").forEach((b) => b.remove());
  if (state.windows && !state.admin) {
    const b = document.createElement("div");
    const standard = state.account === "standard";
    b.className = "banner info sticky";
    b.innerHTML = `<span class="grow">${tr(standard ? "banner.standard" : "banner.not_admin")}</span>`;
    // On a standard account, elevating the window would switch Windows users — don't offer it
    if (!standard) b.appendChild(button(tr("banner.restart_admin"), "btn", () => guard(() => call("restart_as_admin"))));
    $("#banners").appendChild(b);
  }
  if (state.update) {
    const b = document.createElement("div");
    b.className = "banner info sticky";
    b.innerHTML = `<span class="grow">${updating ? tr("banner.updating") : tr("banner.update")}</span>`;
    if (!updating) {
      b.appendChild(button(tr("banner.update_btn"), "btn primary", async () => {
        if (!confirm(tr("banner.update_confirm"))) return;
        await guard(async () => {
          await call("apply_update");
          updating = true;
          renderBanners();
        });
      }));
    }
    $("#banners").appendChild(b);
  }
}

function renderMeta() {
  $("#meta").innerHTML = `v${esc(state.version || "")}${state.admin ? " · " + tr("admin") : ""}`;
}

async function pollState() {
  try {
    state = (await call("get_state")).data;
    renderMeta();
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
  LANG = state.lang || "en";
  applyStaticText();
  renderLangSwitch();
  renderMeta();
  renderBanners();
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

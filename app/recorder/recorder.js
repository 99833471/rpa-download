// Script injetado em todas as páginas/frames durante a gravação.
// Captura cliques, preenchimentos e teclas (Enter), calculando candidatos de
// seletor priorizados e únicos. Envia cada ação para o processo Python via o
// binding window.__rpa_record. Um overlay de controle (apenas no frame de topo)
// permite Concluir/Cancelar a gravação via window.__rpa_control.
//
// NUNCA usa coordenadas de clique — apenas mapeamento de elementos (DOM).

(() => {
  if (window.__rpa_installed) return;
  window.__rpa_installed = true;

  const TOOLBAR_ID = "__rpa_toolbar";
  const isTop = window.top === window.self;

  // ---------------------------------------------------------------- utils
  function cssEsc(s) {
    if (window.CSS && CSS.escape) return CSS.escape(s);
    return String(s).replace(/[^a-zA-Z0-9_-]/g, "\\$&");
  }
  function attrEsc(s) {
    return String(s).replace(/(["\\])/g, "\\$1");
  }
  function looksAuto(id) {
    // Heurística para ignorar ids gerados automaticamente (instáveis).
    if (!id) return true;
    if (id.length > 40) return true;
    if (/\d{4,}/.test(id)) return true;
    if (/[0-9a-f]{8}/i.test(id)) return true;
    if (/^(ember|react|ng-|mui-|radix-|:r)/i.test(id)) return true;
    return false;
  }
  function isUnique(sel) {
    try {
      return document.querySelectorAll(sel).length === 1;
    } catch (e) {
      return false;
    }
  }
  function cssPath(el) {
    if (!(el instanceof Element)) return "";
    const parts = [];
    let cur = el;
    while (cur && cur.nodeType === 1 && cur !== document.body && parts.length < 6) {
      if (cur.id && !looksAuto(cur.id)) {
        parts.unshift("#" + cssEsc(cur.id));
        break;
      }
      let part = cur.tagName.toLowerCase();
      const parent = cur.parentNode;
      if (parent && parent.children) {
        const same = Array.from(parent.children).filter((c) => c.tagName === cur.tagName);
        if (same.length > 1) part += ":nth-of-type(" + (same.indexOf(cur) + 1) + ")";
      }
      parts.unshift(part);
      cur = cur.parentElement;
    }
    return parts.join(" > ");
  }
  function xPath(el) {
    if (el.id && !looksAuto(el.id)) return '//*[@id="' + attrEsc(el.id) + '"]';
    const parts = [];
    let cur = el;
    while (cur && cur.nodeType === 1 && cur !== document.documentElement) {
      let idx = 1;
      let sib = cur.previousElementSibling;
      while (sib) {
        if (sib.tagName === cur.tagName) idx++;
        sib = sib.previousElementSibling;
      }
      parts.unshift(cur.tagName.toLowerCase() + "[" + idx + "]");
      cur = cur.parentElement;
    }
    return "/" + parts.join("/");
  }
  function labelFor(el) {
    const tag = el.tagName.toLowerCase();
    const aria = el.getAttribute && el.getAttribute("aria-label");
    if (aria) return aria.trim();
    const ph = el.getAttribute && el.getAttribute("placeholder");
    if (ph) return ph.trim();
    if (el.id) {
      const lab = document.querySelector('label[for="' + cssEsc(el.id) + '"]');
      if (lab && lab.textContent) return lab.textContent.trim().slice(0, 80);
    }
    const nm = el.getAttribute && el.getAttribute("name");
    if (nm) return nm;
    const txt = (el.textContent || "").trim().replace(/\s+/g, " ");
    if (txt) return txt.slice(0, 80);
    return tag;
  }

  // Lista priorizada de candidatos de seletor, só com os que casam de forma única.
  function candidates(el) {
    const out = [];
    const seen = new Set();
    const add = (type, value) => {
      if (value && !seen.has(value)) {
        seen.add(value);
        out.push({ type, value });
      }
    };
    const tag = el.tagName.toLowerCase();

    if (el.id && !looksAuto(el.id)) {
      const s = "#" + cssEsc(el.id);
      if (isUnique(s)) add("id", s);
    }
    for (const a of ["data-testid", "data-test", "data-cy", "data-qa"]) {
      const v = el.getAttribute && el.getAttribute(a);
      if (v) {
        const s = tag + "[" + a + '="' + attrEsc(v) + '"]';
        if (isUnique(s)) add("css", s);
      }
    }
    const nm = el.getAttribute && el.getAttribute("name");
    if (nm) {
      const s = tag + '[name="' + attrEsc(nm) + '"]';
      if (isUnique(s)) add("css", s);
    }
    const aria = el.getAttribute && el.getAttribute("aria-label");
    if (aria) {
      const s = tag + '[aria-label="' + attrEsc(aria) + '"]';
      if (isUnique(s)) add("css", s);
    }
    const ph = el.getAttribute && el.getAttribute("placeholder");
    if (ph) {
      const s = tag + '[placeholder="' + attrEsc(ph) + '"]';
      if (isUnique(s)) add("css", s);
    }
    // Texto para elementos clicáveis (botões/links) — útil ao Playwright.
    if (["button", "a"].includes(tag) || el.getAttribute("role") === "button") {
      const txt = (el.textContent || "").trim().replace(/\s+/g, " ");
      if (txt && txt.length <= 60) add("text", txt);
    }
    // Caminho CSS estrutural.
    const path = cssPath(el);
    if (path && isUnique(path)) add("css", path);
    // XPath como último recurso (sempre presente).
    add("xpath", xPath(el));
    return out;
  }

  function inToolbar(el) {
    return !!(el && el.closest && el.closest("#" + TOOLBAR_ID));
  }
  function send(payload) {
    try {
      if (window.__rpa_record) window.__rpa_record(JSON.stringify(payload));
    } catch (e) {}
  }
  const FIELD_TAGS = new Set(["input", "textarea", "select"]);
  const SKIP_INPUT_TYPES = new Set(["button", "submit", "reset", "image", "file", "password"]);
  const lastValue = new WeakMap(); // dedupe de valor por elemento
  const touched = new Set();       // campos que receberam foco (snapshot ao concluir)

  // Captura o valor atual de um campo (com dedupe) e registra no histórico.
  function captureField(el) {
    if (!el || inToolbar(el)) return;
    const tag = el.tagName ? el.tagName.toLowerCase() : "";
    if (!FIELD_TAGS.has(tag)) return;
    const type = (el.getAttribute("type") || "").toLowerCase();
    if (SKIP_INPUT_TYPES.has(type)) return;
    let value = el.value;
    if (type === "checkbox" || type === "radio") value = el.checked ? "true" : "false";
    if (value == null) value = "";
    if (tag !== "select" && value === "") return; // ignora campo vazio
    if (lastValue.get(el) === value) return; // já capturado com este valor
    lastValue.set(el, value);
    const label = labelFor(el);
    send({
      action: tag === "select" ? "select" : "fill",
      selectors: candidates(el),
      tag: tag,
      label: label,
      value: value,
    });
    addHistory(label, value);
  }

  // Snapshot final: garante a captura de TODO campo que foi tocado, mesmo os que
  // não disparam 'change' (date pickers, campos preenchidos via JavaScript).
  function snapshotTouched() {
    touched.forEach((el) => {
      try {
        captureField(el);
      } catch (e) {}
    });
  }

  // ------------------------------------------------------------- listeners
  document.addEventListener(
    "click",
    (ev) => {
      const el = ev.target;
      if (!el || inToolbar(el)) return;
      const tag = el.tagName ? el.tagName.toLowerCase() : "";
      // Cliques em campos de texto viram foco; o valor é capturado depois.
      if (FIELD_TAGS.has(tag) && tag !== "select") {
        const t = (el.getAttribute("type") || "").toLowerCase();
        if (!["button", "submit", "checkbox", "radio", "reset"].includes(t)) return;
      }
      send({ action: "click", selectors: candidates(el), tag: tag, label: labelFor(el) });
    },
    true
  );

  // Marca campos que receberam foco (para o snapshot ao concluir).
  document.addEventListener(
    "focusin",
    (ev) => {
      const el = ev.target;
      if (el && !inToolbar(el) && FIELD_TAGS.has((el.tagName || "").toLowerCase())) {
        touched.add(el);
      }
    },
    true
  );

  // Captura no 'change' e também ao SAIR do campo (pega date pickers e campos
  // preenchidos via JavaScript que não disparam 'change').
  document.addEventListener("change", (ev) => captureField(ev.target), true);
  document.addEventListener("focusout", (ev) => captureField(ev.target), true);

  document.addEventListener(
    "keydown",
    (ev) => {
      if (ev.key !== "Enter") return;
      const el = ev.target;
      if (!el || inToolbar(el)) return;
      const tag = el.tagName ? el.tagName.toLowerCase() : "";
      if (tag !== "input") return;
      captureField(el); // grava o valor digitado antes do Enter
      send({ action: "press", selectors: candidates(el), tag: tag, label: labelFor(el), value: "Enter" });
    },
    true
  );

  // --------------------------------------------------------------- overlay
  const HIST = []; // {label, value} — preservado entre recriações da barra

  function addHistory(label, value) {
    HIST.push({ label: label || "(campo)", value: value });
    renderHistory();
  }
  function renderHistory() {
    const list = document.getElementById("__rpa_hist");
    if (!list) return;
    list.innerHTML = "";
    HIST.forEach((it) => {
      const row = document.createElement("div");
      row.style.cssText = "padding:3px 0;border-top:1px solid #2C2C31;";
      const l = document.createElement("div");
      l.textContent = it.label;
      l.style.cssText =
        "color:#D4AF37;font-weight:600;font-size:11px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;";
      const v = document.createElement("div");
      v.textContent = it.value;
      v.style.cssText =
        "color:#F2E9CE;font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;";
      row.appendChild(l);
      row.appendChild(v);
      list.appendChild(row);
    });
    list.scrollTop = list.scrollHeight;
  }

  // Painel compacto no canto inferior direito, com histórico de campos.
  function buildToolbar() {
    if (!isTop || document.getElementById(TOOLBAR_ID)) return;
    const bar = document.createElement("div");
    bar.id = TOOLBAR_ID;
    bar.style.cssText =
      "position:fixed;right:12px;bottom:12px;z-index:2147483647;width:300px;" +
      "background:#161619;color:#F2E9CE;border:1px solid #D4AF37;border-radius:10px;" +
      "padding:8px 10px;font-family:Segoe UI,Arial,sans-serif;font-size:12px;" +
      "box-shadow:0 6px 20px rgba(0,0,0,.45);display:flex;flex-direction:column;gap:6px;";

    const header = document.createElement("div");
    header.style.cssText = "display:flex;align-items:center;gap:6px;";
    const dot = document.createElement("span");
    dot.textContent = "● GRAVANDO";
    dot.style.cssText = "color:#E06C6C;font-weight:700;font-size:11px;flex:1;";
    const finish = document.createElement("button");
    finish.textContent = "✔ Concluir";
    finish.style.cssText =
      "background:#D4AF37;color:#161619;border:none;border-radius:7px;padding:5px 9px;" +
      "font-weight:700;font-size:11px;cursor:pointer;";
    finish.onclick = () => {
      snapshotTouched();
      if (window.__rpa_control) window.__rpa_control("finish");
    };
    const cancel = document.createElement("button");
    cancel.textContent = "✕";
    cancel.title = "Cancelar";
    cancel.style.cssText =
      "background:transparent;color:#F2E9CE;border:1px solid #2C2C31;border-radius:7px;" +
      "padding:5px 8px;font-size:11px;cursor:pointer;";
    cancel.onclick = () => {
      if (window.__rpa_control) window.__rpa_control("cancel");
    };
    header.appendChild(dot);
    header.appendChild(finish);
    header.appendChild(cancel);

    const hint = document.createElement("div");
    hint.textContent = "Campos reconhecidos:";
    hint.style.cssText = "color:#9C9684;font-size:10px;text-transform:uppercase;letter-spacing:.5px;";

    const list = document.createElement("div");
    list.id = "__rpa_hist";
    list.style.cssText = "max-height:30vh;overflow-y:auto;";

    bar.appendChild(header);
    bar.appendChild(hint);
    bar.appendChild(list);
    (document.body || document.documentElement).appendChild(bar);
    renderHistory();
  }

  if (isTop) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", buildToolbar);
    } else {
      buildToolbar();
    }
    // Reinsere a barra caso o site a remova ou após mudanças de DOM.
    setInterval(buildToolbar, 1000);
  }
})();

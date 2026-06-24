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

  // ------------------------------------------------------------- listeners
  document.addEventListener(
    "click",
    (ev) => {
      const el = ev.target;
      if (!el || inToolbar(el)) return;
      const tag = el.tagName ? el.tagName.toLowerCase() : "";
      // Cliques em campos de texto viram foco; o valor é capturado no 'change'.
      if (FIELD_TAGS.has(tag) && tag !== "select") {
        const t = (el.getAttribute("type") || "").toLowerCase();
        if (!["button", "submit", "checkbox", "radio", "reset"].includes(t)) return;
      }
      send({
        action: "click",
        selectors: candidates(el),
        tag: tag,
        label: labelFor(el),
      });
    },
    true
  );

  document.addEventListener(
    "change",
    (ev) => {
      const el = ev.target;
      if (!el || inToolbar(el)) return;
      const tag = el.tagName ? el.tagName.toLowerCase() : "";
      if (!FIELD_TAGS.has(tag)) return;
      const type = (el.getAttribute("type") || "").toLowerCase();
      // Segurança: nunca grava o valor de campos de senha (a sessão cobre o login).
      if (type === "password") return;
      let value = el.value;
      if (type === "checkbox" || type === "radio") value = el.checked ? "true" : "false";
      send({
        action: tag === "select" ? "select" : "fill",
        selectors: candidates(el),
        tag: tag,
        label: labelFor(el),
        value: value,
      });
    },
    true
  );

  document.addEventListener(
    "keydown",
    (ev) => {
      if (ev.key !== "Enter") return;
      const el = ev.target;
      if (!el || inToolbar(el)) return;
      const tag = el.tagName ? el.tagName.toLowerCase() : "";
      if (tag !== "input") return;
      send({ action: "press", selectors: candidates(el), tag: tag, label: labelFor(el), value: "Enter" });
    },
    true
  );

  // --------------------------------------------------------------- overlay
  function buildToolbar() {
    if (!isTop || document.getElementById(TOOLBAR_ID)) return;
    const bar = document.createElement("div");
    bar.id = TOOLBAR_ID;
    bar.style.cssText =
      "position:fixed;top:12px;right:12px;z-index:2147483647;background:#161619;" +
      "color:#F2E9CE;border:1px solid #D4AF37;border-radius:10px;padding:8px 10px;" +
      "font-family:Segoe UI,Arial,sans-serif;font-size:13px;box-shadow:0 6px 20px rgba(0,0,0,.4);" +
      "display:flex;align-items:center;gap:8px;";
    const dot = document.createElement("span");
    dot.textContent = "● GRAVANDO";
    dot.style.cssText = "color:#E06C6C;font-weight:700;";
    const finish = document.createElement("button");
    finish.textContent = "✔ Concluir";
    finish.style.cssText =
      "background:#D4AF37;color:#161619;border:none;border-radius:8px;padding:6px 12px;" +
      "font-weight:700;cursor:pointer;";
    finish.onclick = () => {
      if (window.__rpa_control) window.__rpa_control("finish");
    };
    const cancel = document.createElement("button");
    cancel.textContent = "✕ Cancelar";
    cancel.style.cssText =
      "background:transparent;color:#F2E9CE;border:1px solid #2C2C31;border-radius:8px;" +
      "padding:6px 12px;cursor:pointer;";
    cancel.onclick = () => {
      if (window.__rpa_control) window.__rpa_control("cancel");
    };
    bar.appendChild(dot);
    bar.appendChild(finish);
    bar.appendChild(cancel);
    (document.body || document.documentElement).appendChild(bar);
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

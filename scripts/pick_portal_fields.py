"""Record portal form fields by Option/Alt-clicking them.

Opens the portal in its own browser window. Log in yourself, open the page you
want, then hold Option (Alt) and click a field. The field's id, name, label and
a suggested selector are appended to the output file as one JSON line and a
short "Kaydedildi" note shows in the page. Field values are never recorded.
The browser profile is kept next to the output file, so a restart may not need
a new login.

Usage:
    .venv/bin/python scripts/pick_portal_fields.py [output.jsonl] [start_url]
"""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import sys

from playwright.sync_api import sync_playwright

DEFAULT_URL = "https://portal.hizliteknoloji.com.tr/"

PICKER_JS = r"""
(() => {
  if (window.__pickerInstalled) return;
  window.__pickerInstalled = true;

  const clean = (text) => (text || "").replace(/\s+/g, " ").trim().slice(0, 120);

  function labelFor(el) {
    if (el.id) {
      const label = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
      if (label) return clean(label.innerText);
    }
    const wrapping = el.closest("label");
    if (wrapping) return clean(wrapping.innerText);
    // Nearest text before the field inside the same row or group.
    const group = el.closest(".form-group, tr, .row, .col, td, div");
    if (group) {
      const text = clean(group.innerText);
      if (text && text.length < 120) return text;
    }
    return "";
  }

  function selectorFor(el) {
    if (el.id) return `#${CSS.escape(el.id)}`;
    const tag = el.tagName.toLowerCase();
    const name = el.getAttribute("name");
    if (name) return `${tag}[name="${name}"]`;
    const placeholder = el.getAttribute("placeholder");
    if (placeholder) return `${tag}[placeholder="${placeholder}"]`;
    const text = clean(el.innerText);
    if (text && text.length < 60) return `text=${text}`;
    return "";
  }

  function pathFor(el) {
    const parts = [];
    for (let node = el; node && node.nodeType === 1 && parts.length < 6; node = node.parentElement) {
      let part = node.tagName.toLowerCase();
      if (node.id) { parts.unshift(`${part}#${node.id}`); break; }
      const siblings = node.parentElement ? [...node.parentElement.children].filter((c) => c.tagName === node.tagName) : [];
      if (siblings.length > 1) part += `:nth-of-type(${siblings.indexOf(node) + 1})`;
      parts.unshift(part);
    }
    return parts.join(" > ");
  }

  function describe(el) {
    const rect = el.getBoundingClientRect();
    const info = {
      tag: el.tagName.toLowerCase(),
      type: el.getAttribute("type") || "",
      id: el.id || "",
      name: el.getAttribute("name") || "",
      placeholder: el.getAttribute("placeholder") || "",
      classes: clean(el.className && el.className.baseVal === undefined ? el.className : ""),
      text: el.matches("input, textarea, select") ? "" : clean(el.innerText),
      label: labelFor(el),
      selector: selectorFor(el),
      path: pathFor(el),
      page_x: Math.round(rect.left + rect.width / 2 + window.scrollX),
      page_y: Math.round(rect.top + rect.height / 2 + window.scrollY),
    };
    if (el.tagName === "SELECT") {
      info.options = [...el.options].slice(0, 40).map((o) => ({ value: o.value, text: clean(o.text) }));
    }
    return info;
  }

  const swallow = (event) => {
    if (!event.altKey) return;
    event.preventDefault();
    event.stopPropagation();
  };
  document.addEventListener("mousedown", swallow, true);
  document.addEventListener("mouseup", swallow, true);

  document.addEventListener("click", (event) => {
    if (!event.altKey) return;
    event.preventDefault();
    event.stopPropagation();
    const el = event.target.closest("input, textarea, select, button, a, label, [role], [contenteditable]") || event.target;
    const info = describe(el);
    window.__pick(info);
    const previous = el.style.outline;
    el.style.outline = "3px solid #f59e0b";
    setTimeout(() => { el.style.outline = previous; }, 1200);
    toast(`Kaydedildi: ${info.label || info.placeholder || info.text || info.selector}`);
  }, true);

  // Native prompt/alert dialogs are dismissed by Playwright, so feedback is shown in the page.
  function toast(message) {
    const box = document.createElement("div");
    box.textContent = message;
    box.style.cssText = "position:fixed;right:16px;bottom:16px;z-index:2147483647;background:#111827;color:#fff;" +
      "padding:10px 14px;border-radius:8px;font:14px system-ui;box-shadow:0 4px 12px rgba(0,0,0,.3);max-width:420px";
    document.body.appendChild(box);
    setTimeout(() => box.remove(), 2500);
  }
})();
"""


def main() -> None:
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/picked_fields.jsonl")
    start_url = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_URL
    output.parent.mkdir(parents=True, exist_ok=True)

    def record(source: dict, info: dict) -> None:
        info = {"picked_at": datetime.now().isoformat(timespec="seconds"), "url": source["frame"].url, **info}
        name = info["label"] or info["placeholder"] or info["text"] or "(adsız)"
        with output.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(info, ensure_ascii=False) + "\n")
        print(f"Kaydedildi: {name} -> {info['selector'] or info['path']}", flush=True)

    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            output.parent / "picker-profile", headless=False, viewport=None, locale="tr-TR"
        )
        context.expose_binding("__pick", record)
        context.add_init_script(PICKER_JS)
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(start_url)
        print(
            "Portal açıldı. Giriş yap, istediğin sayfaya git.\n"
            "Bir alanı kaydetmek için Option (⌥) tuşuna basılı tutup tıkla.\n"
            f"Kayıtlar: {output.resolve()}\n"
            "Bitince tarayıcı penceresini kapat.",
            flush=True,
        )
        page.wait_for_event("close", timeout=0)
        context.close()


if __name__ == "__main__":
    main()

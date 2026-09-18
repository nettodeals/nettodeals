"use strict";

document.querySelectorAll('input[name="image_url"]').forEach((input) => {
  const preview = document.createElement("img");
  preview.className = "admin-product-preview";
  preview.alt = "Vorschau des gewählten Produktbilds";
  preview.referrerPolicy = "no-referrer";
  const message = document.createElement("span");
  message.className = "image-preview-message";
  input.parentElement.append(preview, message);
  const refresh = () => {
    preview.hidden = true;
    preview.removeAttribute("src");
    message.textContent = "";
    if (!input.value) return;
    try {
      const url = new URL(input.value);
      if (url.protocol !== "https:") throw new Error("HTTPS erforderlich");
      message.textContent = "Bild wird geladen …";
      preview.src = url.href;
    } catch { message.textContent = "Bitte eine direkte HTTPS-Bildadresse einfügen."; }
  };
  preview.addEventListener("load", () => { preview.hidden = false; message.textContent = "Bild geladen. Bitte Produktmodell und Nutzungsrecht prüfen."; });
  preview.addEventListener("error", () => { preview.hidden = true; message.textContent = "Bild nicht ladbar. Direkte Bildadresse und Hotlink-Sperren prüfen."; });
  input.addEventListener("change", refresh);
  refresh();
});

document.querySelectorAll("[data-copy]").forEach((button) => {
  button.addEventListener("click", async () => {
    const label = button.querySelector("[data-copy-label]");
    try {
      await navigator.clipboard.writeText(button.dataset.copy || "");
      if (label) label.textContent = "Kopiert";
      window.setTimeout(() => {
        if (label) label.textContent = "Kopieren";
      }, 1800);
    } catch {
      if (label) label.textContent = "Markieren";
    }
  });
});

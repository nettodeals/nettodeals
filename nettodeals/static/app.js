"use strict";

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


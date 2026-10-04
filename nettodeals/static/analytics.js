/* Basic consent: no Google script or analytics requests before opt-in. */
(() => {
  "use strict";
  if (window.location.pathname.startsWith("/admin")) return;
  const ID = "G-GQGD9NXG70";
  const KEY = "nettodeals.analytics.v1";
  const TTL = 180 * 24 * 60 * 60 * 1000;
  const banner = document.getElementById("analytics-consent");
  const settings = document.getElementById("analytics-settings");
  const close = document.getElementById("analytics-close");
  if (!banner || !settings || !close) return;
  let started = false;
  let expires = 0;
  let timer;

  function readChoice() {
    try {
      const value = JSON.parse(localStorage.getItem(KEY));
      if (value && ["granted", "denied"].includes(value.choice) &&
          Number.isFinite(value.expires) && value.expires > Date.now() &&
          value.expires <= Date.now() + TTL) return value;
    } catch (_) { /* Storage may be unavailable: default to no tracking. */ }
    return null;
  }
  let choice = readChoice();

  function clearCookies() {
    const parts = window.location.hostname.split(".");
    const domains = [""];
    for (let i = 0; i < parts.length - 1; i++) {
      domains.push("; Domain=" + parts.slice(i).join("."));
    }
    document.cookie.split(";").forEach((entry) => {
      const name = entry.trim().split("=")[0];
      if (name === "_ga" || name === "_ga_GQGD9NXG70") {
        domains.forEach((domain) => {
          document.cookie = name + "=; Max-Age=0; Path=/" + domain + "; SameSite=Lax";
        });
      }
    });
  }
  function show(open) {
    banner.hidden = !open;
    settings.setAttribute("aria-expanded", String(open));
    close.hidden = !choice;
  }
  function stop() {
    window["ga-disable-" + ID] = true;
    clearInterval(timer);
    clearCookies();
    // Reload unloads Google's event listeners, including enhanced measurement.
    // Do not send a denied-consent ping on withdrawal.
    if (started) window.location.reload();
  }
  function start() {
    if (started) return;
    started = true;
    expires = choice.expires;
    window["ga-disable-" + ID] = false;
    window.dataLayer = window.dataLayer || [];
    window.gtag = function () { window.dataLayer.push(arguments); };
    window.gtag("consent", "default", {
      analytics_storage: "granted", ad_storage: "denied",
      ad_user_data: "denied", ad_personalization: "denied"
    });
    window.gtag("js", new Date());
    window.gtag("config", ID, {
      allow_google_signals: false,
      allow_ad_personalization_signals: false,
      cookie_expires: 180 * 24 * 60 * 60,
      cookie_update: false,
      page_location: window.location.origin + window.location.pathname,
      page_referrer: document.referrer ? document.referrer.split(/[?#]/)[0] : ""
    });
    const script = document.createElement("script");
    script.async = true;
    script.src = "https://www.googletagmanager.com/gtag/js?id=" + ID;
    document.head.appendChild(script);
    // Keep a long-open tab from tracking beyond the choice's expiry.
    timer = setInterval(() => {
      if (Date.now() >= expires) { choice = null; stop(); }
    }, 60000);
  }
  function save(value) {
    choice = { choice: value, expires: Date.now() + TTL };
    try { localStorage.setItem(KEY, JSON.stringify(choice)); } catch (_) { /* This page only. */ }
    show(false);
    settings.focus();
    if (value === "granted") start();
    else stop();
  }
  document.getElementById("analytics-accept").addEventListener("click", () => save("granted"));
  document.getElementById("analytics-reject").addEventListener("click", () => save("denied"));
  settings.addEventListener("click", () => {
    show(true);
    document.getElementById("analytics-title").focus();
  });
  close.addEventListener("click", () => { show(false); settings.focus(); });
  // Apply a withdrawal in other open tabs as well.
  window.addEventListener("storage", (event) => {
    if (event.key !== KEY && event.key !== null) return;
    choice = readChoice();
    if (!choice || choice.choice !== "granted") stop();
    else start();
    show(!choice);
  });
  window.addEventListener("pageshow", (event) => {
    if (!event.persisted) return;
    choice = readChoice();
    if (!choice || choice.choice !== "granted") stop();
    else start();
    show(!choice);
  });
  settings.hidden = false;
  show(!choice);
  if (choice && choice.choice === "granted") start();
  else stop();
})();

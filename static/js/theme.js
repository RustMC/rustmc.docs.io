/*
 * Theme toggle. Loaded in <head> so a saved choice applies before the first
 * paint; without a saved choice the system setting decides (see site.css).
 * The toggle button stays hidden when JavaScript does not run.
 */
(function () {
  var KEY = "rustmc-theme";
  var root = document.documentElement;
  var saved = null;
  try {
    saved = localStorage.getItem(KEY);
  } catch (error) {
    saved = null;
  }
  if (saved === "light" || saved === "dark") {
    root.setAttribute("data-theme", saved);
  }

  function isDark() {
    var chosen = root.getAttribute("data-theme");
    if (chosen) {
      return chosen === "dark";
    }
    return window.matchMedia("(prefers-color-scheme: dark)").matches;
  }

  function show(button) {
    var dark = isDark();
    button.setAttribute("aria-pressed", dark ? "true" : "false");
    button.querySelector("[data-label]").textContent = dark ? "Dark" : "Light";
  }

  document.addEventListener("DOMContentLoaded", function () {
    var button = document.querySelector(".theme-toggle");
    if (!button) {
      return;
    }
    button.hidden = false;
    show(button);
    button.addEventListener("click", function () {
      var next = isDark() ? "light" : "dark";
      root.setAttribute("data-theme", next);
      try {
        localStorage.setItem(KEY, next);
      } catch (error) {
        // Storage can be unavailable; the choice then lasts for this page.
      }
      show(button);
    });
  });
})();

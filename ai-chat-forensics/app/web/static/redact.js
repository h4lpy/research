(function () {
  "use strict";

  var toggle = document.getElementById("redact-toggle");
  if (!toggle) return;

  toggle.addEventListener("click", function () {
    var active = document.body.classList.toggle("redact-mode");
    toggle.setAttribute("aria-pressed", active ? "true" : "false");
    toggle.textContent = active ? "Redact: on" : "Redact: off";
  });
})();

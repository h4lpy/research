(function () {
  "use strict";

  var dropzone = document.getElementById("dropzone");
  var input = document.getElementById("file-input");
  var fileNameLabel = document.getElementById("file-name");
  if (!dropzone || !input) return;

  function showFileName() {
    if (!fileNameLabel) return;
    var files = input.files;
    if (!files || !files.length) {
      fileNameLabel.textContent = "";
    } else if (files.length === 1) {
      fileNameLabel.textContent = files[0].name;
    } else {
      fileNameLabel.textContent = files.length + " files selected";
    }
  }

  input.addEventListener("change", showFileName);

  ["dragenter", "dragover"].forEach(function (evt) {
    dropzone.addEventListener(evt, function (e) {
      e.preventDefault();
      dropzone.classList.add("dragover");
    });
  });

  ["dragleave", "drop"].forEach(function (evt) {
    dropzone.addEventListener(evt, function (e) {
      e.preventDefault();
      dropzone.classList.remove("dragover");
    });
  });

  dropzone.addEventListener("drop", function (e) {
    if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length) {
      input.files = e.dataTransfer.files;
      showFileName();
    }
  });
})();

// Sidebar session switching + per-panel Chat/Artifacts tab switching,
// exposed on window.faith so the cross-tab jump-links below (and the
// search/filter block) can reuse the same activation logic instead of
// duplicating it.
var faith = window.faith = window.faith || {};

faith.activateSession = function (panelId) {
  document.querySelectorAll(".session-nav-item").forEach(function (el) {
    el.classList.toggle("active", el.getAttribute("data-panel") === panelId);
  });
  document.querySelectorAll(".session-panel").forEach(function (el) {
    el.classList.toggle("active", el.id === "session-panel-" + panelId);
  });
};

faith.activateTab = function (panelId, tab) {
  document.querySelectorAll('.panel-tab[data-panel="' + panelId + '"]').forEach(function (el) {
    el.classList.toggle("active", el.getAttribute("data-tab") === tab);
  });
  document.querySelectorAll('.tab-content[data-panel="' + panelId + '"]').forEach(function (el) {
    el.classList.toggle("active", el.getAttribute("data-tab-content") === tab);
  });
};

(function () {
  "use strict";

  document.querySelectorAll(".session-nav-item").forEach(function (item) {
    item.addEventListener("click", function () {
      faith.activateSession(item.getAttribute("data-panel"));
    });
  });

  document.querySelectorAll(".panel-tab").forEach(function (btn) {
    btn.addEventListener("click", function () {
      faith.activateTab(btn.getAttribute("data-panel"), btn.getAttribute("data-tab"));
    });
  });
})();

// Cross-tab jump links: Artifacts rows link to "#request-<panel>-<index>",
// but that exchange lives in a different tab (Chat) and possibly a
// different session panel than whatever's currently showing. A plain
// anchor jump does nothing useful against a display:none element, so
// intercept these clicks: switch to the right session and the Chat tab,
// then scroll to the exchange and flash it so it's easy to spot.
(function () {
  "use strict";

  document.addEventListener("click", function (e) {
    var link = e.target.closest ? e.target.closest('a[href^="#request-"]') : null;
    if (!link) return;
    var id = link.getAttribute("href").slice(1);
    var target = document.getElementById(id);
    if (!target) return;

    e.preventDefault();
    var panelId = target.getAttribute("data-panel");
    faith.activateSession(panelId);
    faith.activateTab(panelId, "chat");

    target.scrollIntoView({ behavior: "smooth", block: "center" });
    target.classList.add("jump-highlight");
    setTimeout(function () { target.classList.remove("jump-highlight"); }, 1600);
  });
})();

// Cross-session search + operation-type filter chips + bookmark flags,
// all combined: an exchange shows only if it matches the search text AND
// (no filters are active OR it matches at least one active filter).
// Filters run across every loaded session, not just the active panel -
// hidden panels are still in the DOM - and badge each sidebar entry with
// its own match count so you can see which sessions have hits without
// switching to each one.
(function () {
  "use strict";

  var searchInput = document.getElementById("global-search");
  var filterChips = document.querySelectorAll(".filter-chip");
  var flagButtons = document.querySelectorAll(".flag-toggle");
  if (!searchInput && !filterChips.length) return;

  var globalCount = document.getElementById("global-search-count");
  var panels = document.querySelectorAll(".session-panel");

  function activeFilters() {
    var active = [];
    filterChips.forEach(function (chip) {
      if (chip.classList.contains("active")) active.push(chip.getAttribute("data-filter"));
    });
    return active;
  }

  function matchesFilters(exchange, filters) {
    if (!filters.length) return true;
    return filters.some(function (f) {
      if (f === "bookmarked") return exchange.getAttribute("data-bookmarked") === "1";
      return exchange.getAttribute("data-op-" + f) === "1";
    });
  }

  function apply() {
    var term = searchInput ? searchInput.value.trim().toLowerCase() : "";
    var filters = activeFilters();
    var anyActive = !!(term || filters.length);
    var totalMatches = 0;
    var sessionsWithMatches = 0;

    panels.forEach(function (panel) {
      var panelId = panel.id.replace("session-panel-", "");
      var exchanges = panel.querySelectorAll(".exchange");
      var dividers = panel.querySelectorAll(".idle-divider");
      var matches = 0;

      exchanges.forEach(function (ex) {
        var textOk = !term || ex.textContent.toLowerCase().indexOf(term) !== -1;
        var isMatch = textOk && matchesFilters(ex, filters);
        ex.style.display = isMatch ? "" : "none";
        if (isMatch) matches++;
      });
      dividers.forEach(function (d) {
        d.style.display = anyActive ? "none" : "";
      });

      var badge = document.querySelector('.session-nav-match-badge[data-panel="' + panelId + '"]');
      if (badge) {
        badge.textContent = anyActive ? "· " + matches + " match" + (matches === 1 ? "" : "es") : "";
        badge.classList.toggle("has-matches", !!(anyActive && matches));
        badge.classList.toggle("no-matches", !!(anyActive && !matches));
      }

      totalMatches += matches;
      if (matches) sessionsWithMatches++;
    });

    if (globalCount) {
      globalCount.textContent = anyActive
        ? totalMatches + " match" + (totalMatches === 1 ? "" : "es") + " in " + sessionsWithMatches + " session" + (sessionsWithMatches === 1 ? "" : "s")
        : "";
    }
  }

  if (searchInput) searchInput.addEventListener("input", apply);

  filterChips.forEach(function (chip) {
    chip.addEventListener("click", function () {
      var active = chip.classList.toggle("active");
      chip.setAttribute("aria-pressed", active ? "true" : "false");
      apply();
    });
  });

  flagButtons.forEach(function (btn) {
    btn.addEventListener("click", function () {
      var exchange = btn.closest(".exchange");
      if (!exchange) return;
      var next = exchange.getAttribute("data-bookmarked") !== "1";
      exchange.setAttribute("data-bookmarked", next ? "1" : "0");
      exchange.classList.toggle("flagged", next);
      btn.setAttribute("aria-pressed", next ? "true" : "false");
      btn.title = next
        ? "Remove this bookmark"
        : "Bookmark this exchange for your own reference - not saved, resets when you reload the page";
      apply(); // re-evaluate in case the "Flagged" filter is active
    });
  });
})();

// Artifacts export: JSON (the whole structure) or CSV (files/commands/urls
// flattened into one table) - built client-side from the JSON already
// embedded in the page, so no extra server round-trip is needed.
(function () {
  "use strict";

  var exportButtons = document.querySelectorAll(".export-btn");
  if (!exportButtons.length) return;

  function msToIso(ms) {
    if (ms === null || ms === undefined) return "";
    try {
      return new Date(ms).toISOString();
    } catch (e) {
      return "";
    }
  }

  function csvField(value) {
    var s = value === null || value === undefined ? "" : String(value);
    if (/[",\n]/.test(s)) {
      s = '"' + s.replace(/"/g, '""') + '"';
    }
    return s;
  }

  function toCsv(rows) {
    return rows.map(function (row) {
      return row.map(csvField).join(",");
    }).join("\r\n");
  }

  function artifactsToCsv(art) {
    var rows = [["type", "value", "detail", "timestamp", "request_indices"]];
    (art.files || []).forEach(function (f) {
      rows.push(["file", f.path, "actions: " + (f.actions || []).join(", "), msToIso(f.first_seen), (f.request_indices || []).join(",")]);
    });
    (art.commands || []).forEach(function (c) {
      rows.push(["command", c.command, "cwd: " + (c.cwd || ""), msToIso(c.timestamp), c.request_index]);
    });
    (art.urls || []).forEach(function (u) {
      rows.push(["url", u.url, "sources: " + (u.sources || []).join(","), "", (u.request_indices || []).join(",")]);
    });
    return toCsv(rows);
  }

  function downloadBlob(content, filename, mimeType) {
    var blob = new Blob([content], { type: mimeType });
    var url = URL.createObjectURL(blob);
    var a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
  }

  exportButtons.forEach(function (btn) {
    btn.addEventListener("click", function () {
      var panelId = btn.getAttribute("data-panel");
      var filenameBase = btn.getAttribute("data-filename") || "artifacts";
      var dataEl = document.querySelector('.artifacts-data[data-panel="' + panelId + '"]');
      if (!dataEl) return;

      var art;
      try {
        art = JSON.parse(dataEl.textContent);
      } catch (e) {
        return;
      }

      var format = btn.getAttribute("data-export");
      if (format === "json") {
        downloadBlob(JSON.stringify(art, null, 2), filenameBase + ".json", "application/json");
      } else if (format === "csv") {
        downloadBlob(artifactsToCsv(art), filenameBase + ".csv", "text/csv");
      }
    });
  });
})();

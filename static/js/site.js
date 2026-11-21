/*
 * Small interactive helpers, all optional: the pages work without them.
 * Done: docs menu filter, search across every commit on the Updates page,
 * copy buttons on code blocks. Each control stays hidden unless this runs.
 */
(function () {
  function filterDocs(input) {
    var items = document.querySelectorAll(input.getAttribute("data-filter"));
    input.addEventListener("input", function () {
      var query = input.value.trim().toLowerCase();
      items.forEach(function (item) {
        item.hidden = query !== "" && item.textContent.toLowerCase().indexOf(query) === -1;
      });
    });
  }

  function entry(hash, date, subject, url) {
    var item = document.createElement("li");
    item.className = "update";
    var meta = document.createElement("p");
    meta.className = "update-meta";
    var time = document.createElement("time");
    time.dateTime = date;
    time.textContent = date;
    var link = document.createElement("a");
    link.href = url;
    var code = document.createElement("code");
    code.textContent = hash;
    link.appendChild(code);
    meta.appendChild(time);
    meta.appendChild(link);
    var title = document.createElement("p");
    title.className = "update-subject";
    title.textContent = subject;
    item.appendChild(meta);
    item.appendChild(title);
    return item;
  }

  function searchUpdates(input) {
    var commits = null;
    var results = document.getElementById("updates-search-results");
    var status = document.getElementById("updates-search-status");
    var page = document.getElementById("updates-page");
    var pager = document.getElementById("updates-pager");
    // Matches shown at once; refine the query to see others.
    var limit = 100;

    function show() {
      var query = input.value.trim().toLowerCase();
      results.textContent = "";
      var searching = query !== "";
      page.hidden = searching;
      if (pager) {
        pager.hidden = searching;
      }
      if (!searching) {
        status.textContent = "";
        return;
      }
      if (!commits) {
        status.textContent = "Loading commits…";
        return;
      }
      var matches = commits.filter(function (commit) {
        return (commit[0] + " " + commit[1] + " " + commit[2]).toLowerCase().indexOf(query) !== -1;
      });
      matches.slice(0, limit).forEach(function (commit) {
        results.appendChild(entry(commit[0], commit[1], commit[2], commit[3]));
      });
      status.textContent = matches.length + (matches.length === 1 ? " commit matches" : " commits match") +
        (matches.length > limit ? "; showing the first " + limit + "." : ".");
    }

    input.addEventListener("input", show);
    fetch(input.getAttribute("data-search"))
      .then(function (response) {
        return response.json();
      })
      .then(function (data) {
        commits = data;
        show();
      })
      .catch(function () {
        status.textContent = "Search is unavailable; use the page numbers below.";
      });
  }

  function copyButtons() {
    if (!navigator.clipboard) {
      return;
    }
    document.querySelectorAll("pre").forEach(function (block) {
      var button = document.createElement("button");
      button.type = "button";
      button.className = "copy";
      button.textContent = "Copy";
      button.addEventListener("click", function () {
        navigator.clipboard.writeText(block.innerText).then(function () {
          button.textContent = "Copied";
          setTimeout(function () {
            button.textContent = "Copy";
          }, 1500);
        });
      });
      block.classList.add("has-copy");
      block.appendChild(button);
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-filter]").forEach(function (input) {
      input.closest(".filter").hidden = false;
      filterDocs(input);
    });
    document.querySelectorAll("[data-search]").forEach(function (input) {
      input.closest(".filter").hidden = false;
      searchUpdates(input);
    });
    copyButtons();
  });
})();

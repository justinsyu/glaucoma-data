(function () {
  function valueFor(item, key) {
    if (key === "document_type") {
      return item.dataset.documentType || "";
    }
    return item.dataset[key] || "";
  }

  function compareValues(a, b, key, direction) {
    var left = valueFor(a, key);
    var right = valueFor(b, key);

    if (key === "date") {
      var leftTime = Date.parse(left);
      var rightTime = Date.parse(right);
      if (Number.isNaN(leftTime)) leftTime = direction === "asc" ? Number.MAX_SAFE_INTEGER : Number.MIN_SAFE_INTEGER;
      if (Number.isNaN(rightTime)) rightTime = direction === "asc" ? Number.MAX_SAFE_INTEGER : Number.MIN_SAFE_INTEGER;
      return leftTime - rightTime;
    }

    if (key === "year") {
      var leftYear = Number.parseInt(left, 10);
      var rightYear = Number.parseInt(right, 10);
      if (Number.isNaN(leftYear)) leftYear = direction === "asc" ? Number.MAX_SAFE_INTEGER : Number.MIN_SAFE_INTEGER;
      if (Number.isNaN(rightYear)) rightYear = direction === "asc" ? Number.MAX_SAFE_INTEGER : Number.MIN_SAFE_INTEGER;
      return leftYear - rightYear;
    }

    return left.localeCompare(right, undefined, {
      numeric: true,
      sensitivity: "base"
    });
  }

  function sortBlock(block) {
    var list = block.querySelector("[data-sortable-documents]");
    var keySelect = block.querySelector("[data-sort-key]");
    var dirSelect = block.querySelector("[data-sort-dir]");
    if (!list || !keySelect || !dirSelect) return;

    var key = keySelect.value;
    var direction = dirSelect.value;
    var items = Array.prototype.slice.call(list.querySelectorAll("li"));

    items.sort(function (a, b) {
      var result = compareValues(a, b, key, direction);
      if (result === 0) {
        result = compareValues(a, b, "title", "asc");
      }
      return direction === "desc" ? -result : result;
    });

    items.forEach(function (item) {
      list.appendChild(item);
    });
  }

  function initDocumentSorters() {
    document.querySelectorAll("[data-document-list-block]").forEach(function (block) {
      block.querySelectorAll("select").forEach(function (select) {
        select.addEventListener("change", function () {
          sortBlock(block);
        });
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initDocumentSorters);
  } else {
    initDocumentSorters();
  }
})();

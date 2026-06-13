/**
 * Lightweight interactivity for infographic SVG charts.
 *
 * Markup contract:
 *   <svg class="svg-chart" data-interactive="line">
 *     ...
 *     <circle class="point" data-x="Week 8" data-y="5.8 letters" data-series="Faricimab" cx="..." cy="..." r="4"/>
 *     ...
 *   </svg>
 *
 * Any element with a `data-x` (or `data-y` or `data-value`) attribute
 * becomes a hover target. On hover the tooltip pops up next to the cursor
 * showing the value and (optionally) the series label.
 *
 * Bars work the same way:
 *   <rect class="bar" data-x="3E10 vg/eye" data-y="-84%" data-series="Annualized rate"/>
 *
 * The script also draws an optional vertical hover guide for line charts
 * if the SVG has a <line class="hover-guide"/> element.
 */
(function () {
  if (typeof document === "undefined") return;

  function makeTooltip() {
    var el = document.createElement("div");
    el.className = "chart-tooltip";
    el.setAttribute("role", "tooltip");
    el.setAttribute("aria-hidden", "true");
    document.body.appendChild(el);
    return el;
  }

  function pickSwatchClass(seriesIndex, providedClass) {
    if (providedClass) return providedClass;
    if (seriesIndex === 1) return "alt";
    if (seriesIndex === 2) return "accent";
    return "";
  }

  function setTooltip(tooltip, evt, payload) {
    var swatch = pickSwatchClass(payload.seriesIndex, payload.swatchClass);
    var header = payload.y || payload.value || "";
    var detail = "";
    if (payload.x) {
      detail += '<span class="tooltip-series">' + payload.x + "</span>";
    }
    if (payload.series) {
      detail +=
        '<span class="tooltip-series"><i class="' +
        swatch +
        '"></i> ' +
        payload.series +
        "</span>";
    }
    tooltip.innerHTML = "<strong>" + header + "</strong>" + detail;
    tooltip.style.left = evt.clientX + "px";
    tooltip.style.top = evt.clientY + "px";
    tooltip.classList.add("is-visible");
    tooltip.setAttribute("aria-hidden", "false");
  }

  function hideTooltip(tooltip) {
    tooltip.classList.remove("is-visible");
    tooltip.setAttribute("aria-hidden", "true");
  }

  function readPayload(target) {
    var ds = target.dataset || {};
    if (!ds.x && !ds.y && !ds.value) return null;
    var seriesIndex = 0;
    if (target.classList.contains("alt") || (ds.swatch === "alt")) seriesIndex = 1;
    if (target.classList.contains("accent") || (ds.swatch === "accent")) seriesIndex = 2;
    return {
      x: ds.x || "",
      y: ds.y || ds.value || "",
      value: ds.value || "",
      series: ds.series || "",
      seriesIndex: seriesIndex,
      swatchClass: ds.swatch || ""
    };
  }

  function bindChart(svg, tooltip) {
    var guide = svg.querySelector(".hover-guide");
    var hoverables = svg.querySelectorAll("[data-x], [data-y], [data-value]");

    hoverables.forEach(function (target) {
      target.addEventListener("mouseenter", function (evt) {
        var payload = readPayload(target);
        if (!payload) return;
        target.classList.add("is-active");
        if (guide && target.getAttribute("cx")) {
          guide.setAttribute("x1", target.getAttribute("cx"));
          guide.setAttribute("x2", target.getAttribute("cx"));
          guide.classList.add("is-visible");
        }
        setTooltip(tooltip, evt, payload);
      });
      target.addEventListener("mousemove", function (evt) {
        var payload = readPayload(target);
        if (!payload) return;
        setTooltip(tooltip, evt, payload);
      });
      target.addEventListener("mouseleave", function () {
        target.classList.remove("is-active");
        if (guide) guide.classList.remove("is-visible");
        hideTooltip(tooltip);
      });
      target.addEventListener("focus", function () {
        var payload = readPayload(target);
        if (!payload) return;
        var rect = target.getBoundingClientRect();
        target.classList.add("is-active");
        setTooltip(
          tooltip,
          { clientX: rect.left + rect.width / 2, clientY: rect.top },
          payload
        );
      });
      target.addEventListener("blur", function () {
        target.classList.remove("is-active");
        hideTooltip(tooltip);
      });
      if (!target.hasAttribute("tabindex")) {
        target.setAttribute("tabindex", "0");
      }
    });
  }

  function init() {
    var charts = document.querySelectorAll(".svg-chart[data-interactive]");
    if (!charts.length) return;
    var tooltip = makeTooltip();
    charts.forEach(function (svg) {
      bindChart(svg, tooltip);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();

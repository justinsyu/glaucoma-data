/**
 * Lazy mermaid.js loader.
 *
 * Source markdowns produced by document extraction sometimes contain mermaid
 * code fences (```mermaid). Kramdown emits them as
 * <pre><code class="language-mermaid">...</code></pre>, so they show up as
 * raw text instead of rendered diagrams. This script:
 *   1. Checks if the current page has any language-mermaid blocks.
 *   2. If yes, transforms each <pre><code class="language-mermaid"> into a
 *      <div class="mermaid"> with the original source text.
 *   3. Dynamically imports mermaid.js as an ES module from a CDN and calls
 *      mermaid.run() to render the divs.
 *
 * If the page has zero mermaid blocks, no network request is made.
 *
 * Theme is set to "neutral" so the diagrams match the site's monochromatic
 * light theme. Diagram-side links use the company-primary CSS variable.
 */
(function () {
  function findBlocks() {
    return document.querySelectorAll('pre > code.language-mermaid');
  }

  function transformBlocks(blocks) {
    blocks.forEach(function (code) {
      var pre = code.parentNode;
      if (!pre) return;
      var div = document.createElement('div');
      div.className = 'mermaid';
      div.textContent = code.textContent;
      pre.parentNode.replaceChild(div, pre);
    });
  }

  function loadAndRender() {
    var blocks = findBlocks();
    if (!blocks.length) return;
    transformBlocks(blocks);

    var loader = document.createElement('script');
    loader.type = 'module';
    loader.textContent =
      "import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';" +
      "mermaid.initialize({" +
      "  startOnLoad: false," +
      "  theme: 'neutral'," +
      "  themeVariables: {" +
      "    fontFamily: 'Inter, sans-serif'," +
      "    fontSize: '14px'," +
      "    primaryColor: '#f7f9fb'," +
      "    primaryTextColor: '#06254a'," +
      "    primaryBorderColor: '#d9d9d9'," +
      "    lineColor: '#06254a'," +
      "    secondaryColor: '#ebeceb'," +
      "    tertiaryColor: '#ffffff'" +
      "  }," +
      "  securityLevel: 'loose'," +
      "  flowchart: { useMaxWidth: true, htmlLabels: true, curve: 'basis' }" +
      "});" +
      "mermaid.run({ querySelector: '.mermaid' });";
    document.body.appendChild(loader);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', loadAndRender);
  } else {
    loadAndRender();
  }
})();

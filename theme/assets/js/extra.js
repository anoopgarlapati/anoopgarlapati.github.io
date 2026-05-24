document.addEventListener('DOMContentLoaded', function () {
  // pymdownx.superfences outputs <pre class="mermaid"><code>...</code></pre>
  // Extract text content (which decodes HTML entities) and hand to Mermaid as a div.
  var mermaidBlocks = document.querySelectorAll('pre.mermaid > code');
  mermaidBlocks.forEach(function (code) {
    var div = document.createElement('div');
    div.className = 'mermaid';
    div.textContent = code.textContent.trim();
    code.closest('pre').replaceWith(div);
  });

  mermaid.initialize({
    startOnLoad: true,
    theme: 'default',
    securityLevel: 'loose',
  });
});

# foliate-js (vendored)

Upstream: https://github.com/johnfactotum/foliate-js (MIT, see LICENSE)
Commit: 78914aef4466eb960965702401634c2cb348e9b1 (2026-05-01)

Vendored because upstream publishes no npm release. Only the modules needed to
render EPUB/MOBI/FB2/CBZ are copied; `pdf.js` is replaced by a stub, and the
demo reader (`reader.*`, `ui/`), `dict.js`, `opds.js`, `quote-image.js`,
`uri-template.js` and `vendor/pdfjs/` are omitted.

To update: clone upstream at a newer commit, copy the same file list, re-apply
the `pdf.js` stub, and update the commit hash above.

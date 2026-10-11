// Innesto stub: PDF support (and its ~800 KB pdf.js dependency) is intentionally
// not vendored. foliate-js's view.js imports this module lazily for PDF files.
export const makePDF = async () => {
    throw new Error('PDF files are not supported by Innesto')
}

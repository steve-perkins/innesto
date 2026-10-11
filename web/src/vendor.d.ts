// Minimal typings for the vendored foliate-js modules we touch.
declare module '*/vendor/foliate-js/view.js' {
  export interface TocItem { label: string; href: string; subitems?: TocItem[] }
  export interface Section { id: unknown; linear?: string; size?: number }
  export interface FoliateBook {
    metadata?: { title?: unknown; author?: unknown; language?: unknown }
    sections: Section[]
    toc?: TocItem[]
    dir?: string
    resolveHref(href: string): { index: number; anchor: (doc: Document) => Element | Range | null }
  }
  export interface Location {
    cfi: string
    fraction: number
    section?: { current: number; total: number }
    location?: { current: number; next: number; total: number }
    tocItem?: TocItem
    range?: Range
  }
  export interface Renderer extends HTMLElement {
    setStyles?(css: string): void
    next(): Promise<void>
    prev(): Promise<void>
    getContents(): { doc: Document; index: number }[]
  }
  export class View extends HTMLElement {
    book: FoliateBook
    renderer: Renderer
    lastLocation?: Location
    open(file: File | Blob | string): Promise<void>
    close(): void
    init(opts: { lastLocation?: string | number; showTextStart?: boolean }): Promise<void>
    goTo(target: string | number): Promise<void>
    goToFraction(frac: number): Promise<void>
    goToTextStart(): Promise<void>
    goLeft(): Promise<void> | void
    goRight(): Promise<void> | void
    prev(distance?: number): Promise<void>
    next(distance?: number): Promise<void>
    getCFI(index: number, range: Range): string
  }
}

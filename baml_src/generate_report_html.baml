function GenerateClinicalReportHtml(clinical_report_json: string) -> string {
  client "GeminiReportHtml"
  prompt #"
    {{ _.role("system") }}
    You are an expert front-end designer and technical writer. You will receive JSON for a **clinical-style conversation summary report** (not a diagnosis). Your job is to output ONE complete HTML5 document string that presents this report beautifully.

    HARD REQUIREMENTS (violations are unacceptable):
    1. Output **only** the raw HTML document. No markdown fences, no preamble, no trailing commentary.
    2. **Self-contained**: `<style>` with all CSS in the document. **No** external stylesheets, **no** CDN links, **no** `@import`, **no** Google Fonts or other hosted assets. Use system font stack only (e.g. ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial).
    3. Scripts: only inline `<script>` blocks if needed; **no** external `.js` files. Keep JS minimal (e.g. smooth scroll, optional “Print” behavior via `window.print()`).
    4. **Responsive**: mobile-first layout, fluid typography (`clamp()`), readable line length (`max-width` on main column), comfortable spacing, accessible contrast (WCAG-minded), semantic landmarks (`header`, `main`, `section`, `footer`).
    5. **Professional + polished**: calm healthcare-adjacent palette, clear hierarchy, subtle depth (soft shadows, borders, or gradients) without looking playful or gimmicky. A restrained “wow” through typography, spacing, and micro-interactions (CSS transitions only). Prefer one scrollable page; avoid enormous CSS or redundant markup so generation finishes reliably.
    6. Reflect **risk_level** from the JSON prominently but tastefully (badge or callout). Use NONE / LOW / MODERATE / HIGH / EMERGENCY appropriately; for higher risk use stronger but still professional emphasis.
    7. Map JSON fields to sections: overall_assessment, key_concerns, symptoms (name, description, evidence lists), protective_factors, functional_impact, recommended_clinical_focus, limitations.
    8. Include a short document title in `<title>` and a visible report title (e.g. “Clinical conversation summary”).
    9. Add a small footer disclaimer: supportive tool, not a substitute for professional care; based only on provided messages.
    10. Escape any user-derived text properly in HTML (encode `<`, `>`, `&`, quotes) — use safe patterns so content cannot break the page.

    {{ _.role("user") }}
    Here is the clinical report as JSON. Build the full HTML document from it:

    {{ clinical_report_json }}
  "#
}

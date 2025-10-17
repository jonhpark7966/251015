# Translation Implementation Plan

## Overview
- **Objective**: Translate the existing LaTeX content that feeds the MDX → Astro build pipeline while keeping the current architecture intact.
- **Pipeline Reminder**: LaTeX sources → `latex-importer` script generates MDX → Astro (`npm run build`) produces static site served by FastAPI.

## Translation Workflow
1. **Work per Section**
   - Split the LaTeX sources along logical section boundaries (e.g., `\section`, `\subsection`).
   - Create or reuse per-section LaTeX files or snippets so that each translation unit is small and manageable.
   - Track each section’s progress in version control to enable focused reviews.
2. **Translation Guidelines**
   - Preserve all LaTeX commands, macros, math environments, and structural markup exactly as written.
   - Translate only the human-readable text nodes, including those inside formatting commands such as `\textbf{}` or `\emph{}`.
   - Keep punctuation and spacing consistent to avoid breaking the importer.
   - Run simple linting/formatting (e.g., `latexindent`, brace checks) after edits to catch structural mistakes early.
3. **Automation Hooks**
   - After translating a section, execute the existing importer in `src_space/app/scripts/latex-importer/` to regenerate the MDX for that section.
   - Rebuild the Astro site (`npm run build`) to verify the rendered output; surface any issues for fixes before moving to the next section.

## Version Control Strategy
- Use dedicated feature branches per section or group of related sections.
- Keep commits scoped to a single section’s translation to simplify reviews and potential rollbacks.
- Open pull requests per section so reviewers can check the translation in isolation.

## Terminology Management
- Build a shared glossary (CSV/YAML/Markdown) that maps source terms to their agreed translations.
- Update the glossary whenever a new domain term appears; ensure translators consult it before committing changes.
- Automate glossary validation where possible (e.g., pre-commit hook that flags inconsistent terminology).

## Future Automation/Delegation
- While manual review is deferred, plan for automated quality checks (Lint + importer run) in CI.
- Prepare clear instructions so future assistants (e.g., Claude Code) can follow the same pipeline without ambiguity.


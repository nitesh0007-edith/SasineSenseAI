# Prompt to give Codex

You are working in a research prototype repository called `ros_property_ai_starter`.

Read these files first:
1. `README.md`
2. `CODEX_TASKS.md`
3. `docs/RESEARCH_PLAN.md`
4. `docs/ANNOTATION_GUIDE.md`

Goal:
Build the system incrementally as an evidence-grounded document-intelligence pipeline for historical Scottish/UK property/legal records.

Important constraints:
- This is not an authoritative land-registration system.
- Do not invent RoS internal APIs, schemas, data, architecture, or business rules.
- Do not add autonomous legal-decision behavior.
- Every extracted field should preserve evidence/provenance.
- External OCR/VLM services must be behind provider interfaces.
- Use mock/local providers by default.
- Add tests for every feature.
- Keep changes small and runnable.
- Follow `CODEX_TASKS.md` in order.
- Do not jump to agents before the first milestone is complete.
- Preserve conflicting extraction candidates rather than silently dropping them.
- Prefer deterministic validation when possible.
- Add clear TODOs where a real dataset or provider is required.

Start with:
1. Run the tests.
2. Inspect the repository for missing imports or broken paths.
3. Complete Phase 0.
4. Implement Phase 1 Task 1.1 and 1.2.
5. Stop after tests pass and summarize:
   - files changed;
   - commands run;
   - current limitations;
   - recommended next task.

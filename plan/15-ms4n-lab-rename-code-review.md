<!-- Mirrored from .omx/plans for git-visible review durability. Keep in sync with the OMX code-review artifact. -->

# Code Review: Rename MS4N-prefixed Lab Surface to Lab

Date: 2026-05-14
Scope: planning/documentation rename of the user-facing top-level surface from an MS4N-prefixed Lab label to **Lab**.

## Verdict

- Code-reviewer recommendation: **APPROVE**
- Architectural status: **CLEAR**
- Final recommendation: **APPROVE**

## Decision reviewed

- User-facing presentation surface: `Lab`
- Future presentation package: `src/automataii/presentation/qt/tabs/lab/`
- Future tab class: `LabTab`
- Future objectName: `tab_lab`
- Future UI tests: `tests/presentation/lab/test_lab_presenter.py`, `tests/ui/tabs/test_lab_tab.py`
- Backend/research bounded context remains MS4N: `domain/application/infrastructure/ms4n`

## First review findings and fixes

1. Stale commit slice name used an MS4N-prefixed Lab wording.
   - Fixed in `plan/10`: now `lab tab skeleton`.
2. Presentation test path implied a presentation-level MS4N namespace.
   - Fixed in `plan/10`: mechanism-design seam test is `tests/presentation/qt/tabs/mechanism_design/test_ms4n_snapshot_adapter.py`.
3. Naming constraint sentence was malformed.
   - Fixed in `plan/10`: now explicitly requires `LabTab`, `presentation/qt/tabs/lab`, and `tab_lab`.
4. Markdown whitespace check failed.
   - Fixed: `git diff --cached --check` passes.

## Verification evidence

```text
git diff --cached --check
# passed
```

```text
stale naming scan
# no residues for stale MS4N-prefixed Lab label/class/package/objectName/test path terms
```

```text
uv run pytest tests/test_project_serializer_assets.py tests/ui/tabs/test_path_trace_manager.py -q
51 passed in 1.49s
```

Second-pass review:

- code-reviewer: **APPROVE**, 0 issues.
- architect: **CLEAR**.

## Remaining implementation guardrail

During coding, Lab UI may depend on `application.ms4n`, but `domain.ms4n` must remain Qt-free and the presentation package must remain `lab`, not MS4N-prefixed.

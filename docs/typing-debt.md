# Typing debt policy

The mypy debt is mostly legacy UI typing, not core-domain rot.

Run:

```bash
make type-check        # fail only on new mypy debt
make type-debt-report  # show debt by layer, error code, and file
```

Current cleanup order:

1. Fix new mypy errors immediately; do not update the baseline to hide them.
2. Reduce `legacy-qt-ui` by touching one hot file at a time when already editing it.
3. Reduce `opencv-image-pipeline` with small adapter casts around OpenCV/YAML calls.
4. Update `scripts/mypy_baseline.json` only after errors are actually fixed:

```bash
uv run python scripts/check_mypy_baseline.py --update --report
```

Do not try to annotate the entire Qt layer in one pass. It is too broad and
will produce behavior-neutral churn without making the app safer.

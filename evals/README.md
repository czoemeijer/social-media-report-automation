# Evaluation suite

This directory defines privacy-safe, synthetic campaign cases and a deterministic scorer. It does
not contain real screenshots or published benchmark claims.

## Generate the synthetic screenshot-like fixture

```bash
uv run python evals/generate_synthetic_fixture.py
```

Generated PNG files are written under `evals/generated/`, which is ignored by Git. The images are
simple fake Insights screens with no real people, accounts, or campaign data.

## Score a model/workflow run

Save the Dify structured result as a JSON object containing `reconstruction` and `assets`, then run:

```bash
uv run python evals/evaluate.py path/to/prediction.json
```

The scorer reports field extraction accuracy, exact-number fidelity, null-vs-zero accuracy, scope
classification, pairwise asset grouping F1, Story grouping accuracy, and deterministic numerical
consistency. Results are printed for that run only. Do not publish them unless the provider, model,
settings, dataset version, and date are recorded and the run was actually performed.

Vision calls are intentionally outside the default test suite because they cost money and send
fixture images to the configured Dify model provider.

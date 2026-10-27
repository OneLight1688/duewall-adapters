# Citing DueWall data

## Text citation

> DueWall Labs, "DueWall structured dataset: tokenized credit maturities,
> liquidity terms and fund NAV", snapshot 2026-10-25.
> https://duewall.com (data: CC-BY 4.0)

## BibTeX

```bibtex
@misc{duewall2026snapshot,
  author       = {{DueWall Labs}},
  title        = {DueWall structured dataset: tokenized credit maturities,
                  liquidity terms and fund {NAV}},
  year         = {2026},
  month        = {10},
  note         = {Snapshot 2026-10-25; data licensed CC-BY 4.0;
                  per-record provenance in source\_url field},
  url          = {https://duewall.com}
}
```

## Per-fund citation (terms pages)

> DueWall Labs, "{Fund} ({TOKEN}) — structured liquidity terms", extracted from
> issuer factsheet, verified {verification date}. https://duewall.com/fund-{slug}.html

## Notes for researchers

- Every event carries `source_url` — cite the underlying document when your
  claim depends on a single record.
- `status` distinguishes machine-extracted (`draft`) from human-verified
  (`verified`) records; state which you rely on.
- Snapshots are immutable point-in-time exports; the live site updates weekly.
- Found an error? Open an issue — corrections are applied publicly.

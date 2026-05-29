# Real public-domain plan PDFs for the workbench demo (M7.W1)

Three single-page PDF extracts from the Cambridge MA Historical Commission
public records, used by the workbench's PDF viewport (image #1 of the
M6 blueprint).

| File | Source jurisdiction | Source URL (public record) | Drawing slug in KG |
|------|---------------------|----------------------------|---------------------|
| `cambridge-343medford-overview.pdf` | Cambridge MA, USA | https://www.cambridgema.gov/-/media/Files/historicalcommission/pdf/chcmeetingfiles/case4487_plans_BZA.pdf · page 5 | cambridge-343medford-overview |
| `cambridge-2garden-existing-overview.pdf` | Cambridge MA, USA | Cambridge MA Historical Commission case · page 9 | cambridge-2garden-existing-overview |
| `cambridge-sp336-basement.pdf` | Cambridge MA, USA | Cambridge MA Historical Commission case SP336 · page 8 | cambridge-sp336-basement |

All three are public records, originally posted on `cambridgema.gov` by
the Cambridge Historical Commission. They are reproduced here as-is for
the purpose of demonstrating the ArchReview-KG plan-review pipeline on
real-world floor plans, with full attribution. No redaction or alteration
has been made beyond the single-page extraction documented in each
case's `*_provenance.json` file in `../understanding_benchmarks/real/`.

These PDFs are NOT covered by the project's MIT license; they remain
property of their original authors. If you are an author or the licensing
authority and would like the file removed, please open an issue.

## Provenance and matching
Each provenance file under `samples/understanding_benchmarks/real/` notes
the original `local_path_used_for_annotation` from `tmp/p86-multisrc/...`;
the committed file here is the same byte content with a normalised
filename matching the project slug, so the web UI can find it by:

```python
samples/real_plans/{project_slug}.pdf
```

This convention is used by `archkg.kg.web::drawing_page_png` (M7.W1
PDF-viewport endpoint).

# Standards Source PDFs — Provenance

PDFs in this directory are **public-domain Chinese national-standard documents**
fetched from authoritative gov.cn / ministry-aligned sources. They are NOT
redistributed (gitignored) — this file records where each was obtained so the
extraction can be reproduced.

| File | Standard | Pages | Source URL | Fetched |
|---|---|---|---|---|
| `GB50096-2011.pdf` | 住宅设计规范 (强制条文摘要) | 8 | https://download.s21i.co99.net/16469700/0/1/ABUIABA9GAAg36SW9AUo95ea-QI.pdf | 2026-04-26 |
| `GB50016-2014.pdf` | 建筑设计防火规范 (2018年版) | 464 | https://yjgl.tj.gov.cn/ZWFW5050/BZ2939/GJBZ6056/202011/W020201112603058585171.pdf (天津市应急管理局) | 2026-04-26 |
| `GB50352-2019.pdf` | 民用建筑设计统一标准 | 65 | https://pyso.newswz.cn/upload/202207/202207141825456611.pdf | 2026-04-26 |
| `GB50763-2012.pdf` | 无障碍设计规范 | 116 | https://www.ahsz.gov.cn/download/5bbe97c7b760b4e97150fcb8 (安徽省商州市) | 2026-04-26 |

## Notes
- GB 50096-2011 source is a curated 强制条文 (mandatory clauses only) PDF, not the full 100-page standard. This is intentional: the rule engine only acts on operative thresholds, and 强制 clauses are the operative subset.
- GB 50016-2014 includes the 2018 partial-amendment edition (含 5.5.8 / 5.5.13 / 5.5.15 修订).
- All clauses extracted into `archkg/knowledge/data/standards.yaml` carry `paraphrase: false` if the `clause_text` is verbatim from the source PDF, or `true` if rewritten for clarity.

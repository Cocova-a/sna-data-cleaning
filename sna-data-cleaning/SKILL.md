---
name: sna-data-cleaning
description: Clean social network analysis transfer-record CSV data into a city-pair yearly panel and compute yearly network-level indicators. Use when the user has an original transfer records CSV containing trans_time, city_A, and city_B columns, or Chinese aliases such as 申请年份, 申请人城市, 第二申请人城市, plus a city reference workbook such as 市县简称对照.xlsx, and asks to clean data, build a panel, count year-city-pair transfers, or calculate SNA metrics such as nodes, edges, density, average degree, weighted degree, clustering, giant component ratio, and degree centralization.
---

# SNA Data Cleaning

## Workflow

Use `scripts/build_sna_panel.py` for the deterministic cleaning and metric calculation pipeline.

Required inputs:
- Original records CSV uploaded or provided by the user. It must contain `trans_time`, `city_A`, and `city_B`, or recognizable Chinese aliases.
- City reference workbook, usually `市县简称对照.xlsx`, with:
  - `Sheet1` containing a `城市` column for valid mainland cities.
  - `港澳台` containing a `城市` column for Hong Kong, Macau, and Taiwan cities to exclude.

Default outputs:
- `<prefix>面板.csv`
- `<prefix>网络指标.csv`

If the user does not specify `prefix`, infer it from the original CSV stem by removing a trailing `记录` if present. For example:
- `人工智能技术专利转移记录.csv` -> `人工智能技术专利转移面板.csv`
- `人工智能技术专利转移记录.csv` -> `人工智能技术专利转移网络指标.csv`

## Cleaning Rules

1. Extract only `trans_time`, `city_A`, and `city_B`.
   - The script can infer common source columns such as `申请年份`, `公开公告年份`, `授权公告年份`, `转让生效年份`, `申请人城市`, `第一申请人城市`, `转让人城市`, `第二申请人城市`, and `受让人城市`.
   - Use `--time-column`, `--city-a-column`, and `--city-b-column` when the source uses different column names.
2. Strip surrounding whitespace in these fields.
3. Delete rows where any extracted field is blank.
4. Keep only rows where both `city_A` and `city_B` exist in the valid mainland city set from `Sheet1/城市`.
5. Delete rows where either `city_A` or `city_B` exists in the Hong Kong/Macau/Taiwan city set from `港澳台/城市`.
6. Group by `trans_time`, `city_A`, and `city_B`; count records as `count`.

## Network Metric Rules

Use `city_A -> city_B` as a directed edge and `count` as edge weight.

For structural metrics, exclude self-loops where `city_A == city_B`. This affects:
- `edges`
- `density`
- `avg_degree`
- `avg_weighted_degree`
- `avg_clustering`
- `giant_component_ratio`
- `degree_centralization`

Compute annual metrics with columns:

`year, nodes, edges, density, avg_degree, avg_weighted_degree, avg_clustering, giant_component_ratio, degree_centralization`

Metric definitions:
- `nodes`: distinct cities appearing in the annual panel before self-loop exclusion.
- `edges`: distinct non-self-loop directed city pairs.
- `density`: directed density, `edges / (nodes * (nodes - 1))`.
- `avg_degree`: average total directed degree, `(in_degree + out_degree) / nodes`.
- `avg_weighted_degree`: average weighted degree using non-self-loop transfer counts, adding each edge weight to both endpoints.
- `avg_clustering`: average unweighted clustering on the undirected projection of non-self-loop edges.
- `giant_component_ratio`: largest connected component size divided by node count on the undirected projection.
- `degree_centralization`: directed total-degree centralization normalized as `sum(max_degree - degree_i) / (2 * (nodes - 1) * (nodes - 2))`; use `0` when `nodes <= 2`.

## Running The Script

Use the bundled Python runtime when available. Example:

```powershell
& "<python>" "C:\Users\叶柯延\.codex\skills\sna-data-cleaning\scripts\build_sna_panel.py" `
  --input-csv "D:\path\xxxx记录.csv" `
  --city-reference "D:\path\市县简称对照.xlsx" `
  --output-dir "D:\path\outputs"
```

Optional arguments:
- `--prefix "xxxx"` to force output names.
- `--panel-output "D:\path\custom面板.csv"` to force panel path.
- `--metrics-output "D:\path\custom网络指标.csv"` to force metrics path.
- `--time-column`, `--city-a-column`, and `--city-b-column` to force source column mapping.
- `--valid-sheet`, `--exclude-sheet`, `--city-column`, and `--exclude-city-column` to force city reference workbook mapping.

After running, report:
- panel file path
- metrics file path
- input rows
- removed blank rows
- removed rows not in `Sheet1/城市`
- removed Hong Kong/Macau/Taiwan rows
- panel rows
- total `count`
- metrics year range

## Validation

Always verify that:
- Panel columns are `trans_time, city_A, city_B, count`.
- Sum of panel `count` equals the number of cleaned transfer rows.
- Metrics columns match the required schema.
- Ratio metrics are finite and within `[0, 1]`.
- Process files are not left behind unless the user asks for them.

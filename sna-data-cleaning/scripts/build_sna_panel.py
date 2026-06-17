#!/usr/bin/env python
"""Build a yearly city-pair transfer panel and annual SNA metrics."""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd


REQUIRED_COLUMNS = ["trans_time", "city_A", "city_B"]
PANEL_COLUMNS = ["trans_time", "city_A", "city_B", "count"]
METRIC_COLUMNS = [
    "year",
    "nodes",
    "edges",
    "density",
    "avg_degree",
    "avg_weighted_degree",
    "avg_clustering",
    "giant_component_ratio",
    "degree_centralization",
]

CSV_ENCODINGS = ["utf-8-sig", "utf-8", "gb18030", "gbk"]
VALID_SHEET_ALIASES = ["Sheet1", "大陆", "内地", "地级市", "城市"]
EXCLUDE_SHEET_ALIASES = ["港澳台", "港澳臺", "香港澳门台湾", "香港澳門臺灣"]
CITY_COLUMN_ALIASES = ["城市", "城市名称", "地级市", "市", "city", "City"]
DEFAULT_COLUMN_ALIASES = {
    "trans_time": [
        "trans_time",
        "year",
        "年份",
        "申请年份",
        "公开公告年份",
        "授权公告年份",
        "转让生效年份",
    ],
    "city_A": [
        "city_A",
        "source_city",
        "from_city",
        "申请人城市",
        "第一申请人城市",
        "转让人城市",
        "出让人城市",
    ],
    "city_B": [
        "city_B",
        "target_city",
        "to_city",
        "第二申请人城市",
        "受让人城市",
        "转入城市",
    ],
}


def strip_text(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def strip_series(series: pd.Series) -> pd.Series:
    return series.dropna().map(strip_text).loc[lambda s: s != ""]


def normalize_header(value: object) -> str:
    return strip_text(value).replace("\ufeff", "")


def choose_sheet(excel: pd.ExcelFile, explicit: str | None, aliases: list[str]) -> str:
    if explicit:
        if explicit not in excel.sheet_names:
            raise ValueError(
                f"Sheet '{explicit}' was not found. Available sheets: {excel.sheet_names}"
            )
        return explicit

    normalized = {normalize_header(name): name for name in excel.sheet_names}
    for alias in aliases:
        if alias in normalized:
            return normalized[alias]
    raise ValueError(
        f"Could not infer sheet. Tried aliases {aliases}. "
        f"Available sheets: {excel.sheet_names}"
    )


def choose_column(columns: list[str], explicit: str | None, aliases: list[str], label: str) -> str:
    normalized = {normalize_header(column): column for column in columns}
    if explicit:
        explicit = normalize_header(explicit)
        if explicit not in normalized:
            raise ValueError(
                f"Column '{explicit}' was not found for {label}. "
                f"Available columns: {columns}"
            )
        return normalized[explicit]

    for alias in aliases:
        if alias in normalized:
            return normalized[alias]
    raise ValueError(
        f"Could not infer {label} column. Tried aliases {aliases}. "
        f"Available columns: {columns}"
    )


def load_city_sets(
    reference_path: Path,
    valid_sheet: str | None = None,
    exclude_sheet: str | None = None,
    city_column: str | None = None,
    exclude_city_column: str | None = None,
) -> tuple[set[str], set[str], dict[str, str]]:
    excel = pd.ExcelFile(reference_path)
    valid_sheet_name = choose_sheet(excel, valid_sheet, VALID_SHEET_ALIASES)
    exclude_sheet_name = choose_sheet(excel, exclude_sheet, EXCLUDE_SHEET_ALIASES)

    valid_df = pd.read_excel(excel, sheet_name=valid_sheet_name, dtype=str)
    exclude_df = pd.read_excel(excel, sheet_name=exclude_sheet_name, dtype=str)
    valid_city_col = choose_column(
        list(valid_df.columns), city_column, CITY_COLUMN_ALIASES, "valid city"
    )
    exclude_city_col = choose_column(
        list(exclude_df.columns),
        exclude_city_column or city_column,
        CITY_COLUMN_ALIASES,
        "excluded city",
    )

    metadata = {
        "valid_sheet": valid_sheet_name,
        "exclude_sheet": exclude_sheet_name,
        "valid_city_column": valid_city_col,
        "exclude_city_column": exclude_city_col,
    }
    return (
        set(strip_series(valid_df[valid_city_col])),
        set(strip_series(exclude_df[exclude_city_col])),
        metadata,
    )


def infer_prefix(input_csv: Path) -> str:
    stem = input_csv.stem
    return stem[:-2] if stem.endswith("记录") else stem


def sort_key(key: tuple[str, str, str]) -> tuple[int, str, str, str]:
    year = key[0]
    return (int(year) if year.isdigit() else 10**9, year, key[1], key[2])


def year_sort_key(year: str) -> tuple[int, str]:
    return (int(year) if year.isdigit() else 10**9, year)


def normalize_year(value: object) -> str:
    value = strip_text(value)
    try:
        as_float = float(value)
    except ValueError:
        return value
    if as_float.is_integer():
        return str(int(as_float))
    return value


def resolve_input_columns(
    fieldnames: list[str] | None,
    time_column: str | None,
    city_a_column: str | None,
    city_b_column: str | None,
) -> dict[str, str]:
    if not fieldnames:
        raise ValueError("Input CSV has no header row.")

    fields = {normalize_header(field): field for field in fieldnames}
    explicit = {
        "trans_time": time_column,
        "city_A": city_a_column,
        "city_B": city_b_column,
    }
    resolved: dict[str, str] = {}
    for target, explicit_name in explicit.items():
        if explicit_name:
            explicit_name = normalize_header(explicit_name)
            if explicit_name not in fields:
                raise ValueError(
                    f"Column '{explicit_name}' was not found in input CSV. "
                    f"Available columns: {fieldnames}"
                )
            resolved[target] = fields[explicit_name]
            continue
        for candidate in DEFAULT_COLUMN_ALIASES[target]:
            if candidate in fields:
                resolved[target] = fields[candidate]
                break
        if target not in resolved:
            raise ValueError(
                f"Missing required column for {target}. Tried aliases: "
                f"{DEFAULT_COLUMN_ALIASES[target]}. Available columns: {fieldnames}"
            )
    return resolved


def open_csv_with_fallback(path: Path) -> tuple[object, str]:
    last_error: UnicodeDecodeError | None = None
    for encoding in CSV_ENCODINGS:
        handle = path.open("r", encoding=encoding, newline="")
        try:
            handle.peek if False else None
            handle.read(4096)
            handle.seek(0)
            return handle, encoding
        except UnicodeDecodeError as error:
            handle.close()
            last_error = error
    raise UnicodeDecodeError(
        last_error.encoding if last_error else "unknown",
        last_error.object if last_error else b"",
        last_error.start if last_error else 0,
        last_error.end if last_error else 0,
        f"Could not decode CSV with encodings {CSV_ENCODINGS}",
    )


def build_panel(
    input_csv: Path,
    panel_output: Path,
    main_cities: set[str],
    hmt_cities: set[str],
    time_column: str | None = None,
    city_a_column: str | None = None,
    city_b_column: str | None = None,
) -> dict[str, object]:
    counts: Counter[tuple[str, str, str]] = Counter()
    stats: dict[str, object] = {
        "input_rows": 0,
        "removed_blank": 0,
        "removed_not_in_valid_city_set": 0,
        "removed_in_excluded_city_set": 0,
        "cleaned_rows": 0,
    }

    handle, csv_encoding = open_csv_with_fallback(input_csv)
    stats["csv_encoding"] = csv_encoding
    with handle:
        reader = csv.DictReader(handle)
        columns = resolve_input_columns(
            reader.fieldnames, time_column, city_a_column, city_b_column
        )
        stats["resolved_columns"] = columns

        for row in reader:
            stats["input_rows"] = int(stats["input_rows"]) + 1
            trans_time = normalize_year(row.get(columns["trans_time"]))
            city_a = strip_text(row.get(columns["city_A"]))
            city_b = strip_text(row.get(columns["city_B"]))
            if not trans_time or not city_a or not city_b:
                stats["removed_blank"] = int(stats["removed_blank"]) + 1
                continue
            if city_a not in main_cities or city_b not in main_cities:
                stats["removed_not_in_valid_city_set"] = (
                    int(stats["removed_not_in_valid_city_set"]) + 1
                )
                continue
            if city_a in hmt_cities or city_b in hmt_cities:
                stats["removed_in_excluded_city_set"] = (
                    int(stats["removed_in_excluded_city_set"]) + 1
                )
                continue
            counts[(trans_time, city_a, city_b)] += 1
            stats["cleaned_rows"] = int(stats["cleaned_rows"]) + 1

    panel_output.parent.mkdir(parents=True, exist_ok=True)
    with panel_output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(PANEL_COLUMNS)
        for key in sorted(counts, key=sort_key):
            writer.writerow([*key, counts[key]])

    stats["panel_rows"] = len(counts)
    stats["panel_count_sum"] = sum(counts.values())
    return stats


def average_clustering(nodes: set[str], adjacency: dict[str, set[str]]) -> float:
    if not nodes:
        return 0.0
    total = 0.0
    for node in nodes:
        neighbors = list(adjacency.get(node, set()))
        degree = len(neighbors)
        if degree < 2:
            continue
        links = 0
        for index, first in enumerate(neighbors):
            for second in neighbors[index + 1 :]:
                if second in adjacency.get(first, set()):
                    links += 1
        total += (2.0 * links) / (degree * (degree - 1))
    return total / len(nodes)


def giant_component_ratio(nodes: set[str], adjacency: dict[str, set[str]]) -> float:
    if not nodes:
        return 0.0
    seen: set[str] = set()
    best = 0
    for start in nodes:
        if start in seen:
            continue
        stack = [start]
        seen.add(start)
        size = 0
        while stack:
            node = stack.pop()
            size += 1
            for neighbor in adjacency.get(node, set()):
                if neighbor not in seen:
                    seen.add(neighbor)
                    stack.append(neighbor)
        best = max(best, size)
    return best / len(nodes)


def calculate_metrics(panel_csv: Path, metrics_output: Path) -> dict[str, object]:
    year_rows: dict[str, list[tuple[str, str, int]]] = defaultdict(list)
    with panel_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != PANEL_COLUMNS:
            raise ValueError(f"Unexpected panel columns: {reader.fieldnames}")
        for row in reader:
            year = strip_text(row.get("trans_time"))
            city_a = strip_text(row.get("city_A"))
            city_b = strip_text(row.get("city_B"))
            count = int(float(strip_text(row.get("count"))))
            if year and city_a and city_b and count > 0:
                year_rows[year].append((city_a, city_b, count))

    output_rows: list[dict[str, object]] = []
    for year in sorted(year_rows, key=year_sort_key):
        nodes: set[str] = set()
        directed_edges: set[tuple[str, str]] = set()
        in_degree: defaultdict[str, int] = defaultdict(int)
        out_degree: defaultdict[str, int] = defaultdict(int)
        weighted_degree: defaultdict[str, int] = defaultdict(int)
        adjacency: defaultdict[str, set[str]] = defaultdict(set)

        for city_a, city_b, count in year_rows[year]:
            nodes.add(city_a)
            nodes.add(city_b)
            if city_a == city_b:
                continue
            edge = (city_a, city_b)
            if edge not in directed_edges:
                directed_edges.add(edge)
                out_degree[city_a] += 1
                in_degree[city_b] += 1
                adjacency[city_a].add(city_b)
                adjacency[city_b].add(city_a)
            weighted_degree[city_a] += count
            weighted_degree[city_b] += count

        node_count = len(nodes)
        edge_count = len(directed_edges)
        density = edge_count / (node_count * (node_count - 1)) if node_count > 1 else 0.0
        avg_degree = (
            sum(in_degree[node] + out_degree[node] for node in nodes) / node_count
            if node_count
            else 0.0
        )
        avg_weighted_degree = (
            sum(weighted_degree[node] for node in nodes) / node_count if node_count else 0.0
        )
        degrees = [in_degree[node] + out_degree[node] for node in nodes]
        if node_count > 2 and degrees:
            max_degree = max(degrees)
            degree_centralization = sum(max_degree - degree for degree in degrees) / (
                2 * (node_count - 1) * (node_count - 2)
            )
        else:
            degree_centralization = 0.0

        output_rows.append(
            {
                "year": year,
                "nodes": node_count,
                "edges": edge_count,
                "density": density,
                "avg_degree": avg_degree,
                "avg_weighted_degree": avg_weighted_degree,
                "avg_clustering": average_clustering(nodes, adjacency),
                "giant_component_ratio": giant_component_ratio(nodes, adjacency),
                "degree_centralization": degree_centralization,
            }
        )

    metrics_output.parent.mkdir(parents=True, exist_ok=True)
    with metrics_output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=METRIC_COLUMNS)
        writer.writeheader()
        for row in output_rows:
            formatted = dict(row)
            for col in METRIC_COLUMNS[3:]:
                formatted[col] = f"{float(row[col]):.10f}"
            writer.writerow(formatted)

    bad_values = 0
    for row in output_rows:
        for col in METRIC_COLUMNS[3:]:
            value = float(row[col])
            if not math.isfinite(value):
                bad_values += 1
        for col in [
            "density",
            "avg_clustering",
            "giant_component_ratio",
            "degree_centralization",
        ]:
            value = float(row[col])
            if value < -1e-12 or value > 1 + 1e-12:
                bad_values += 1

    years = [str(row["year"]) for row in output_rows]
    return {
        "metric_rows": len(output_rows),
        "year_min": min(years, key=year_sort_key) if years else None,
        "year_max": max(years, key=year_sort_key) if years else None,
        "bad_metric_values": bad_values,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Clean transfer records into an SNA panel and yearly network metrics."
    )
    parser.add_argument("--input-csv", required=True, type=Path)
    parser.add_argument("--city-reference", required=True, type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--prefix")
    parser.add_argument("--panel-output", type=Path)
    parser.add_argument("--metrics-output", type=Path)
    parser.add_argument("--time-column")
    parser.add_argument("--city-a-column")
    parser.add_argument("--city-b-column")
    parser.add_argument("--valid-sheet")
    parser.add_argument("--exclude-sheet")
    parser.add_argument("--city-column")
    parser.add_argument("--exclude-city-column")
    return parser.parse_args()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    args = parse_args()
    input_csv = args.input_csv.resolve()
    city_reference = args.city_reference.resolve()
    output_dir = (args.output_dir or input_csv.parent).resolve()
    prefix = args.prefix or infer_prefix(input_csv)
    panel_output = (args.panel_output or output_dir / f"{prefix}面板.csv").resolve()
    metrics_output = (args.metrics_output or output_dir / f"{prefix}网络指标.csv").resolve()

    main_cities, hmt_cities, reference_metadata = load_city_sets(
        city_reference,
        valid_sheet=args.valid_sheet,
        exclude_sheet=args.exclude_sheet,
        city_column=args.city_column,
        exclude_city_column=args.exclude_city_column,
    )
    panel_stats = build_panel(
        input_csv,
        panel_output,
        main_cities,
        hmt_cities,
        args.time_column,
        args.city_a_column,
        args.city_b_column,
    )
    metric_stats = calculate_metrics(panel_output, metrics_output)

    summary = {
        "input_csv": str(input_csv),
        "city_reference": str(city_reference),
        "panel_output": str(panel_output),
        "metrics_output": str(metrics_output),
        "valid_city_count": len(main_cities),
        "excluded_city_count": len(hmt_cities),
        **reference_metadata,
        **panel_stats,
        **metric_stats,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

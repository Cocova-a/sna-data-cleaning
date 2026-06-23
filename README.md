# SNA 数据清洗 Codex Skill

把原始数据的城市关联记录，一键清洗成社会网络分析可用的“年份-城市对”面板，并自动计算年度网络指标。注意:本skill范围仅限中国内陆城市。

这个仓库提供了一个 Codex Skill，适合需要处理社会网络分析（SNA）数据的研究者，尤其是做技术转移、专利合作、城市创新网络、区域协同创新等方向的同学。

## 这个 Skill 能做什么

- 从原始 CSV 中识别年份、来源城市、目标城市字段。
- 删除年份或城市为空的无效记录。
- 根据城市对照表，清洗数据整理出城市名。
- 按“年份-城市 A-城市 B”汇总转移次数。
- 输出可直接用于 SNA 分析的城市对年度面板。
- 计算每年的整体网络指标。

## 适合谁使用

这个 Skill 适合：

- 社会网络分析（SNA）研究者；
- 城市网络、创新网络、区域经济研究者；
- 需要把原始记录整理成网络面板数据的学生和研究人员；
- 使用 Codex 辅助数据清洗和论文实证分析的人。

## 输入文件

### 1. 原始记录 CSV

原始 CSV 至少需要包含以下三类信息：

| 含义 | 推荐字段名 | 可识别的中文字段示例 |
| --- | --- | --- |
| 年份 | `trans_time` | `申请年份`、`公开公告年份`、`授权公告年份`、`转让生效年份` |
| 来源城市 | `city_A` | `申请人城市`、`第一申请人城市`、`转让人城市`、`出让人城市` |
| 目标城市 | `city_B` | `第二申请人城市`、`受让人城市`、`转入城市` |

### 2. 城市参考表 Excel

通常是类似 `市县简称对照.xlsx` 的文件。

建议包含：

- `Sheet1`：内地有效城市列表；
- `港澳台`：香港、澳门、台湾城市列表；
- 城市列名建议为 `城市`。

如果你的表名或列名不同，也可以在运行时手动指定。

## 输出结果

Skill 会默认生成两个 CSV 文件：

| 文件 | 内容 |
| --- | --- |
| `xxx面板.csv` | 年份-城市 A-城市 B 的转移次数面板 |
| `xxx网络指标.csv` | 每年的网络整体指标 |

面板文件字段：

```csv
trans_time,city_A,city_B,count
```

网络指标文件字段：

```csv
year,nodes,edges,density,avg_degree,avg_weighted_degree,avg_clustering,giant_component_ratio,degree_centralization
```

## 网络指标说明

- `nodes`：年度网络中的城市节点数；
- `edges`：年度网络中的有向城市连接数；
- `density`：有向网络密度；
- `avg_degree`：平均度；
- `avg_weighted_degree`：平均加权度；
- `avg_clustering`：平均聚类系数；
- `giant_component_ratio`：最大连通分量占比；
- `degree_centralization`：度中心势。

计算网络结构指标时，脚本会把 `city_A -> city_B` 视为有向边，把 `count` 视为边权重，并在结构指标中排除自循环。

## 安装到 Codex

把本仓库中的 skill 文件夹放到你的 Codex skills 目录中。

Windows 示例：

```text
C:\Users\你的用户名\.codex\skills\sna-data-cleaning
```

放好后，目录结构建议类似：

```text
sna-data-cleaning
├── SKILL.md
├── agents
│   └── openai.yaml
└── scripts
    └── build_sna_panel.py
```

之后在 Codex 里提出类似需求即可触发：

```text
帮我把这份技术转移记录清洗成 SNA 城市对面板，并计算年度网络指标。
```

## 使用示例

如果直接运行脚本，可以使用：

```powershell
python scripts\build_sna_panel.py `
  --input-csv "D:\data\人工智能技术专利转移记录.csv" `
  --city-reference "D:\data\市县简称对照.xlsx" `
  --output-dir "D:\data\outputs"
```

如果字段名比较特殊，可以手动指定：

```powershell
python scripts\build_sna_panel.py `
  --input-csv "D:\data\records.csv" `
  --city-reference "D:\data\市县简称对照.xlsx" `
  --output-dir "D:\data\outputs" `
  --time-column "申请年份" `
  --city-a-column "申请人城市" `
  --city-b-column "第二申请人城市"
```

运行后会输出处理摘要，包括输入行数、删除空值行数、删除非有效城市行数、面板行数、指标年份范围等信息。

## 依赖

主要依赖：

- Python 3；
- pandas；
- openpyxl。

如果通过 Codex 使用，通常可以让 Codex 调用当前环境中的 Python 来运行脚本。

## 注意事项

- 如果你的城市表 sheet 名或城市列名和默认值不同，请使用参数手动指定。
- 输出 CSV 使用 UTF-8 BOM 编码，通常可以直接用 Excel 打开。

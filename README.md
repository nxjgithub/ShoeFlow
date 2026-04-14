# 女鞋爆款视频解析与内容生产系统

这是一个面向女鞋电商短视频带货场景的内容生产与优化系统。项目当前处于从 0 到 1 的基础建设阶段，目标不是立即做“一键自动成片”，而是先建立可复用、可追溯、可验证的内容工业化链路。

系统的核心链路是：

1. 导入女鞋爆款视频样本
2. 解析视频结构、镜头、文案、OCR 与转写结果
3. 提炼可复用的内容模板
4. 标准化自家女鞋商品信息
5. 将模板适配到具体 SKU
6. 生成脚本、镜头清单和素材清单
7. 记录成片来源与发布表现
8. 用回流数据持续优化模板和规则

## 当前项目状态

当前仓库已经搭好最小工程基础：

- `src/gemeiqi/`：Python 源码骨架
- `examples/fixtures/`：可校验的样例业务数据
- `data/samples/`：本地样例素材索引
- `docs/`：架构、数据契约、路线图
- `tests/`：基础单元测试
- `AGENTS.md`：给 Codex/协作代理的项目工作说明

`temp_data/` 目录中保留了当前提供的原始样例素材，包括 1 个短视频和 2 张图片。代码和文档通过索引文件引用这些素材，不会移动原始文件。

## 快速开始

建议使用仓库内已有虚拟环境或 Python 3.11+。

```powershell
.\.venv\Scripts\python.exe -m gemeiqi.cli inspect-samples
.\.venv\Scripts\python.exe -m gemeiqi.cli validate-fixtures
.\.venv\Scripts\python.exe -m gemeiqi.cli bootstrap-demo
.\.venv\Scripts\python.exe -m gemeiqi.cli analyze-local-video --threshold 45 --min-segment 2
.\.venv\Scripts\python.exe -m gemeiqi.cli generate-script-drafts --template-file data/outputs/local_video_analysis_tuned/content_template_draft.json --output-dir regenerated_from_template
.\\.venv\\Scripts\\python.exe -m gemeiqi.cli prepare-seedance-plan --analysis-dir data/outputs/local_video_analysis_tuned --product-id sku_maryjane_001 --output-dir seedance_generation
.\\.venv\\Scripts\\python.exe -m gemeiqi.cli render-draft-video --analysis-dir data/outputs/local_video_analysis_tuned --product-id sku_loafer_001 --output-dir rendered_videos
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

`analyze-local-video` 会读取 `temp_data/4f9893387224c46272b063713119596f.mp4`，输出抽样帧、粗切片、独立视频片段和 HTML 预览页。

默认输出位置：

```text
data/outputs/local_video_analysis/
├── analysis.json
├── preview.html
├── frames/
└── segments/
```

如果你已经手工修改过模板草稿，可以直接重新生成脚本执行单，不需要再从视频开始分析：

```powershell
.\.venv\Scripts\python.exe -m gemeiqi.cli generate-script-drafts --template-file data/outputs/local_video_analysis_tuned/content_template_draft.json --output-dir regenerated_from_template
```

如果你已经拿到了爆款模板和商品脚本，并且要把片段交给 `Seedance 2.0` 生成，可先产出片段计划和请求模板：

```powershell
.\.venv\Scripts\python.exe -m gemeiqi.cli prepare-seedance-plan --analysis-dir data/outputs/local_video_analysis_tuned --product-id sku_maryjane_001 --output-dir seedance_generation
```

默认会输出：

```text
data/outputs/seedance_generation/sku_maryjane_001/
├── seedance_plan.json
├── seedance_summary.md
└── request_templates/
```

如果你已经具备 `Seedance 2.0` 的 API Key、Base URL 和可公网访问的商品图 URL，可以继续提交与轮询：

```powershell
$env:SEEDANCE_API_KEY = "你的 API Key"
$env:SEEDANCE_API_BASE_URL = "你的 Seedance API Base URL"
.\.venv\Scripts\python.exe -m gemeiqi.cli submit-seedance-plan --plan-file data/outputs/seedance_generation/sku_maryjane_001/seedance_plan.json
.\.venv\Scripts\python.exe -m gemeiqi.cli poll-seedance-tasks --tasks-file data/outputs/seedance_generation/sku_maryjane_001/seedance_tasks.json
```

如果你想基于已有片段和脚本执行单，快速合成一条可播放的视频草稿：

```powershell
.\.venv\Scripts\python.exe -m gemeiqi.cli render-draft-video --analysis-dir data/outputs/local_video_analysis_tuned --product-id sku_loafer_001 --output-dir rendered_videos
```

`render-draft-video` 只是本地预览渲染，不是 `Seedance 2.0` 的真实生成结果。

如果没有使用虚拟环境：

```powershell
$env:PYTHONPATH = "src"
python -m gemeiqi.cli validate-fixtures
```

## 目录结构

```text
.
├── AGENTS.md
├── README.md
├── docs/
├── data/
├── examples/
├── src/
└── tests/
```

## 当前最小落地路径

第一阶段建议只围绕 1 到 3 个 SKU 跑通链路：

1. 把 10 到 30 条女鞋爆款视频录入样本池
2. 先人工或半自动补齐结构化解析字段
3. 从解析结果沉淀第一版模板
4. 录入自家商品属性和卖点
5. 生成第一版脚本与素材清单
6. 人工剪辑出样片
7. 记录模板来源、脚本版本、商品版本和发布表现

## 设计原则

- 先模板化，再自动化
- 先结构迁移，不做表面模仿
- 先保证商品表达正确，再追求生成效果
- 先半自动闭环，再逐步提高自动化比例
- 用真实数据定义模板价值

详细路线见 [docs/ROADMAP.md](docs/ROADMAP.md)。

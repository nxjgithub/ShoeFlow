# 数据契约

本文档描述当前阶段最小数据对象。代码中的校验规则位于 `src/gemeiqi/contracts.py`。

## VideoSample

爆款视频样本对象。

必填字段：

- `id`
- `platform`
- `title`
- `source_type`
- `source`
- `category`
- `metrics`
- `tags`

建议字段：

- `caption`
- `author`
- `duration_seconds`
- `collected_at`
- `asset_refs`
- `notes`

## VideoAnalysis

视频结构化解析对象。

必填字段：

- `id`
- `sample_id`
- `summary`
- `hook_type`
- `primary_selling_points`
- `segments`

`segments` 中建议包含 `start`、`end`、`role`、`visual_focus`、`selling_point`、`copywriting`、`reusable`。

## ContentTemplate

爆款内容模板对象。

必填字段：

- `id`
- `name`
- `version`
- `source_analysis_ids`
- `platforms`
- `hook_type`
- `scene_structure`
- `selling_point_order`
- `copywriting_style`
- `product_variables`

模板必须保留来源解析 ID，避免失去追溯性。

## Product

女鞋商品标准化对象。

必填字段：

- `id`
- `name`
- `category`
- `shoe_type`
- `attributes`
- `primary_selling_points`
- `secondary_selling_points`
- `target_audience`
- `target_scenarios`
- `risk_notes`
- `asset_refs`

商品字段要服务内容生产，不只是商品资料归档。

## TemplateMatch

模板与商品适配结果。

必填字段：

- `id`
- `template_id`
- `product_id`
- `score`
- `matched_reasons`
- `warnings`
- `variable_mapping`

`score` 只是参考，必须同时保留可解释原因。

## ScriptOutput

脚本输出对象。

必填字段：

- `id`
- `template_id`
- `product_id`
- `platform`
- `title_options`
- `scenes`
- `material_checklist`
- `trace`

`trace` 至少记录模板和商品来源，后续要扩展到脚本版本、生成器版本和人工审核状态。

## PerformanceRecord

发布效果回流对象。

必填字段：

- `id`
- `script_id`
- `platform`
- `published_at`
- `metrics`
- `quality_review`
- `notes`

指标建议分为结果类、效率类和质量类三组，避免只看流量。

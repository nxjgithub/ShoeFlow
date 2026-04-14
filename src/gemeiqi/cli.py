"""项目骨架的命令行入口。"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

from gemeiqi.contracts import require_no_issues, validate_collection
from gemeiqi.dotenv import load_project_env
from gemeiqi.paths import FIXTURES_DIR, SAMPLES_DIR, ensure_output_dir, project_path
from gemeiqi.pipeline import build_script_output, score_template_for_product
from gemeiqi.repository import dump_json, load_json
from gemeiqi.seedance import (
    DEFAULT_ASPECT_RATIO,
    DEFAULT_MODEL,
    DEFAULT_RESOLUTION,
    GENERATION_PROFILE_PRODUCT,
    GENERATION_PROFILE_TRYON,
    build_client_from_env,
    build_seedance_plan,
    refresh_seedance_tasks,
    resolve_reference_images,
    submit_seedance_plan,
    write_request_templates,
    write_seedance_summary,
)
from gemeiqi.template_editor import load_template_from_markdown, write_template_editor_markdown
from gemeiqi.video_processing import analyze_local_video
from gemeiqi.video_renderer import render_script_video

FIXTURE_SPECS = {
    "video_sample": FIXTURES_DIR / "video_samples.json",
    "product": FIXTURES_DIR / "products.json",
    "template": FIXTURES_DIR / "templates.json",
    "performance_record": FIXTURES_DIR / "performance_records.json",
}


def main(argv: list[str] | None = None) -> int:
    load_project_env()
    parser = argparse.ArgumentParser(prog="gemeiqi")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("inspect-samples", help="查看本地样例素材索引")
    subparsers.add_parser("validate-fixtures", help="校验 examples/fixtures 中的业务数据")

    demo_parser = subparsers.add_parser("bootstrap-demo", help="生成一份演示脚本输出")
    demo_parser.add_argument("--product-id", default="sku_loafer_001")
    demo_parser.add_argument("--template-id", default="tpl_commute_comfort_001")
    demo_parser.add_argument("--platform", default="douyin")
    demo_parser.add_argument("--output-dir", default="demo")

    video_parser = subparsers.add_parser("analyze-local-video", help="抽帧并生成本地视频粗切片")
    video_parser.add_argument(
        "--video",
        default="temp_data/4f9893387224c46272b063713119596f.mp4",
        help="本地视频路径",
    )
    video_parser.add_argument("--output-dir", default="local_video_analysis", help="输出目录名")
    video_parser.add_argument("--sample-id", default="vs_local_001", help="视频样本 ID")
    video_parser.add_argument("--interval", type=float, default=1.0, help="抽帧间隔，单位秒")
    video_parser.add_argument("--threshold", type=float, default=18.0, help="切片差异阈值")
    video_parser.add_argument("--min-segment", type=float, default=1.0, help="最短片段时长")
    video_parser.add_argument("--no-ocr", action="store_true", help="跳过 OCR 字幕识别")
    video_parser.add_argument(
        "--product-ids",
        nargs="*",
        default=[],
        help="指定要生成脚本草稿的商品 ID；为空时默认处理全部样例商品",
    )
    generate_parser = subparsers.add_parser(
        "generate-script-drafts",
        help="基于已有模板文件重新生成商品适配和脚本执行单",
    )
    generate_parser.add_argument(
        "--template-file",
        default="data/outputs/local_video_analysis_tuned/content_template_draft.json",
        help="模板 JSON 文件路径",
    )
    generate_parser.add_argument(
        "--output-dir",
        default="regenerated_script_drafts",
        help="输出目录名",
    )
    generate_parser.add_argument(
        "--product-ids",
        nargs="*",
        default=[],
        help="指定要生成脚本草稿的商品 ID；为空时默认处理全部样例商品",
    )
    editor_parser = subparsers.add_parser(
        "export-template-editor",
        help="把模板 JSON 导出为可人工修改的 Markdown 编辑卡",
    )
    editor_parser.add_argument(
        "--template-file",
        default="data/outputs/local_video_analysis_tuned/content_template_draft.json",
        help="模板 JSON 文件路径",
    )
    editor_parser.add_argument(
        "--output-file",
        default="data/outputs/local_video_analysis_tuned/template_editor.md",
        help="Markdown 编辑卡输出路径",
    )
    render_parser = subparsers.add_parser(
        "render-draft-video",
        help="基于脚本执行单和已有片段合成视频草稿",
    )
    render_parser.add_argument(
        "--analysis-dir",
        default="data/outputs/local_video_analysis_tuned",
        help="视频分析输出目录",
    )
    render_parser.add_argument(
        "--product-id",
        default="sku_loafer_001",
        help="要渲染的视频对应商品 ID",
    )
    render_parser.add_argument(
        "--script-file",
        default="",
        help="可选，直接指定 script_output.json 路径",
    )
    render_parser.add_argument(
        "--output-dir",
        default="rendered_videos",
        help="渲染结果输出目录名",
    )
    seedance_parser = subparsers.add_parser(
        "prepare-seedance-plan",
        help="把脚本执行单转换成 Seedance 2.0 片段生成计划",
    )
    seedance_parser.add_argument(
        "--analysis-dir",
        default="data/outputs/local_video_analysis_tuned",
        help="视频分析输出目录",
    )
    seedance_parser.add_argument(
        "--product-id",
        default="sku_maryjane_001",
        help="要生成视频片段的商品 ID",
    )
    seedance_parser.add_argument(
        "--script-file",
        default="",
        help="可选，直接指定 script_output.json 路径",
    )
    seedance_parser.add_argument(
        "--output-dir",
        default="seedance_generation",
        help="Seedance 计划输出目录名",
    )
    seedance_parser.add_argument(
        "--model",
        default=os.environ.get("SEEDANCE_MODEL", DEFAULT_MODEL),
        help="Seedance 模型标识",
    )
    seedance_parser.add_argument(
        "--aspect-ratio",
        default=DEFAULT_ASPECT_RATIO,
        help="视频比例，例如 9:16",
    )
    seedance_parser.add_argument(
        "--generation-profile",
        choices=[GENERATION_PROFILE_PRODUCT, GENERATION_PROFILE_TRYON],
        default=GENERATION_PROFILE_PRODUCT,
        help="Seedance 生成画像：product_showcase 保商品细节，model_tryon 生成模特试穿",
    )
    seedance_parser.add_argument(
        "--resolution",
        default=DEFAULT_RESOLUTION,
        help="视频分辨率，例如 1080p",
    )
    seedance_parser.add_argument(
        "--reference-images",
        nargs="*",
        default=[],
        help="显式指定商品参考图路径；为空时回退到商品 asset_refs",
    )
    seedance_parser.add_argument(
        "--public-reference-urls",
        nargs="*",
        default=[],
        help="可选，给 Seedance API 使用的公开参考图 URL",
    )
    seedance_parser.add_argument(
        "--watermark",
        action="store_true",
        help="请求 Seedance 时保留默认水印",
    )
    submit_seedance_parser = subparsers.add_parser(
        "submit-seedance-plan",
        help="把 Seedance 计划提交到视频生成 API",
    )
    submit_seedance_parser.add_argument(
        "--plan-file",
        default="data/outputs/seedance_generation/sku_maryjane_001/seedance_plan.json",
        help="Seedance 计划文件路径",
    )
    submit_seedance_parser.add_argument(
        "--api-base-url",
        default="",
        help="Seedance API Base URL；为空时从环境变量 SEEDANCE_API_BASE_URL 读取",
    )
    submit_seedance_parser.add_argument(
        "--include-high-risk",
        action="store_true",
        help="一并提交高风险片段",
    )
    submit_seedance_parser.add_argument(
        "--scene-indexes",
        nargs="*",
        type=int,
        default=[],
        help="只提交指定分镜序号，用于低成本验证，例如 2 5",
    )
    poll_seedance_parser = subparsers.add_parser(
        "poll-seedance-tasks",
        help="刷新 Seedance 任务状态",
    )
    poll_seedance_parser.add_argument(
        "--tasks-file",
        default="data/outputs/seedance_generation/sku_maryjane_001/seedance_tasks.json",
        help="Seedance 任务清单路径",
    )
    poll_seedance_parser.add_argument(
        "--api-base-url",
        default="",
        help="Seedance API Base URL；为空时从环境变量 SEEDANCE_API_BASE_URL 读取",
    )

    args = parser.parse_args(argv)

    if args.command == "inspect-samples":
        return inspect_samples()
    if args.command == "validate-fixtures":
        return validate_fixtures()
    if args.command == "bootstrap-demo":
        return bootstrap_demo(
            product_id=args.product_id,
            template_id=args.template_id,
            platform=args.platform,
            output_dir=args.output_dir,
        )
    if args.command == "analyze-local-video":
        return analyze_video_command(
            video=args.video,
            output_dir=args.output_dir,
            sample_id=args.sample_id,
            interval=args.interval,
            threshold=args.threshold,
            min_segment=args.min_segment,
            enable_ocr=not args.no_ocr,
            product_ids=args.product_ids,
        )
    if args.command == "generate-script-drafts":
        return generate_script_drafts_command(
            template_file=args.template_file,
            output_dir=args.output_dir,
            product_ids=args.product_ids,
        )
    if args.command == "export-template-editor":
        return export_template_editor_command(
            template_file=args.template_file,
            output_file=args.output_file,
        )
    if args.command == "render-draft-video":
        return render_draft_video_command(
            analysis_dir=args.analysis_dir,
            product_id=args.product_id,
            script_file=args.script_file,
            output_dir=args.output_dir,
        )
    if args.command == "prepare-seedance-plan":
        return prepare_seedance_plan_command(
            analysis_dir=args.analysis_dir,
            product_id=args.product_id,
            script_file=args.script_file,
            output_dir=args.output_dir,
            model=args.model,
            aspect_ratio=args.aspect_ratio,
            resolution=args.resolution,
            generation_profile=args.generation_profile,
            reference_images=args.reference_images,
            public_reference_urls=args.public_reference_urls,
            watermark=args.watermark,
        )
    if args.command == "submit-seedance-plan":
        return submit_seedance_plan_command(
            plan_file=args.plan_file,
            api_base_url=args.api_base_url,
            include_high_risk=args.include_high_risk,
            scene_indexes=args.scene_indexes,
        )
    if args.command == "poll-seedance-tasks":
        return poll_seedance_tasks_command(
            tasks_file=args.tasks_file,
            api_base_url=args.api_base_url,
        )

    parser.error(f"未知命令：{args.command}")
    return 2


def inspect_samples() -> int:
    sample_index = load_json(SAMPLES_DIR / "sample_assets.json")
    assets = sample_index.get("assets", [])

    print(sample_index.get("description", "样例素材索引"))
    for asset in assets:
        path = project_path(asset["path"])
        status = "存在" if path.exists() else "缺失"
        print(f"- {asset['id']} [{asset['kind']}] {asset['path']} ({status})")

    return 0


def validate_fixtures() -> int:
    all_issues = []
    for kind, path in FIXTURE_SPECS.items():
        records = _load_records(path)
        issues = validate_collection(kind, records)
        if issues:
            all_issues.extend(issues)
            print(f"{kind}: {len(issues)} 个问题")
            for issue in issues:
                print(f"  - {issue.format()}")
        else:
            print(f"{kind}: 通过（{len(records)} 条记录）")

    return 1 if all_issues else 0


def bootstrap_demo(
    product_id: str,
    template_id: str,
    platform: str,
    output_dir: str,
) -> int:
    products = _index_by_id(_load_records(FIXTURE_SPECS["product"]))
    templates = _index_by_id(_load_records(FIXTURE_SPECS["template"]))

    product = products[product_id]
    template = templates[template_id]

    require_no_issues("product", [product])
    require_no_issues("template", [template])

    match = score_template_for_product(template, product, platform)
    script_output = build_script_output(product, template, match, platform)

    target_dir = ensure_output_dir(output_dir)
    dump_json(target_dir / "template_match.json", match)
    dump_json(target_dir / "script_output.json", script_output)

    print(f"已生成：{_display_path(target_dir / 'template_match.json')}")
    print(f"已生成：{_display_path(target_dir / 'script_output.json')}")
    print(f"适配分：{match['score']}")
    return 0


def analyze_video_command(
    video: str,
    output_dir: str,
    sample_id: str,
    interval: float,
    threshold: float,
    min_segment: float,
    enable_ocr: bool,
    product_ids: list[str],
) -> int:
    video_path = project_path(video)
    if not video_path.exists():
        raise FileNotFoundError(f"视频文件不存在：{video_path}")

    target_dir = ensure_output_dir(output_dir)
    result = analyze_local_video(
        video_path=video_path,
        output_dir=target_dir,
        sample_id=sample_id,
        sample_interval_seconds=interval,
        scene_threshold=threshold,
        min_segment_seconds=min_segment,
        enable_ocr=enable_ocr,
    )
    generated_products = generate_script_drafts_for_products(
        output_dir=target_dir,
        product_ids=product_ids,
    )

    print(f"视频时长：{result['video']['duration_seconds']} 秒")
    print(f"抽样帧数：{len(result['frames'])}")
    print(f"粗切片数：{len(result['segments'])}")
    print(f"OCR：{'已启用' if enable_ocr else '已跳过'}")
    print(f"脚本草稿商品数：{generated_products}")
    print(f"分析结果：{_display_path(target_dir / 'analysis.json')}")
    print(f"解析草稿：{_display_path(target_dir / 'video_analysis_draft.json')}")
    print(f"模板草稿：{_display_path(target_dir / 'content_template_draft.json')}")
    print(f"模板摘要：{_display_path(target_dir / 'template_summary.md')}")
    print(f"模板编辑卡：{_display_path(target_dir / 'template_editor.md')}")
    print(f"脚本目录：{_display_path(target_dir / 'script_drafts')}")
    print(f"适配摘要：{_display_path(target_dir / 'script_drafts' / 'matches_summary.md')}")
    print(f"标注表：{_display_path(target_dir / 'segments_annotation.md')}")
    print(f"预览页面：{_display_path(target_dir / 'preview.html')}")
    return 0


def generate_script_drafts_command(
    template_file: str,
    output_dir: str,
    product_ids: list[str],
) -> int:
    template_path = _resolve_input_path(template_file)
    if not template_path.exists():
        raise FileNotFoundError(f"模板文件不存在：{template_path}")

    template = _load_template_file(template_path)
    target_dir = ensure_output_dir(output_dir)
    generated_products = generate_script_drafts_for_products(
        output_dir=target_dir,
        product_ids=product_ids,
        template=template,
    )

    dump_json(target_dir / "source_template.json", template)
    print(f"模板来源：{_display_path(template_path)}")
    print(f"脚本草稿商品数：{generated_products}")
    print(f"输出目录：{_display_path(target_dir)}")
    print(f"适配摘要：{_display_path(target_dir / 'script_drafts' / 'matches_summary.md')}")
    return 0


def export_template_editor_command(template_file: str, output_file: str) -> int:
    template_path = _resolve_input_path(template_file)
    if not template_path.exists():
        raise FileNotFoundError(f"模板文件不存在：{template_path}")

    template = _load_template_file(template_path)
    output_path = _resolve_output_path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_template_editor_markdown(output_path, template)
    print(f"模板来源：{_display_path(template_path)}")
    print(f"编辑卡输出：{_display_path(output_path)}")
    return 0


def render_draft_video_command(
    analysis_dir: str,
    product_id: str,
    script_file: str,
    output_dir: str,
) -> int:
    analysis_path = _resolve_input_path(analysis_dir)
    if not analysis_path.exists():
        raise FileNotFoundError(f"分析目录不存在：{analysis_path}")

    analysis = load_json(analysis_path / "analysis.json")
    if script_file:
        script_path = _resolve_input_path(script_file)
    else:
        script_path = analysis_path / "script_drafts" / product_id / "script_output.json"
    if not script_path.exists():
        raise FileNotFoundError(f"脚本文件不存在：{script_path}")

    products = _index_by_id(_load_records(FIXTURE_SPECS["product"]))
    product = products[product_id]
    script_output = load_json(script_path)

    target_dir = ensure_output_dir(output_dir, product_id)
    render_plan = render_script_video(
        analysis=analysis,
        script_output=script_output,
        product=product,
        analysis_dir=analysis_path,
        output_dir=target_dir,
    )

    print(f"分析目录：{_display_path(analysis_path)}")
    print(f"脚本来源：{_display_path(script_path)}")
    print(f"输出视频：{_display_path(Path(render_plan['output_video']))}")
    print(f"渲染计划：{_display_path(target_dir / 'render_plan.json')}")
    return 0


def prepare_seedance_plan_command(
    analysis_dir: str,
    product_id: str,
    script_file: str,
    output_dir: str,
    model: str,
    aspect_ratio: str,
    resolution: str,
    generation_profile: str,
    reference_images: list[str],
    public_reference_urls: list[str],
    watermark: bool,
) -> int:
    analysis_path = _resolve_input_path(analysis_dir)
    if not analysis_path.exists():
        raise FileNotFoundError(f"分析目录不存在：{analysis_path}")

    analysis = load_json(analysis_path / "analysis.json")
    if script_file:
        script_path = _resolve_input_path(script_file)
    else:
        script_path = analysis_path / "script_drafts" / product_id / "script_output.json"
    if not script_path.exists():
        raise FileNotFoundError(f"脚本文件不存在：{script_path}")

    products = _index_by_id(_load_records(FIXTURE_SPECS["product"]))
    product = products[product_id]
    script_output = load_json(script_path)
    resolved_images = resolve_reference_images(product, explicit_paths=reference_images)

    target_dir = ensure_output_dir(output_dir, product_id)
    plan = build_seedance_plan(
        analysis=analysis,
        script_output=script_output,
        product=product,
        reference_images=resolved_images,
        output_dir=target_dir,
        model=model,
        aspect_ratio=aspect_ratio,
        resolution=resolution,
        watermark=watermark,
        public_reference_urls=public_reference_urls,
        generation_profile=generation_profile,
    )
    dump_json(target_dir / "seedance_plan.json", plan)
    write_seedance_summary(target_dir / "seedance_summary.md", plan)
    write_request_templates(target_dir, plan)

    print(f"分析目录：{_display_path(analysis_path)}")
    print(f"脚本来源：{_display_path(script_path)}")
    print(f"参考图数量：{len(resolved_images)}")
    print(f"生成计划：{_display_path(target_dir / 'seedance_plan.json')}")
    print(f"计划摘要：{_display_path(target_dir / 'seedance_summary.md')}")
    print(f"请求模板目录：{_display_path(target_dir / 'request_templates')}")
    return 0


def submit_seedance_plan_command(
    plan_file: str,
    api_base_url: str,
    include_high_risk: bool,
    scene_indexes: list[int],
) -> int:
    plan_path = _resolve_input_path(plan_file)
    if not plan_path.exists():
        raise FileNotFoundError(f"Seedance 计划文件不存在：{plan_path}")

    plan = load_json(plan_path)
    client = build_client_from_env(api_base_url or None)
    result = submit_seedance_plan(
        plan=plan,
        output_dir=plan_path.parent,
        client=client,
        include_high_risk=include_high_risk,
        scene_indexes=scene_indexes,
    )
    print(f"计划来源：{_display_path(plan_path)}")
    print(f"任务清单：{_display_path(plan_path.parent / 'seedance_tasks.json')}")
    print(f"已处理片段数：{len(result.get('tasks', []))}")
    return 0


def poll_seedance_tasks_command(tasks_file: str, api_base_url: str) -> int:
    tasks_path = _resolve_input_path(tasks_file)
    if not tasks_path.exists():
        raise FileNotFoundError(f"Seedance 任务文件不存在：{tasks_path}")

    client = build_client_from_env(api_base_url or None)
    refreshed = refresh_seedance_tasks(tasks_path, client)
    print(f"任务文件：{_display_path(tasks_path)}")
    print(f"刷新时间：{refreshed.get('refreshed_at', '')}")
    for task in refreshed.get("tasks", []):
        task_id = task.get("task_id", "")
        latest_status = task.get("latest_status", task.get("status", ""))
        print(
            f"- scene {task.get('scene_index')} ({task.get('role')}) "
            f"task_id={task_id or 'N/A'} status={latest_status or 'unknown'}"
        )
    return 0


def generate_script_drafts_for_products(
    output_dir: Path,
    product_ids: list[str],
    template: dict[str, Any] | None = None,
) -> int:
    if template is None:
        template = load_json(output_dir / "content_template_draft.json")
    products = _load_records(FIXTURE_SPECS["product"])
    if product_ids:
        target_ids = set(product_ids)
        products = [product for product in products if product["id"] in target_ids]

    require_no_issues("template", [template])
    for product in products:
        require_no_issues("product", [product])

    script_dir = output_dir / "script_drafts"
    script_dir.mkdir(parents=True, exist_ok=True)

    summary_lines = [
        "# 商品适配与脚本草稿摘要",
        "",
        f"- 模板：`{template['id']}` {template['name']}",
        "",
        "| 商品 ID | 商品名 | 适配分 | 匹配原因 | 主要警告 | 脚本文件 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]

    for product in products:
        match = score_template_for_product(template, product, "douyin")
        script_output = build_script_output(product, template, match, "douyin")
        product_dir = script_dir / product["id"]
        product_dir.mkdir(parents=True, exist_ok=True)
        dump_json(product_dir / "template_match.json", match)
        dump_json(product_dir / "script_output.json", script_output)
        write_script_markdown(product_dir / "script_output.md", product, match, script_output)

        summary_lines.append(
            "| "
            f"{product['id']} | "
            f"{product['name']} | "
            f"{match['score']} | "
            f"{'<br>'.join(match['matched_reasons']) or '待人工补充'} | "
            f"{'<br>'.join(match['warnings']) or '无'} | "
            f"`script_drafts/{product['id']}/script_output.md` |"
        )

    (script_dir / "matches_summary.md").write_text(
        "\n".join(summary_lines) + "\n",
        encoding="utf-8",
    )
    return len(products)


def write_script_markdown(
    path: Path,
    product: dict[str, Any],
    match: dict[str, Any],
    script_output: dict[str, Any],
) -> None:
    lines = [
        "# 脚本草稿",
        "",
        f"- 商品：`{product['id']}` {product['name']}",
        f"- 适配分：`{match['score']}`",
        f"- 模板：`{script_output['template_id']}`",
        "",
        "## 匹配原因",
        "",
    ]
    for reason in match.get("matched_reasons", []):
        lines.append(f"- {reason}")
    if not match.get("matched_reasons"):
        lines.append("- 待人工补充")

    lines.extend(["", "## 风险提示", ""])
    for warning in match.get("warnings", []):
        lines.append(f"- {warning}")
    if not match.get("warnings"):
        lines.append("- 无")

    lines.extend(["", "## 标题候选", ""])
    for title in script_output.get("title_options", []):
        lines.append(f"- {title}")

    lines.extend(["", "## 剪辑备注", ""])
    for note in script_output.get("editing_notes", []):
        lines.append(f"- {note}")

    lines.extend(["", "## 分镜脚本", ""])
    for scene in script_output.get("scenes", []):
        lines.extend(
            [
                f"### 第 {scene['index']} 段 · {scene['role']}",
                "",
                f"- 时长：{scene['duration_seconds']} 秒",
                f"- 镜头类型：{scene.get('shot_type', '')}",
                f"- 建议产出方式：{scene.get('production_mode', '')}",
                f"- 景别：{scene.get('framing', '')}",
                f"- 机位：{scene.get('camera_angle', '')}",
                f"- 镜头动作：{scene.get('camera_motion', '')}",
                f"- 画面主体：{scene.get('subject_focus', '')}",
                f"- 素材来源建议：{scene.get('asset_source_suggestion', '')}",
                f"- 目标：{scene['goal']}",
                f"- 片段卖点：{scene.get('selling_point', '') or '待人工补充'}",
                f"- 建议字幕：{scene.get('subtitle_suggestion', '')}",
                f"- 建议口播：{scene.get('narration_suggestion', '')}",
                f"- 文案提示：{scene['copywriting_prompt']}",
                f"- 模板参考：{'；'.join(scene.get('template_examples', [])) or '无'}",
                f"- 复用提示：{scene.get('reusable_hint', '') or '无'}",
                f"- 画面要求：{'；'.join(scene['visual_requirements'])}",
                f"- 风险控制：{'；'.join(scene['risk_control']) or '无'}",
                f"- 执行备注：{'；'.join(scene.get('execution_notes', [])) or '无'}",
                "",
            ]
        )

    lines.extend(["## 素材清单", ""])
    for item in script_output.get("material_checklist", []):
        status = "必需" if item.get("required") else "可选"
        lines.append(f"- [{status}] {item['name']}（{item['source']}）")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _resolve_input_path(path_value: str) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return project_path(path_value)


def _resolve_output_path(path_value: str) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return project_path(path_value)


def _load_template_file(path: Path) -> dict[str, Any]:
    if path.suffix.lower() == ".md":
        return load_template_from_markdown(path)
    return load_json(path)


def _load_records(path: Path) -> list[dict[str, Any]]:
    records = load_json(path)
    if not isinstance(records, list):
        raise TypeError(f"{path} 必须包含一个 JSON 列表")
    return records


def _index_by_id(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {record["id"]: record for record in records}


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(Path.cwd()))
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())

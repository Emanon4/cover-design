"""Mechanical checks for real files and review records. No OCR or aesthetic claims."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from validate_cover_plan import Report, normalize_title

REVIEW_KEYS = ("title", "identity", "interaction", "evidence_truth", "thumbnail", "crop")
STATUSES = {"通过", "需修改", "待验证", "不适用"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_file(root: Path, value: object, report: Report, label: str) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        report.errors.append(f"{label} 缺少文件路径")
        return None
    path = Path(value)
    path = path if path.is_absolute() else root / path
    if not path.is_file():
        report.errors.append(f"{label} 文件不存在：{value}")
        return None
    return path.resolve()


def inspect_image(path: Path | None, report: Report, label: str) -> tuple[int, int] | None:
    if path is None:
        return None
    from PIL import Image
    try:
        with Image.open(path) as im:
            im.verify()
        with Image.open(path) as im:
            return im.size
    except (OSError, ValueError, Image.DecompressionBombError) as exc:
        report.errors.append(f"{label} 无法解码为完整图片：{exc}")
        return None


def check_review(
    value: object, key: str, root: Path, report: Report, ready: bool,
    allow_na: bool = False,
) -> list[Path]:
    if not isinstance(value, dict):
        report.errors.append(f"{key} 缺少审阅记录")
        return []
    status = value.get("status")
    report.require(status in STATUSES, f"{key} 审阅状态无效")
    basis = value.get("basis")
    report.require(isinstance(basis, str) and bool(basis.strip()), f"{key} 缺少观察依据或待验证原因")
    evidence = value.get("evidence", [])
    if not isinstance(evidence, list):
        report.errors.append(f"{key} evidence 必须为文件路径列表")
        return []
    paths = [path for item in evidence if (path := resolve_file(root, item, report, key))]
    if status == "通过":
        report.require(bool(paths), f"{key} 通过但没有实际查看的文件")
    elif status == "不适用":
        report.require(allow_na, f"{key} 不能标为不适用")
    elif status in {"待验证", "需修改"}:
        message = f"{key}：{status}"
        (report.errors if ready else report.warnings).append(message)
    return paths


def check_artifacts(manifest_path: Path, plan: dict, report: Report, ready: bool = False) -> None:
    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        report.errors.append("成片图片检查需要 Pillow；先安装 requirements.txt，方案检查无需此依赖")
        return
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        report.errors.append(f"无法读取成片清单：{exc}")
        return
    if not isinstance(manifest, dict):
        report.errors.append("成片清单必须为 JSON 对象")
        return
    root = manifest_path.resolve().parent
    report.require(manifest.get("schema_version") == 2, "成片清单 schema_version 应为 2")
    canvas = manifest.get("canvas")
    valid_canvas = (
        isinstance(canvas, list) and len(canvas) == 2
        and all(type(n) is int and n > 0 for n in canvas)
    )
    report.require(valid_canvas, "成片清单 canvas 应为两个正整数")
    if valid_canvas:
        report.require(tuple(canvas) == plan.get("canvas"), "成片清单画布与方案不一致")
    variants = manifest.get("variants")
    if not isinstance(variants, list) or not variants:
        report.errors.append("成片清单缺少 variants 列表")
        return
    schemes = plan.get("schemes", {})
    seen: set[str] = set()
    for item in variants:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            report.errors.append("每个成片需要对象格式和字符串 id")
            continue
        label = item["id"]
        report.require(label in schemes, f"成片 {label} 不在方案中")
        report.require(label not in seen, f"成片 {label} 重复")
        seen.add(label)
        image_path = resolve_file(root, item.get("image"), report, f"{label} 成片")
        size = inspect_image(image_path, report, f"{label} 成片")
        if size and valid_canvas:
            report.require(size == tuple(canvas), f"{label} 实际尺寸 {size} 不匹配画布 {canvas}")
        if image_path:
            report.require(
                item.get("reviewed_sha256") == sha256(image_path),
                f"{label} 审阅哈希与当前图片不一致；修改后须重新审阅",
            )
        transcription = item.get("title_transcription")
        report.require(isinstance(transcription, str), f"{label} 缺少实际标题抄录")
        if isinstance(transcription, str) and label in schemes:
            report.require(
                normalize_title(transcription) == normalize_title(schemes[label].get("封面短句", "")),
                f"{label} 成片标题抄录与方案不一致",
            )

        thumbnail = resolve_file(root, item.get("thumbnail"), report, f"{label} 缩略图")
        thumb_size = inspect_image(thumbnail, report, f"{label} 缩略图")
        if size and thumb_size:
            report.require(thumb_size[0] <= 360, f"{label} 缩略图过大，需查看手机单卡尺度")
            ratio_error = abs(thumb_size[1] - thumb_size[0] * size[1] / size[0])
            report.require(ratio_error <= 1.1, f"{label} 缩略图比例被拉伸")
        crops = item.get("crops")
        crop_paths: list[Path] = []
        if not isinstance(crops, list) or not crops:
            report.errors.append(f"{label} 缺少目标或模拟裁切预览")
        else:
            for crop in crops:
                if not isinstance(crop, dict):
                    report.errors.append(f"{label} 裁切条目必须为对象")
                    continue
                scene = crop.get("scene")
                report.require(isinstance(scene, str) and bool(scene.strip()), f"{label} 裁切缺少展示场景")
                crop_path = resolve_file(root, crop.get("file"), report, f"{label} 裁切")
                inspect_image(crop_path, report, f"{label} 裁切")
                if crop_path:
                    crop_paths.append(crop_path)
        reviews = item.get("reviews")
        if not isinstance(reviews, dict):
            report.errors.append(f"{label} 缺少 reviews 对象")
            continue
        for key in REVIEW_KEYS:
            review = reviews.get(key)
            paths = check_review(
                review, f"{label}.{key}", root, report, ready,
                allow_na=(key == "identity" and item.get("has_presenter") is False),
            )
            if not isinstance(review, dict) or review.get("status") != "通过":
                continue
            if key in {"title", "identity", "interaction", "evidence_truth"} and image_path:
                report.require(image_path in paths, f"{label}.{key} 未绑定当前成片")
            if key == "identity":
                report.require(any(path != image_path for path in paths), f"{label}.identity 缺少人物参考文件")
            if key == "thumbnail":
                report.require(thumbnail in paths, f"{label}.thumbnail 未查看指定缩略图")
            if key == "crop":
                report.require(
                    bool(crop_paths) and all(path in paths for path in crop_paths),
                    f"{label}.crop 未查看全部指定裁切",
                )
        if ready and schemes.get(label, {}).get("素材性质") == "待补素材":
            report.errors.append(f"{label} 仍缺少主要证据素材，不能标记准备发布")

    missing = set(schemes) - seen
    if missing:
        message = "未交付方案：" + "、".join(sorted(missing))
        if ready and plan.get("inputs", {}).get("工作模式") == "单变量测试":
            report.errors.append(message)
        else:
            report.warnings.append(message + "；仅检查本次交付部分")
    opening = manifest.get("opening")
    paths = check_review(opening, "opening", root, report, ready)
    if isinstance(opening, dict) and opening.get("status") == "通过":
        report.require(
            plan.get("inputs", {}).get("开场依据状态") == "成片已核验",
            "开场通过但方案未更新为成片已核验",
        )
        source = opening.get("source")
        report.require(isinstance(source, str) and bool(source.strip()), "开场通过需记录实际视频来源")
        time_range = opening.get("time_range")
        valid_range = (
            isinstance(time_range, list) and len(time_range) == 2
            and all(type(n) in (int, float) for n in time_range)
            and 0 <= time_range[0] < time_range[1]
        )
        report.require(valid_range, "开场通过需记录实际秒数区间")
        report.require(bool(paths), "实际开场缺少审阅证据")
    elif plan.get("inputs", {}).get("开场依据状态") == "成片已核验":
        report.errors.append("方案称开场已核验，但成片清单没有对应通过记录")

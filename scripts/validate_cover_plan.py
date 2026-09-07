#!/usr/bin/env python3
"""Validate a v2 cover plan; optionally inspect artifacts, never auto-grade aesthetics."""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIELD_RE = re.compile(r"^\s*-\s*([^：:]+)[：:]\s*(.*?)\s*$")
HEADING_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
PLACEHOLDER_RE = re.compile(r"^(?:TODO|TBD|待补|待定|[-—]+|<[^>]+>)$", re.I)
INPUT_FIELDS = (
    "方案版本", "工作模式", "目标账号", "账号定位版本", "核心判断", "封面承诺",
    "内容依据", "开场依据状态", "开场兑现点", "标题策略", "画布", "展示场景",
)
SCHEME_FIELDS = (
    "封面短句", "点击动机", "视觉家族", "人物目标", "人物动词", "作用对象",
    "可见结果", "人物设计", "主要证据关系", "素材性质", "素材来源",
    "真实性边界", "构图与镜头",
)
STATIC_ACTIONS = {
    "站立", "站着", "出镜", "微笑", "摆姿势", "摆拍", "无", "站立微笑", "站着微笑",
}
MODES = {"单稿", "概念探索", "单变量测试"}
SOURCE_TYPES = {"实拍", "真实截图", "官方素材", "生成示意", "混合", "待补素材"}
OPENING_STATES = {"脚本已有", "建议补拍", "成片已核验", "待提供"}
# These are declared changes. Image review still must verify the actual fixed conditions.
TEST_VARIABLES = {
    "封面短句": {"封面短句", "排版换行", "点击动机"},
    "人物动作": {"人物动词", "作用对象", "可见结果", "人物设计"},
    "证据占比": {"证据占比", "构图与镜头"},
}
NARRATIVE_FIELDS = (
    "封面短句", "视觉家族", "人物目标", "人物动词", "作用对象", "可见结果", "主要证据关系",
)


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def require(self, condition: bool, message: str) -> None:
        if not condition:
            self.errors.append(message)

    def as_dict(self) -> dict:
        return {"ok": not self.errors, "errors": self.errors, "warnings": self.warnings}


def normalize_title(value: str) -> str:
    """Ignore visual whitespace only; punctuation, English and numbers are invariants."""
    return re.sub(r"\s+", "", unicodedata.normalize("NFC", value))


def empty(value: str) -> bool:
    return not value.strip() or bool(PLACEHOLDER_RE.fullmatch(value.strip()))


def parse_plan(text: str, report: Report) -> tuple[dict, dict, dict]:
    headings = list(HEADING_RE.finditer(text))
    sections: dict[str, dict[str, str]] = {}
    for i, match in enumerate(headings):
        name = match[1].strip()
        report.require(name not in sections, f"重复章节：{name}")
        end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        fields: dict[str, str] = {}
        for line in text[match.end():end].splitlines():
            field = FIELD_RE.match(line)
            if field:
                key, value = field[1].strip(), field[2].strip()
                report.require(key not in fields, f"{name} 重复字段：{key}")
                fields[key] = value
        sections[name] = fields
    schemes = {
        match[1]: fields
        for name, fields in sections.items()
        if (match := re.fullmatch(r"方案\s+([A-Z])", name))
    }
    return sections.get("输入判断", {}), schemes, sections


def require_fields(fields: dict, names: tuple, context: str, report: Report) -> None:
    for name in names:
        report.require(not empty(fields.get(name, "")), f"{context} 缺少有效字段：{name}")


def check_plan(text: str) -> tuple[Report, dict]:
    report = Report()
    inputs, schemes, sections = parse_plan(text, report)
    for section_name in ("验收", "验收记录"):
        for key, value in sections.get(section_name, {}).items():
            if re.match(r"^通过(?:[，。；\s]|$)", value):
                report.errors.append(f"{section_name}.{key} 不应在方案中预填通过；请绑定实际成片清单")
    require_fields(inputs, INPUT_FIELDS, "输入判断", report)
    report.require(inputs.get("方案版本") == "2", "需要方案版本 2；旧稿请按 output-template.md 迁移")
    mode = inputs.get("工作模式")
    report.require(mode in MODES, "工作模式应为单稿、概念探索或单变量测试")
    count = len(schemes)
    report.require(count > 0, "至少需要一套「## 方案 A」")
    if mode == "单稿":
        report.require(count == 1, "单稿模式只需一套方案")
    elif mode == "概念探索":
        report.require(count >= 2, "概念探索至少需要两套有叙事差异的方案")
    elif mode == "单变量测试":
        report.require(count == 2, "单变量测试需要两套对照方案")

    size_match = re.fullmatch(r"\s*(\d+)\s*[xX×]\s*(\d+)\s*", inputs.get("画布", ""))
    canvas = tuple(map(int, size_match.groups())) if size_match else None
    report.require(bool(canvas and min(canvas) > 0), "画布须为正整数宽×高，如 1080×1440")
    opening_state = inputs.get("开场依据状态")
    report.require(opening_state in OPENING_STATES, "开场依据状态无效")
    if opening_state == "成片已核验":
        require_fields(inputs, ("开场核验依据",), "实际开场", report)
    else:
        report.warnings.append("尚未核验实际开场；脚本衔接或补拍建议不是视频验收")
    title_policy = inputs.get("标题策略")
    report.require(title_policy in {"锁定", "可提案"}, "标题策略应为锁定或可提案")
    if title_policy == "锁定":
        require_fields(inputs, ("原始标题",), "标题锁定", report)

    fingerprints: dict[tuple, str] = {}
    for label, fields in schemes.items():
        require_fields(fields, SCHEME_FIELDS, f"方案 {label}", report)
        title = fields.get("封面短句", "")
        if title_policy == "锁定":
            report.require(
                normalize_title(title) == normalize_title(inputs.get("原始标题", "")),
                f"方案 {label} 改动了锁定标题（包括标点、数字或英文）",
            )
        if len(normalize_title(title)) > 24:
            report.warnings.append(f"方案 {label} 标题较长，请通过实际排版检查，勿擅改锁定文案")
        if re.search(r"震惊|炸裂|史诗级", title):
            report.warnings.append(f"方案 {label} 标题含刺激词，需核对具体内容；锁定标题不自动修改")
        action = re.sub(r"[\s，。！？、/／+＋与和]", "", fields.get("人物动词", ""))
        report.require(action not in STATIC_ACTIONS, f"方案 {label} 人物动词只是静态状态")
        source_type = fields.get("素材性质")
        report.require(source_type in SOURCE_TYPES, f"方案 {label} 素材性质无效")
        if source_type in {"生成示意", "混合", "待补素材"}:
            report.warnings.append(f"方案 {label} 含示意或待补素材，须视觉核对真实性边界")
        fingerprint = tuple(fields.get(key, "").strip() for key in NARRATIVE_FIELDS)
        if fingerprint in fingerprints:
            report.errors.append(f"方案 {label} 与 {fingerprints[fingerprint]} 无已声明的叙事差异")
        fingerprints[fingerprint] = label
        if mode == "概念探索":
            require_fields(fields, ("差异说明",), f"方案 {label}", report)

    if count > 1:
        recommendation = sections.get("推荐", {})
        require_fields(recommendation, ("推荐方案", "推荐理由"), "推荐", report)
        chosen = recommendation.get("推荐方案", "").removeprefix("方案").strip()
        report.require(chosen in schemes, "推荐方案必须指向已存在的方案编号")

    if mode == "单变量测试":
        test = sections.get("测试设计", {})
        require_fields(test, ("唯一变量", "固定条件", "对照条件", "指标口径"), "测试设计", report)
        variable = test.get("唯一变量")
        report.require(variable in TEST_VARIABLES, "支持的唯一变量：封面短句、人物动作或证据占比")
        for label, fields in schemes.items():
            require_fields(fields, ("变量取值",), f"方案 {label}", report)
            if variable == "证据占比":
                require_fields(fields, ("证据占比",), f"方案 {label}", report)
        if count == 2 and variable in TEST_VARIABLES:
            left, right = schemes.values()
            report.require(left.get("变量取值") != right.get("变量取值"), "测试的两个变量取值相同")
            compared = set(SCHEME_FIELDS) | {"排版换行", "证据占比"}
            changed = {key for key in compared if left.get(key) != right.get(key)}
            allowed = TEST_VARIABLES[variable]
            report.require(bool(changed & allowed), "所选变量没有实际声明变化")
            report.require(not changed - allowed, "单变量测试同时改变了固定字段：" + "、".join(sorted(changed - allowed)))
        report.warnings.append("单变量字段检查不验证图片相同条件，也不证明发布数据可因果归因")

    return report, {"inputs": inputs, "schemes": schemes, "canvas": canvas}


def validate(text: str) -> list[str]:
    """Keep the old callable shape while requiring explicit migration to schema v2."""
    return check_plan(text)[0].errors


def self_test() -> int:
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern="test_*.py")
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    return 0 if result.wasSuccessful() else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", type=Path, help="v2 Markdown plan")
    parser.add_argument("--artifacts", type=Path, help="Manifest of actual files and review records")
    parser.add_argument("--ready", action="store_true", help="Require completed visual and actual opening reviews")
    parser.add_argument("--json", action="store_true", help="Structured report; warnings do not imply failure")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    if args.path is None or (args.ready and args.artifacts is None):
        parser.error("需要方案路径；--ready 还需要 --artifacts")
    try:
        text = args.path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        print(f"无法读取方案：{exc}", file=sys.stderr)
        return 2
    report, plan = check_plan(text)
    stage = "方案字段校验（未验证成片）"
    if args.artifacts:
        from validate_artifacts import check_artifacts
        check_artifacts(args.artifacts, plan, report, ready=args.ready)
        stage = "发布前记录核对" if args.ready else "成片文件与审阅记录核对"
    if args.json:
        print(json.dumps({"stage": stage, **report.as_dict()}, ensure_ascii=False, indent=2))
    else:
        for error in report.errors:
            print(f"ERROR: {error}")
        for warning in report.warnings:
            print(f"WARN: {warning}")
        print(f"{stage}：{'失败' if report.errors else '通过'}")
        if args.artifacts:
            print("文件与记录检查不替代实际视觉审阅，也不证明点击或留存效果。")
    return 1 if report.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

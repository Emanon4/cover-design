#!/usr/bin/env python3
"""Validate a cover-design Markdown delivery before generation or publishing."""

from __future__ import annotations

import argparse
import re
import sys
import tempfile
from pathlib import Path


FIELD_RE = re.compile(r"^\s*-\s*([^：:]+)[：:]\s*(.*?)\s*$")
SCHEME_RE = re.compile(r"^##\s+方案\s+([ABC])\s*$", re.MULTILINE)
PLACEHOLDER_RE = re.compile(r"^(?:待补|待定|TODO|TBD|N/?A|[-—]+|\[[^\]]*\]|<[^>]*>)$", re.I)

INPUT_FIELDS = (
    "目标账号",
    "账号定位版本",
    "选题",
    "核心判断",
    "点击后可兑现的回答",
    "可见证据",
    "素材缺口",
    "采用的账号视觉指纹",
    "明确不采用的参考元素",
)
SCHEME_FIELDS = (
    "结构类型",
    "封面短句",
    "一眼先看见",
    "人物",
    "证据物",
    "构图",
    "品牌元素",
    "色彩",
    "制作说明",
    "动效转静态说明",
    "风险",
)
EXECUTION_FIELDS = (
    "画布",
    "安全区",
    "标题坐标与最大宽度",
    "人物占比与锚点",
    "证据物占比与锚点",
    "品牌角标",
    "字级关系",
    "合成层级",
    "需要补拍或补生成的素材",
    "参考图绑定",
    "固定提示词",
    "本轮单一变量",
    "负面约束",
    "生图底图提示词",
    "后期排版说明",
    "最终输出",
)


def field_map(text: str) -> dict[str, str]:
    return {
        match.group(1).strip(): match.group(2).strip()
        for line in text.splitlines()
        if (match := FIELD_RE.match(line))
    }


def section(text: str, heading: str, next_heading_level: int = 2) -> str:
    pattern = re.compile(
        rf"^{re.escape(heading)}\s*$\n(.*?)(?=^{'#' * next_heading_level}\s+|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(text)
    return match.group(1) if match else ""


def missing_or_placeholder(value: str) -> bool:
    return not value or bool(PLACEHOLDER_RE.fullmatch(value.strip()))


def validate(text: str) -> list[str]:
    errors: list[str] = []
    inputs = field_map(section(text, "## 输入判断"))
    for name in INPUT_FIELDS:
        if missing_or_placeholder(inputs.get(name, "")):
            errors.append(f"输入判断缺少有效字段：{name}")

    scheme_matches = list(SCHEME_RE.finditer(text))
    labels = [match.group(1) for match in scheme_matches]
    if labels != ["A", "B", "C"]:
        errors.append("必须按顺序包含且只包含「## 方案 A」「## 方案 B」「## 方案 C」")

    for index, match in enumerate(scheme_matches):
        label = match.group(1)
        end = scheme_matches[index + 1].start() if index + 1 < len(scheme_matches) else len(text)
        block = text[match.end() : end]
        fields = field_map(block)
        for name in SCHEME_FIELDS:
            if missing_or_placeholder(fields.get(name, "")):
                errors.append(f"方案 {label} 缺少有效字段：{name}")
        title = fields.get("封面短句", "")
        han_count = len(re.findall(r"[\u3400-\u9fff]", title))
        if title and not 8 <= han_count <= 18:
            errors.append(f"方案 {label} 的封面短句含 {han_count} 个汉字，应为 8—18 个")

    recommendation = field_map(section(text, "## 推荐"))
    for name in ("推荐方案", "推荐理由"):
        if missing_or_placeholder(recommendation.get(name, "")):
            errors.append(f"推荐部分缺少有效字段：{name}")

    execution = field_map(section(text, "## 推荐方案执行稿"))
    for name in EXECUTION_FIELDS:
        if missing_or_placeholder(execution.get(name, "")):
            errors.append(f"推荐方案执行稿缺少有效字段：{name}")
    canvas = execution.get("画布", "")
    normalized_canvas = canvas.lower().replace(" ", "").replace("x", "×")
    if canvas and "1080×1440" not in normalized_canvas:
        errors.append("最终画布必须为 1080×1440")

    if re.search(r"(震惊|炸裂|史诗级)", text):
        errors.append("发现空泛刺激词：请用具体矛盾或可兑现判断替换")
    return errors


def self_test() -> int:
    valid_fields = "\n".join(
        [
            "- 结构类型：实测拆解型",
            "- 封面短句：机器人真的会取代工人吗",
            "- 一眼先看见：机器人夹爪",
            "- 人物：右侧半身，指向夹爪",
            "- 证据物：左侧唯一机器人夹爪",
            "- 构图：左右对撞并保留上方标题区",
            "- 品牌元素：像素猫角标",
            "- 色彩：深灰底与橙色强调",
            "- 制作说明：保持夹爪结构真实",
            "- 动效转静态说明：用视线形成阅读顺序",
            "- 风险：需要核验设备型号",
        ]
    )
    input_fields = "\n".join(f"- {name}：测试内容" for name in INPUT_FIELDS)
    execution_fields = "\n".join(
        f"- {name}：{'1080×1440' if name == '画布' else '测试内容'}"
        for name in EXECUTION_FIELDS
    )
    sample = (
        f"## 输入判断\n{input_fields}\n"
        f"## 方案 A\n{valid_fields}\n"
        f"## 方案 B\n{valid_fields}\n"
        f"## 方案 C\n{valid_fields}\n"
        "## 推荐\n- 推荐方案：方案 A\n- 推荐理由：证据最清楚\n"
        f"## 推荐方案执行稿\n{execution_fields}\n"
    )
    good_errors = validate(sample)
    bad_errors = validate("## 方案 A\n- 封面短句：震惊\n")
    if good_errors or not bad_errors:
        print(f"self-test failed: good={good_errors!r}, bad={bad_errors!r}", file=sys.stderr)
        return 1
    with tempfile.TemporaryDirectory() as temp_dir:
        Path(temp_dir, "sample.md").write_text(sample, encoding="utf-8")
    print("self-test passed")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", type=Path, help="Markdown cover plan")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    if args.path is None:
        parser.error("path is required unless --self-test is used")
    try:
        text = args.path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"无法读取 {args.path}: {exc}", file=sys.stderr)
        return 2
    errors = validate(text)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"封面方案校验通过：{args.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

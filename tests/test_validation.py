"""Synthetic inputs only: rule regressions, file integrity and review-state boundaries."""
from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from validate_cover_plan import Report, check_plan, validate
from validate_artifacts import check_artifacts, sha256


def fixture(name: str) -> str:
    return (ROOT / "tests" / "fixtures" / name).read_text(encoding="utf-8")


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.battery = fixture("battery-plan.md")
        self.ai = fixture("ai-tutorial-plan.md")
        self.ab = fixture("ai-ab-plan.md")

    def assert_invalid(self, text, fragment):
        self.assertTrue(any(fragment in error for error in validate(text)), validate(text))

    def test_single_battery_illustration_is_valid_plan_not_validated_video(self):
        report, _ = check_plan(self.battery)
        self.assertEqual(report.errors, [])
        self.assertTrue(any("尚未核验实际开场" in warning for warning in report.warnings))

    def test_ai_title_with_english_and_seven_han_is_accepted(self):
        self.assertEqual(validate(self.ai), [])

    def test_short_english_title_and_alternate_canvas_are_accepted(self):
        text = self.ai.replace("AI真的能替我工作", "AI？").replace("1080×1440", "1920×1080")
        self.assertEqual(validate(text), [])

    def test_locked_title_cannot_change_punctuation_or_words(self):
        self.assert_invalid(self.ai.replace("- 封面短句：AI真的能替我工作", "- 封面短句：AI真的能替我工作？"), "锁定标题")

    def test_locked_title_ignores_visual_spaces_only(self):
        self.assertEqual(validate(self.ai.replace("- 封面短句：AI真的能替我工作", "- 封面短句：AI 真的能替我工作")), [])

    def test_slash_is_literal_title_content(self):
        source = self.ai.replace("AI真的能替我工作", "输入/输出")
        self.assertEqual(validate(source), [])
        self.assert_invalid(source.replace("- 封面短句：输入/输出", "- 封面短句：输入输出"), "锁定标题")

    def test_static_action_is_rejected(self):
        self.assert_invalid(self.battery.replace("- 人物动词：指向", "- 人物动词：站立"), "静态状态")

    def test_same_narrative_different_explanation_is_not_exploration(self):
        body = self.battery.split("## 方案 A\n", 1)[1]
        text = self.battery.replace("工作模式：单稿", "工作模式：概念探索")
        text += "\n- 差异说明：第一种方向。\n## 方案 B\n" + body
        text += "\n- 差异说明：换了衣服颜色。\n## 推荐\n- 推荐方案：A\n- 推荐理由：示意关系清楚。\n"
        self.assert_invalid(text, "无已声明的叙事差异")

    def test_input_output_relationship_is_not_rejected_for_object_count(self):
        self.assertEqual(validate(self.ai), [])

    def test_missing_real_assets_can_be_explicit_draft(self):
        report, _ = check_plan(self.ai)
        self.assertEqual(report.errors, [])
        self.assertTrue(any("待补素材" in warning for warning in report.warnings))

    def test_actual_opening_claim_requires_basis(self):
        self.assert_invalid(self.ai.replace("开场依据状态：脚本已有", "开场依据状态：成片已核验"), "开场核验依据")

    def test_constraint_word_is_not_treated_as_title(self):
        self.assertEqual(validate(self.ai + "\n- 负面约束：禁止使用震惊字样。\n"), [])

    def test_plan_cannot_preapprove_artifacts(self):
        self.assert_invalid(self.ai + "\n## 验收记录\n- 缩略图：通过\n", "预填通过")

    def test_ab_title_only_is_valid_design(self):
        self.assertEqual(validate(self.ab), [])

    def test_ab_cannot_also_change_clothes(self):
        at = self.ab.index("## 方案 B")
        text = self.ab[:at] + self.ab[at:].replace("浅灰外套", "黑色工装")
        self.assert_invalid(text, "固定字段")

    def test_duplicate_fields_are_not_silently_overwritten(self):
        self.assert_invalid(self.ai + "\n- 人物动词：站立\n", "重复字段")

    def test_recommendation_cannot_fill_missing_scheme_field(self):
        at = self.ab.index("## 方案 B")
        text = self.ab[:at] + self.ab[at:].replace("- 素材性质：待补素材\n", "", 1)
        text = text.replace("## 推荐\n", "## 推荐\n- 素材性质：待补素材\n")
        self.assert_invalid(text, "方案 B 缺少有效字段：素材性质")

    def test_old_schema_reports_migration(self):
        self.assert_invalid(self.ai.replace("- 方案版本：2\n", ""), "迁移")

    def test_cli_does_not_claim_visual_success(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "validate_cover_plan.py"),
             str(ROOT / "tests" / "fixtures" / "battery-plan.md"), "--json"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["stage"], "方案字段校验（未验证成片）")


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        # Mechanical placeholder images, never presenter/product examples.
        for name, size, color in [
            ("cover.png", (1080, 1440), "white"),
            ("reference.png", (100, 100), "gray"),
            ("thumb.png", (270, 360), "white"),
            ("crop.png", (270, 270), "white"),
        ]:
            Image.new("RGB", size, color).save(self.root / name)
        self.pending = {"status": "待验证", "basis": "合成测试，未作视觉判断。", "evidence": []}
        self.manifest = {
            "schema_version": 2, "canvas": [1080, 1440],
            "variants": [{
                "id": "A", "image": "cover.png",
                "reviewed_sha256": sha256(self.root / "cover.png"),
                "title_transcription": "电池耐用靠谁配合",
                "thumbnail": "thumb.png",
                "crops": [{"file": "crop.png", "scene": "模拟裁切"}],
                "reviews": {key: copy.deepcopy(self.pending) for key in
                            ("title", "identity", "interaction", "evidence_truth", "thumbnail", "crop")},
            }],
            "opening": copy.deepcopy(self.pending),
        }
        self.plan = check_plan(fixture("battery-plan.md"))[1]

    def check(self, ready=False):
        path = self.root / "artifacts.json"
        path.write_text(json.dumps(self.manifest, ensure_ascii=False), encoding="utf-8")
        report = Report()
        check_artifacts(path, self.plan, report, ready)
        return report

    def test_pending_visuals_are_draft_not_ready(self):
        self.assertEqual(self.check().errors, [])
        self.assertTrue(self.check(ready=True).errors)

    def test_missing_output_file_fails(self):
        self.manifest["variants"][0]["image"] = "not-created.png"
        self.assertTrue(any("文件不存在" in e for e in self.check().errors))

    def test_changed_image_invalidates_review(self):
        Image.new("RGB", (1080, 1440), "black").save(self.root / "cover.png")
        self.assertTrue(any("哈希" in e for e in self.check().errors))

    def test_wrong_actual_dimensions_fail(self):
        Image.new("RGB", (100, 100), "white").save(self.root / "cover.png")
        self.manifest["variants"][0]["reviewed_sha256"] = sha256(self.root / "cover.png")
        self.assertTrue(any("实际尺寸" in e for e in self.check().errors))

    def test_invalid_image_bytes_fail(self):
        (self.root / "cover.png").write_bytes(b"not an image")
        self.assertTrue(any("无法解码" in e for e in self.check().errors))

    def test_title_transcription_drift_fails(self):
        self.manifest["variants"][0]["title_transcription"] += "！"
        self.assertTrue(any("标题抄录" in e for e in self.check().errors))

    def test_stretched_thumbnail_fails(self):
        Image.new("RGB", (270, 270), "white").save(self.root / "thumb.png")
        self.assertTrue(any("比例被拉伸" in e for e in self.check().errors))

    def test_pass_without_review_evidence_fails(self):
        self.manifest["variants"][0]["reviews"]["title"]["status"] = "通过"
        self.assertTrue(any("没有实际查看" in e for e in self.check().errors))

    def test_identity_requires_reference_and_current_image(self):
        self.manifest["variants"][0]["reviews"]["identity"] = {
            "status": "通过", "basis": "合成测试记录。", "evidence": ["cover.png"],
        }
        self.assertTrue(any("缺少人物参考" in e for e in self.check().errors))

    def test_crop_review_must_point_to_crop(self):
        self.manifest["variants"][0]["reviews"]["crop"] = {
            "status": "通过", "basis": "合成测试记录。", "evidence": ["cover.png"],
        }
        self.assertTrue(any("未查看全部" in e for e in self.check().errors))

    def test_cannot_skip_identity_when_presenter_exists(self):
        self.manifest["variants"][0]["reviews"]["identity"]["status"] = "不适用"
        self.assertTrue(any("不能标为不适用" in e for e in self.check().errors))

    def test_false_actual_opening_claim_fails(self):
        self.plan["inputs"]["开场依据状态"] = "成片已核验"
        self.assertTrue(any("没有对应通过记录" in e for e in self.check().errors))

    def test_complete_synthetic_records_pass_mechanics_only(self):
        item = self.manifest["variants"][0]
        evidence = {
            "title": ["cover.png"],
            "identity": ["cover.png", "reference.png"],
            "interaction": ["cover.png"],
            "evidence_truth": ["cover.png"],
            "thumbnail": ["thumb.png"],
            "crop": ["crop.png"],
        }
        for key, files in evidence.items():
            item["reviews"][key] = {"status": "通过", "basis": "合成测试记录，不是审美验收。", "evidence": files}
        self.plan["inputs"]["开场依据状态"] = "成片已核验"
        self.manifest["opening"] = {
            "status": "通过", "basis": "合成测试用的开场记录。",
            "source": "synthetic-video-record", "time_range": [0, 3], "evidence": ["reference.png"],
        }
        self.assertEqual(self.check(ready=True).errors, [])

    def test_missing_assets_cannot_be_ready(self):
        self.plan["schemes"]["A"]["素材性质"] = "待补素材"
        self.assertTrue(any("仍缺少" in e for e in self.check(ready=True).errors))

    def test_malformed_manifest_is_reported(self):
        path = self.root / "broken.json"
        path.write_text("{", encoding="utf-8")
        report = Report()
        check_artifacts(path, self.plan, report)
        self.assertTrue(any("无法读取" in e for e in report.errors))


if __name__ == "__main__":
    unittest.main()

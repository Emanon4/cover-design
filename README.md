# Cover Design · v2.0.0

Meme「多工序撰稿设计环节链」旗下的短视频封面设计 Skill。根据脚本、真人和产品素材，设计标题与人物情境，选择主要证据关系，并检查实际输出。

适用于科创大牛猫、蒸汽电波及其他内容账号。最高目标仍是「兑现型点击」：观众因正文能够满足的期待点开，开场及时确认这种期待。执行入口是 [SKILL.md](SKILL.md)。

## v2 升级了什么

| 决策问题 | v2 的处理 |
|---|---|
| 写实生成图被当成实测证据 | 区分实拍、真实截图、官方素材与生成示意，混合图逐项说明来源。 |
| 人物有姿势却没在表达内容 | 用目标、动作、作用对象和可见结果设计情境，身份固定，服装与表演可变。 |
| 所有科技题材都套黑金工装 | 按内容选择明亮实测、编辑海报或真实现场，标题与人物共同构图。 |
| AI 教程和产品只剩芯片或机器人装饰 | 分开前沿解读、教程、产品体验，用对应能力证据或输入输出支撑命题。 |
| 填完方案就宣布成片合格 | 分开方案字段校验、成片文件与审阅记录、实际开场检查。 |
| 多张创意图被误称为 A/B 测试 | 单稿、概念探索、单变量测试分别交付，并记录真实可比条件。 |

用户给定标题默认锁定，包括英文、数字和标点。8—18 个汉字与 1080×1440 都是设计参考，不再作为所有任务的硬门槛。一个主要证据关系可以包含两个产品、输入输出或协同部件，不机械限制为一个物件。

## 设计如何落实

先确认脚本支持的命题与素材来源，再推导人物情境。例如解释系统协同，应让人物与多个部件的配合关系发生可见联系；只有托举动作时，不能自动认为“协同”已经被画面讲清。

科创大牛猫保留「科技商业杂志的判断感＋短视频封面的动作证据」。杂志质感来自主图质量、编辑判断与克制排版，不要求刊头、小英文或固定黑金底。生成示意不能因为精致而获得“实测”身份。

蒸汽电波共用 AI 任务分流和证据规则，但保留自身出镜人、工作站气质与视觉语言。新增账号先形成最小档案，不直接借用其他账号的吉祥物或色彩体系。

参考研究仍保留在 [影视飓风观察](references/filmmaking-hurricane-findings.md) 与 [大牛猫动效观察](references/tech-bull-cat-motion-findings.md)。这些是带时间边界的历史观察，不代表当前平台效果；研究中的旧版制作建议以 v2 执行规则为准。

## 使用方式

将仓库安装到客户端的 Skills 目录；目标不存在时可运行：

```bash
git clone https://github.com/Emanon4/cover-design.git ~/.codex/skills/cover-design
```

已有安装先确认它是独立克隆还是指向项目的链接，再更新对应源目录，不覆盖本机修改。

调用示例：

```text
使用 $cover-design，根据脚本做一张封面，标题保持不变。
使用 $cover-design，比较两种人物与产品互动方式，先给概念方案。
使用 $cover-design，只改变封面短句，设计两版可比的测试。
使用 $cover-design，检查这张成片的人物、产品真实性和手机裁切。
```

只要一张时交付一套；要求多版时再探索。用户只要建议或审稿，不自动生图或发布。客户端有内置生图能力时可直接使用，不强制 API；真人参考仍须逐图比对，不承诺精确锁定身份。

## 输出与验收

方案采用 [v2 模板](references/output-template.md)，按任务填写。制作时交付完整提示词、参考图绑定、成片及实际可编辑的排版源文件；底图与完整封面的存在不等于拥有分层文件。

成片审阅记录使用 [交接契约中的 artifacts.json](references/generation-handoff.md)。需要实际查看原图、等比例缩略图与目标裁切，然后把观察、文件和哈希绑定。改图后旧审阅哈希失效。

开场分别记录「脚本已有」「建议补拍」「成片已核验」或「待提供」。只有读过脚本时，不能宣称视频前三秒已经兑现。封面可以作为草案交付，开场状态保持待验证。

## 验证命令

Python 3.10 或更新版本。Markdown 方案检查仅用标准库；图片检查和回归测试需要 Pillow：

```bash
python3 -m pip install -r requirements.txt
python3 scripts/validate_cover_plan.py tests/fixtures/battery-plan.md
python3 scripts/validate_cover_plan.py tests/fixtures/ai-tutorial-plan.md
python3 scripts/validate_cover_plan.py tests/fixtures/ai-ab-plan.md
python3 scripts/validate_cover_plan.py --self-test
```

核对真实交付文件时：

```bash
python3 scripts/validate_cover_plan.py cover-plan.md --artifacts artifacts.json
python3 scripts/validate_cover_plan.py cover-plan.md --artifacts artifacts.json --ready
```

默认允许有明确待验证项的草案；`--ready` 要求所有适用审阅和实际开场记录完成。加 `--json` 输出结构化结果。缺失文件、尺寸不符、标题抄录不符或审阅哈希过期都会失败。

程序能检查文件完整性和记录之间的矛盾，不能自动判断人像相似度、工程正确性或审美质量。标题抄录来自执行者审阅，并非程序已经做过 OCR；“记录检查通过”不等于程序亲自看过画面。

## 验证范围

回归案例全部为虚构或合成，不包含真实脚本、人像或产品材料。覆盖电池机制示意、缺少素材的 AI 教程、标题单变量对照，以及锁定标题误改、静态姿势、重复方案、字段串入下一节、图片损坏、错误裁切比例、旧审阅记录和虚假开场状态等反例。

这些测试证明工作流规则与检查脚本在相应输入下的行为，不证明图片更好看，也没有测得点击率或留存提升。发布后的学习方法见 [evaluation-loop.md](references/evaluation-loop.md)。

## 从 v1 迁移

CLI 路径与 `--self-test` 保留。旧稿需要按 v2 模板补上模式、标题策略、素材性质和开场状态；缺少版本会明确提示迁移，不默默将旧稿视为合格。无需保留三套方案或继续使用固定画布。

## 文件导航

- [SKILL.md](SKILL.md) 负责模式选择和必须保留的判断边界。
- [output-template.md](references/output-template.md) 与 [generation-handoff.md](references/generation-handoff.md) 负责方案和制作交接。
- [ai-content-routes.md](references/ai-content-routes.md) 负责 AI 内容分流。
- [accounts-tech-bull-cat.md](references/accounts-tech-bull-cat.md) 与 [accounts-steam-radio.md](references/accounts-steam-radio.md) 负责账号差异。
- `scripts/` 和 `tests/` 负责校验及可运行的虚构回归案例。

真实脚本、真人照片、登录态、未发布材料和未获授权的品牌资产不进入此公开仓库。

## License

[MIT](LICENSE)

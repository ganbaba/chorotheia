# Chorotheia

**Memory beyond context.**

Universal Agent Context & Memory System

让记忆超越上下文的边界。

## 定义

| 项目 | 定义 |
|---|---|
| 正式名称 | Chorotheia |
| 初始正式版本 | v1.0.0 |
| 主宣传语 | Memory beyond context. |
| 协作宣传语 | One memory. Any agent. |
| 定位 | 通用 Agent 上下文与持久化记忆系统 |
| 设计理念 | Local-first · Agent-agnostic |
| 品牌关键词 | MEMORY · CONTINUITY · COLLABORATION |
| 建议中文译名 | 科洛忒亚（保留为建议，不宣称注册商标） |
| CLI / Python 包名 | `chorotheia` |
| 全局安装目录 | `~/.chorotheia/` |
| 项目记忆目录 | `.agent/` |

名称融合 Choros 的共享空间与协作意象，以及 Letheia 的记忆延续、抵抗遗忘意象。它是项目采用的品牌叙事，不是对古希腊词义或权利状态的法律认定。

## 品牌图标

<p align="center"><img src="icon.svg" alt="Chorotheia brand icon" width="160"></p>

采用用户提供的 SVG 作为 Chorotheia 品牌图标：香槟金环弧与中心节点、雾蓝色双轨道、透明背景。源文件为 [icon.svg](icon.svg)，与用户提供的文件内容完全一致，不裁切、改色或重新绘制。

图标与文字字标分别提供：小尺寸标识使用图标，横幅或标题排版使用下方字标。SVG 的 `viewBox` 为 `0 0 160 160`，可按需缩放；源文件默认显示尺寸为 145 × 145。优先使用矢量源文件，不以先前的小尺寸 PNG 作为发布源素材。

## 文字设计

沿用最终确定的 `C H O R O T H E I A` 字标、两条宣传语和三个关键词。深色与浅色 SVG 均为文字排版资产，与上述品牌图标配套使用。

发布排版采用深墨色 `#111820`、暖白色 `#f5f0e7` 与柔金色 `#b6a78c`。这三色是本次发布素材的落地选择；原始品牌定义未指定精确色号。字体采用系统无衬线字体回退，不分发第三方字体。

保留名称大小写、宣传语拼写和句点；正文用 Chorotheia，CLI 使用小写。不要使用 ® 或声称商标已完成查重。品牌资产随源码提供，仓库公开不等于授予商标权或完成许可声明。

## README 页首

README 使用紧凑的横排“图标＋字标”，配合原生居中文本、宣传语和徽章栏，不将整个页首嵌入带背景的大幅图片。

- [深色主题组合标识](readme-logo-dark.svg)
- [浅色主题组合标识](readme-logo-light.svg)

两版标识直接复用原始 SVG 图标的图形内容，使用透明背景；README 通过 `picture` 与 `prefers-color-scheme` 选择对应字色。原始 [icon.svg](icon.svg) 保持不变。

Stars、Forks、Issues、Release 和 Checks 徽章读取仓库实际状态；Python 版本和设计理念对应项目当前定义。未设置不存在的许可证或翻译状态徽章。

## 正式模块命名

Chorotheia Core、Bootstrap、Memory、Checkpoint、Restore、Handoff、Guard、Compact、Recall、Hooks、Adapters、Doctor。职责及实际实现映射见 [架构](../docs/ARCHITECTURE.md)。

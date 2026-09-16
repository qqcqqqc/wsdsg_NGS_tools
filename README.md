# 🤪 宇宙无敌 NGS Tool-CQL 定制版 🚀

<p align="center">
  <img src="assets/wawawa.png" alt="疯狂戴夫" width="780"/>
</p>

<p align="center">
  <i>“脑子……歪？数据……歪？不要慌！戴夫顶着锅盖、拿着铲子来帮你撕裂 FASTQ 啦！”</i>
</p>

---

## 🤪 这究竟是个啥奇葩小工具？

这是一个nb的 **NGS 扩增子分析tool**！

专门用来拯救被分析折磨得掉头发的湿实验同学：
* 命令行太长记不住？`cutadapt` 参数填错直接崩掉？
* `CRISPResso2` 批量跑分析天天报各种奇奇怪怪的错？
* 测序引物发生不可抗力 5' 端降解截断？
* 傻傻分不清反向互补链导致 `sgRNA not present in amplicon`？

**不用怕！把数据丢进来，点击按钮，剩下的全部交给戴夫！** 🌻

---

## ⚠️ 戴夫的避坑生存法则（血泪提醒！）

> 🚨 **填写 Excel 表格时，请死死记住以下两条保命法则**：
>
> 1. **样品名绝对不能是“纯数字”**！比如千万别填 `123` 或 `2026`（Excel 会把它当成数值类型，导致脚本识别崩溃！请写成 `Sample_123` 或 `S123`）。
> 2. **样品名绝对不能包含中文破折号 `—` 或全角符号**！横线请一律使用英文半角的 `-` 或下划线 `_`（中文破折号会导致 `cutadapt` 和 `CRISPResso2` 在 Linux 下原地发疯）。


---

## 📊 表格智能识别与示例格式

软件支持 **智能列名关键字识别**！表头列的左右排列顺序 **随意乱摆** 都行，只要包含对应关键字即可自动抓取！

---

### 1. 🔀 FASTQ 拆分表格示例 (`Demux_Template.xlsx`)

适用于 **`🔀 FASTQ UDI 拆分`** 功能：

| 样品名 | 描述 | 所在样品库 | 索引序列1 | 索引序列2 |
| :--- | :--- | :--- | :--- | :--- |
| Sample1 | Control_Rep1 | BEV1-LJG7071 | GAGTAC | ACTGAC |
| Sample2 | ABE_Treat | BEV1-LJG7071 | GAGTAC | TGACAT |

* **戴夫提示**：`所在样品库` 填写文库名称或其前缀（如 `BEV1` 即可匹配）；`索引序列1` 和 `索引序列2` 填写 Index 序列。

---

### 2. 🧬 CRISPResso2 基因编辑分析表格示例

适用于 **`🧬 CRISPResso2 基因编辑效率分析`** 功能：

#### 碱基编辑模式 (BE 模式):
| 样品名 | 描述 | sg | 原始序列 | 原始碱基 | 修改后碱基 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Sample_ABE | ABE-Target1 | GGAAGCTCCAAAGAGTGGCA | GGAAGCTCCAAAGAGTGGCAACGTAG... | A | G |
| Sample_CBE | CBE-Target2 | TAACGTCCCAAACGCGCCAA | GAAATGAAACTTGGGGCGAGGACCAC... | C | T |

#### 敲除模式 (NHEJ 模式):
| 样品名 | 描述 | sg | 原始序列 |
| :--- | :--- | :--- | :--- |
| Sample_CUT1 | CUT-Knockout | TAACGTCCCAAACGCGCCAA | GAAATGAAACTTGGGGCGAGGACCAC... |

---

### 📈 结果汇总指标快速解读指南

分析完成后输出的汇总 Excel 表格中，各项生物学指标定义如下：

#### 1. 敲除与移码分析指标 (NHEJ 汇总表 / BE Sheet 4)
* **`TotalIndels`（总 Indel 突变率）**：
  反映全部测序读段中发生插入或缺失的整体百分比。

  $$
  \text{TotalIndels} = \frac{\text{全部 Indels (包含 } 3n, 3n+1, 3n+2)}{\text{总 Reads (WT + 全部 Indels + Substitutions)}}
  $$

* **`Indels_non3n`（非 3n 移码 Indel 突变率）**：
  插入缺失碱基数非 3 的倍数会导致翻译阅读框移码（Frameshift），造成蛋白失活。评估**基因敲除（KO）破坏有效性**时看此指标。

  $$
  \text{Indels}_{\text{non-3n}} = \frac{\text{非 3 的倍数 Indels (即 } 3n+1 \text{ 与 } 3n+2)}{\text{总 Reads (WT + 全部 Indels + Substitutions)}}
  $$

* **`Indels_without_subs`（排除点突变背景的 Indel 率）**：
  分子依然是所有 Indels，所谓 `without_subs` 是指**分母去除了纯单碱基替换（Substitutions）**。由于测序和 PCR 会自带微量（0.1%~1%）点突变噪音，剔除该噪音可更真实反映纯净扩增子中的 Indel 占比。

  $$
  \text{Indels}_{\text{without-subs}} = \frac{\text{全部 Indels (包含 } 3n, 3n+1, 3n+2)}{\text{WT} + \text{全部 Indels}}
  $$

#### 2. 碱基编辑分析指标 (BE 汇总表)
* **列 `1, 2, 3 ... 20`（目标编辑效率）**：
  记录 sgRNA 第 1 到第 20 位上**目标产物**的突变效率（例如 ABE 中 $A \to G$、CBE 中 $C \to T$）。
* **列 `u1, u2, u3 ... u20`（非预期杂突变率 / Bystander Unwanted Mutation）**：
  `u` 代表 **Unspecified**，记录对应位点上突变成**除原始碱基和目标产物之外的其他杂碱基**的比例。
  * **在 ABE ($A \to G$) 中**：原始是 $A$，目标是 $G$，`u` 列即为突变为 **$C$ 或 $T$** 的杂产物比例。
  * **在 CBE ($C \to T$) 中**：原始是 $C$，目标是 $T$，`u` 列即为突变为 **$A$ 或 $G$** 的杂产物比例。

---

## 🚀 极速启动指南 (戴夫强烈推荐源代码版！)

> 💡 **关键提示（所有人必读）**：
> 无论是运行 **源代码** 还是下载 **打包好的可执行软件 (.exe)**，**都必须先配置底层运行环境**（安装 WSL2 / cutadapt / CRISPResso2）。
> 戴夫**强烈优先推荐使用【源代码版】**！跑起来最稳、更新最快！

### 🌟 推荐方案 A：源代码版 (优先推荐)

1. **准备 Python 环境**：
   * 如果你的电脑还没有 Python，请先去 [Python 官网 (python.org)](https://www.python.org/downloads/) 下载并安装 Python 3.10+。
2. **下载与启动**：
   * **推荐方式（支持一键自动无缝更新）**：在终端运行 `git clone https://github.com/qqcqqqc/wsdsg_NGS_tools.git` 克隆代码。用此方式下载，以后在软件中点 **`🔄 检查软件更新`** 按钮就能一秒静默自动升级！
   * **备选方式（手动下载 ZIP）**：点击页面右上角绿色 `<Code>` 按钮 -> `Download ZIP` 解压。
   * **🪟 Windows 用户**：解压/克隆代码包后，**直接双击 `创建桌面快捷方式.bat`**！桌面上会瞬间生成快捷方式，以后直接双击桌面图标运行！
   * **🍎 macOS / 🐧 Linux 用户**：直接双击或在终端运行 `./启动软件.sh` 即可一键拉起！

---

### 📦 备选方案 B：下载打包好的单独软件 (再不济的选择)

如果你实在不想安装 Python 环境，可以前往仓库的 [Releases 页面](https://github.com/qqcqqqc/wsdsg_NGS_tools/releases) 下载打包好的单独软件。
* 下载完成后直接解压双击运行即可！
* *(请注意：使用打包版依然需要在软件内点击“点我教你配置环境”配置底层分析组件)*

---

## 📄 协议与致谢

- 本项目在 **MIT License** 协议下开源。
- 感谢原作者 [M.Q. @ ShanghaiTech University] 的初始探索与贡献。
- 感谢 `CRISPResso2` 与 `cutadapt` 大佬团队提供的工具！
- 感谢 G老师的大力支持！！！



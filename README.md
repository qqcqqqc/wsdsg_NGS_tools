# 🤪 宇宙无敌 NGS Tool-CQL 定制版 🚀

<p align="center">
  <img src="assets/wawawa.png" alt="疯狂戴夫" width="480"/>
</p>

<p align="center">
  <i>“脑子……歪？数据……歪？不要慌！戴夫顶着锅盖、拿着铲子来帮你撕裂 FASTQ 啦！”</i>
</p>

---

## 🤪 这究竟是个啥奇葩小工具？

这是一个运行在桌面的 **NGS 扩增子测序数据拆分与 CRISPR 基因编辑效率分析神器**！

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

## 🛠️ 戴夫的黑科技特性

- **双端 UDI 强力拆分**：多线程极速并发！支持文库名任意前缀模糊匹配（比如填 `BEV1` 就能自动抓取 `BEV1-LJG7071_R1.fastq.gz`）。哪怕引物被降解掉了几个碱基，也能顺藤摸瓜拆出来！
- **基因编辑效率自动汇总大表**：同时搞定 NHEJ 敲除、Base Editing (BE 碱基编辑)、HDR 同源重组和 Prime Editing (PE 引导编辑)。跑完自动双手奉上精美 Excel 汇总大表！
- **链方向自动翻转 (RC Auto-Correction)**：如果你不小心把 Amplicon 扩增子填成了反向互补链，戴夫会自动帮你在后台把序列翻转过来，彻底告别报错！
- **0.5 秒暴力终结进程**：参数填错了想紧急刹车？点击“停止”按钮，0.5 秒内瞬间强杀 WSL 内部所有后台子进程，CPU 和内存占用瞬间归零！

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

## 🚀 极速启动指南 (戴夫强烈推荐源代码版！)

> 💡 **关键提示（所有人必读）**：
> 无论是运行 **源代码** 还是下载 **打包好的可执行软件 (.exe)**，**都必须先配置底层运行环境**（安装 WSL2 / cutadapt / CRISPResso2）。
> 戴夫**强烈优先推荐使用【源代码版】**！跑起来最稳、更新最快！

### 🌟 推荐方案 A：源代码版 (优先推荐)

1. **准备 Python 环境**：
   * 如果你的电脑还没有 Python，请先去 [Python 官网 (python.org)](https://www.python.org/downloads/) 下载并安装 Python 3.10+。
2. **下载与启动**：
   * **🪟 Windows 用户**：解压代码包后，**直接双击 `创建桌面快捷方式.bat`**！桌面上会瞬间生成快捷方式，以后直接双击桌面图标运行！
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
- 感谢 `CRISPResso2` 与 `cutadapt` 大佬团队提供的底花工具支持！

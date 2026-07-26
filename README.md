# 🧬 NGS & CRISPR 扩增子测序分析工具 v10.25

<p align="center">
  <img src="assets/crazy_dave.png"  width="280"/>
</p>

<p align="center">
  <i>宇宙最帅cql的NGS小工具！</i>
</p>

---

## 🤪 这是个啥小工具？

这是一个运行在桌面的 **NGS 扩增子测序数据拆分与 CRISPR 基因编辑效率分析工具**。

专门用来解决湿实验和生信分析之间各种奇奇怪怪的小烦恼：比如 `cutadapt` 命令行记不住、`CRISPResso2` 批量分析频繁报错、引物发生了 5' 端降解截断、或者表头字段经常填错等等。

---

## 🛠️ 很好用的特性

- **双端 UDI 强力拆分**：基于 `cutadapt` 多线程加速。
- **编辑效率自动汇总**：支持 NHEJ、Base Editing (BE)、HDR 和 Prime Editing (PE)。分析完成后自动导出精美的 Excel 汇总大表。
- **链方向自动纠正 (Reverse Complement)**：如果你不小心把扩增子填成了反向互补链，后台会自动识别并翻转序列，防止报错 `sgRNA not present in amplicon`。
- **秒级进程终结**：遇到跑错参数的情况，点击“停止”按钮，0.5 秒内自动扫荡并清理所有后台子进程，CPU 和内存占用瞬间归零。

---

## 📊 表格列名匹配机制与示例格式

软件对输入的 Excel 表格采用了 **智能列名识别** 机制：

> 💡 **匹配逻辑说明**：
> 只要表头包含对应关键字（如“样品”、“描述”、“库”、“索引1”、“sg”、“原始序列”等），**列的左右排列顺序可以任意排列**，系统都能自动精准定位抓取数据！

---

### 1. 🔀 FASTQ 拆分表格示例 (`Demux_Template.xlsx`)

适用于 **`🔀 FASTQ UDI 拆分`** 功能：

| 样品名 | 描述 | 所在样品库 | 索引序列1 | 索引序列2 |
| :--- | :--- | :--- | :--- | :--- |
| Sample1 | Control_Rep1 | BEV1-LJG7071 | GAGTAC | ACTGAC |
| Sample2 | ABE_Treat | BEV1-LJG7071 | GAGTAC | TGACAT |

* **说明**：`所在样品库` 填写文库名称或其前缀关键字（如 `BEV1`、`BEV1-LJG7071` 均可智能匹配）；`索引序列1` 和 `索引序列2` 填写双端 Index / Barcode 序列。

---

### 2. 🧬 CRISPResso2 基因编辑效率分析表格示例

适用于 **`🧬 CRISPResso2 基因编辑效率分析`** 功能：

#### 碱基编辑模式 (BE Mode):
| 样品名 | 描述 | sg | 原始序列 | 原始碱基 | 修改后碱基 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Sample_ABE | ABE-Target1 | GGAAGCTCCAAAGAGTGGCA | GGAAGCTCCAAAGAGTGGCAACGTAG... | A | G |
| Sample_CBE | CBE-Target2 | TAACGTCCCAAACGCGCCAA | GAAATGAAACTTGGGGCGAGGACCAC... | C | T |

#### 双断裂敲除模式 (NHEJ Mode):
| 样品名 | 描述 | sg | 原始序列 |
| :--- | :--- | :--- | :--- |
| Sample_CUT1 | CUT-Knockout | TAACGTCCCAAACGCGCCAA | GAAATGAAACTTGGGGCGAGGACCAC... |

* **说明**：
  * `sg`：填写 20 nt 左右的 guide 序列。
  * `原始序列`：填写包含 sgRNA 的完整 Amplicon 扩增子序列（就算填了反向互补链，后台也会自动修正）。
  * `原始碱基`与`修改后碱基`：BE 模式下用于指定编辑类型（如 A ➔ G 或 C ➔ T）。

---

## 🛠️ 安装与启动

### 1. 环境准备
* **Windows**：需安装 WSL2 (Ubuntu/Debian)。
* **macOS / Linux**：直接原生运行。
* 生信环境需包含 `cutadapt` 与 `CRISPResso2`（已安装在 conda 环境中）。

### 2. 启动软件
```bash
# 1. 克隆代码
git clone https://github.com/qqcqqqc/wsdsg_NGS_tools.git
cd wsdsg_NGS_tools

# 2. 安装界面依赖
pip install -r requirements.txt

# 3. 启动 GUI 界面
python app.py
```

---

## 📁 目录结构

```text
wsdsg_NGS_tools/
├── app.py                   # 软件启动入口
├── requirements.txt         # Python 依赖清单
├── README.md                # 软件说明文档
├── assets/                  # 搞怪图标资源
├── examples/                # 示例 Excel 表格文件
├── core/                    # 后台逻辑引擎 (Demux/CRISPResso/CQL/WSL通信)
└── gui/                     # 界面 UI 组件 (主窗口/拆分Tab/分析Tab/弹窗)
```

---

## 📄 协议与致谢

- 本项目在 **MIT License** 协议下开源。
- 感谢原作者 [M.Q. @ ShanghaiTech University] 的初始探索与贡献。
- 感谢 `CRISPResso2` 与 `cutadapt` 团队提供的底花生信工具支持。

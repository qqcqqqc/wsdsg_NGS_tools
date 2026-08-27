import os
import sys
import time
import re
from typing import Dict, List, Tuple, Optional, Callable, Any
import pandas as pd

from core.demux_engine import run_demux_pipeline
from core.crispresso_engine import (
    run_crispresso_batch_pipeline,
    summarize_be_batch,
    summarize_nhej_batch
)

def parse_cql_sample_sheet(xlsx_path: str) -> List[Dict[str, str]]:
    """
    Parse CQL all-in-one sample sheet containing columns:
    - 样品名 (Sample Name)
    - 描述 (Description: e.g. ABE-..., CBE-..., CUT-...)
    - 所在样品库 (Pool / Library)
    - 索引序列1 (Index 1)
    - 索引序列2 (Index 2)
    - sg (sgRNA sequence)
    - 原始序列 / Amplicon sequence (avoid matching 索引序列!)
    """
    if not os.path.exists(xlsx_path):
        raise FileNotFoundError(f"Excel 文件不存在: {xlsx_path}")

    df = pd.read_excel(xlsx_path)
    samples = []

    col_name = next((c for c in df.columns if '样品' in str(c) or 'Sample' in str(c)), df.columns[0])
    col_desc = next((c for c in df.columns if '描述' in str(c) or 'Desc' in str(c)), None)
    col_pool = next((c for c in df.columns if '库' in str(c) or 'Pool' in str(c) or 'Library' in str(c)), None)
    col_idx1 = next((c for c in df.columns if '索引1' in str(c) or 'idx1' in str(c).lower() or 'Index1' in str(c) or '索引序列1' in str(c)), None)
    col_idx2 = next((c for c in df.columns if '索引2' in str(c) or 'idx2' in str(c).lower() or 'Index2' in str(c) or '索引序列2' in str(c)), None)
    col_sg = next((c for c in df.columns if 'sg' in str(c).lower() or 'gRNA' in str(c) or 'guide' in str(c).lower()), None)
    
    # Strict Amplicon matching avoiding '索引'
    col_amp = next((c for c in df.columns if ('原始序列' in str(c) or '扩增子' in str(c) or 'amplicon' in str(c).lower()) and '索引' not in str(c)), None)
    if not col_amp:
        col_amp = next((c for c in df.columns if '序列' in str(c) and '索引' not in str(c)), None)

    col_base_from = next((c for c in df.columns if '原始碱基' in str(c) or ('from' in str(c).lower() and 'base' in str(c).lower())), None)
    col_base_to = next((c for c in df.columns if '修改后碱基' in str(c) or ('to' in str(c).lower() and 'base' in str(c).lower())), None)

    for _, row in df.iterrows():
        s_name = str(row[col_name]).strip() if pd.notna(row[col_name]) else ""
        if not s_name or s_name.lower() == 'nan':
            continue

        s_desc = str(row[col_desc]).strip() if col_desc and pd.notna(row[col_desc]) else ""
        s_pool = str(row[col_pool]).strip() if col_pool and pd.notna(row[col_pool]) else ""
        s_idx1 = str(row[col_idx1]).strip() if col_idx1 and pd.notna(row[col_idx1]) else ""
        s_idx2 = str(row[col_idx2]).strip() if col_idx2 and pd.notna(row[col_idx2]) else ""
        s_sg = str(row[col_sg]).strip().upper() if col_sg and pd.notna(row[col_sg]) else ""
        s_amp = str(row[col_amp]).strip().upper() if col_amp and pd.notna(row[col_amp]) else ""
        raw_from = str(row[col_base_from]).strip().upper() if col_base_from and pd.notna(row[col_base_from]) else ""
        raw_to = str(row[col_base_to]).strip().upper() if col_base_to and pd.notna(row[col_base_to]) else ""

        # Auto-detect mode based on description prefix:
        # ABE -> BE (A to G)
        # CBE -> BE (C to T)
        # CUT -> NHEJ
        desc_upper = s_desc.upper()
        if desc_upper.startswith("CUT") or "CUT" in desc_upper:
            mode = "NHEJ"
            base_from = "C"
            base_to = "T"
        else:
            mode = "Base Editing (BE)"
            if raw_from and raw_from.lower() != 'nan' and raw_to and raw_to.lower() != 'nan':
                base_from = raw_from
                base_to = raw_to
            elif desc_upper.startswith("ABE") or "ABE" in desc_upper:
                base_from = "A"
                base_to = "G"
            elif desc_upper.startswith("CBE") or "CBE" in desc_upper:
                base_from = "C"
                base_to = "T"
            else:
                base_from = raw_from if raw_from and raw_from.lower() != 'nan' else "A"
                base_to = raw_to if raw_to and raw_to.lower() != 'nan' else "G"

        samples.append({
            'name': s_name,
            'desc': s_desc,
            'pool': s_pool,
            'idx1': s_idx1,
            'idx2': s_idx2,
            'sg': s_sg,
            'amplicon': s_amp,
            'mode': mode,
            'base_from': base_from,
            'base_to': base_to
        })

    return samples

def run_cql_pipeline(
    excel_path: str,
    raw_fastq_dir: str,
    output_dir: str,
    log_callback: Optional[Callable[[str], None]] = None,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> Tuple[str, str, str]:
    """
    Run complete CQL All-in-One Demux & Analysis Pipeline:
    1. Demuxes raw FASTQ into Demux_Output/ using cutadapt.
    2. Auto-routes samples (ABE -> A-to-G BE, CBE -> C-to-T BE, CUT -> NHEJ).
    3. Runs parallel CRISPResso2 into CRISPResso_Output/.
    4. Auto-exports dedicated BE and NHEJ summary Excel sheets!
    """
    if log_callback:
        log_callback("=" * 65 + "\n")
        log_callback("  ⚡ CQL 专属拆分分析一体化流水线启动\n")
        log_callback("=" * 65 + "\n")

    excel_path = os.path.abspath(excel_path)
    raw_fastq_dir = os.path.abspath(raw_fastq_dir)
    output_dir = os.path.abspath(output_dir)

    demux_out_dir = os.path.join(output_dir, "Demux_Output")
    crispresso_out_dir = os.path.join(output_dir, "CRISPResso_Output")

    os.makedirs(demux_out_dir, exist_ok=True)
    os.makedirs(crispresso_out_dir, exist_ok=True)

    cql_samples = parse_cql_sample_sheet(excel_path)
    total_samples = len(cql_samples)

    if log_callback:
        log_callback(f"[INFO] 识别到待处理总样本数: {total_samples}\n")
        abe_cnt = sum(1 for s in cql_samples if s['mode'] == 'Base Editing (BE)' and s['base_from'] == 'A')
        cbe_cnt = sum(1 for s in cql_samples if s['mode'] == 'Base Editing (BE)' and s['base_from'] == 'C')
        cut_cnt = sum(1 for s in cql_samples if s['mode'] == 'NHEJ')
        log_callback(f"  ├ ABE 样本数 (A->G): {abe_cnt}\n")
        log_callback(f"  ├ CBE 样本数 (C->T): {cbe_cnt}\n")
        log_callback(f"  └ CUT 样本数 (NHEJ): {cut_cnt}\n")

    # Step 1: Execute Demux Pipeline
    if log_callback:
        log_callback("\n------------------------------------------------------------\n")
        log_callback(" [步骤 1/2] 正在进行 Fastq 样品库双端 UDI 自动拆分...\n")
        log_callback("------------------------------------------------------------\n")

    demux_files = run_demux_pipeline(
        excel_path=excel_path,
        fastq_dir=raw_fastq_dir,
        output_dir=demux_out_dir,
        error_rate=0.0,
        no_indels=True,
        log_callback=log_callback,
        progress_callback=lambda curr, tot: progress_callback(int(curr * 0.4 / max(1, tot) * 100), 100) if progress_callback else None
    )

    if log_callback:
        log_callback("\n------------------------------------------------------------\n")
        log_callback(" [步骤 2/2] 正在自动按 ABE/CBE/CUT 路由并进行多核 CPU 分析...\n")
        log_callback("------------------------------------------------------------\n")

    be_samples = [s for s in cql_samples if s['mode'] == "Base Editing (BE)"]
    nhej_samples = [s for s in cql_samples if s['mode'] == "NHEJ"]

    # Run CRISPResso2 for BE samples
    if be_samples:
        if log_callback:
            log_callback(f"[RUN] 正在分析 {len(be_samples)} 个 BE (ABE+CBE) 样本...\n")
        
        be_records = []
        for s in be_samples:
            be_records.append({
                '样品名': s['name'],
                '描述': s['desc'],
                'sg': s['sg'],
                '原始序列': s['amplicon'],
                '原始碱基': s['base_from'],
                '修改后碱基': s['base_to']
            })
        df_be_sheet = pd.DataFrame(be_records)
        tmp_be_excel = os.path.join(output_dir, ".tmp_be_sheet.xlsx")
        df_be_sheet.to_excel(tmp_be_excel, index=False)
        
        run_crispresso_batch_pipeline(
            excel_path=tmp_be_excel,
            fastq_dir=demux_out_dir,
            output_dir=crispresso_out_dir,
            mode="Base Editing (BE)",
            log_callback=log_callback,
            progress_callback=lambda curr, tot: progress_callback(40 + int(curr * 0.4 / max(1, tot) * 100), 100) if progress_callback else None
        )
        if os.path.exists(tmp_be_excel):
            os.remove(tmp_be_excel)

    # Run CRISPResso2 for NHEJ samples
    if nhej_samples:
        if log_callback:
            log_callback(f"[RUN] 正在分析 {len(nhej_samples)} 个 CUT (NHEJ) 样本...\n")
            
        nhej_records = []
        for s in nhej_samples:
            nhej_records.append({
                '样品名': s['name'],
                '描述': s['desc'],
                'sg': s['sg'],
                '原始序列': s['amplicon']
            })
        df_nhej_sheet = pd.DataFrame(nhej_records)
        tmp_nhej_excel = os.path.join(output_dir, ".tmp_nhej_sheet.xlsx")
        df_nhej_sheet.to_excel(tmp_nhej_excel, index=False)
        
        run_crispresso_batch_pipeline(
            excel_path=tmp_nhej_excel,
            fastq_dir=demux_out_dir,
            output_dir=crispresso_out_dir,
            mode="NHEJ",
            log_callback=log_callback,
            progress_callback=lambda curr, tot: progress_callback(80 + int(curr * 0.2 / max(1, tot) * 100), 100) if progress_callback else None
        )
        if os.path.exists(tmp_nhej_excel):
            os.remove(tmp_nhej_excel)

    be_summary_path = summarize_be_batch(be_samples, crispresso_out_dir) if be_samples else ""
    nhej_summary_path = summarize_nhej_batch(nhej_samples, crispresso_out_dir) if nhej_samples else ""

    if progress_callback:
        progress_callback(100, 100)

    if log_callback:
        log_callback("\n" + "=" * 65 + "\n")
        log_callback("  🎉 CQL 一体化拆分与分析全部顺利完成！\n")
        log_callback(f"  ├ 拆分 Fastq 目录: {demux_out_dir}\n")
        log_callback(f"  ├ 分析结果目录:   {crispresso_out_dir}\n")
        if be_summary_path:
            log_callback(f"  ├ BE 汇总表格:    {be_summary_path}\n")
        if nhej_summary_path:
            log_callback(f"  └ NHEJ 汇总表格:  {nhej_summary_path}\n")
        log_callback("=" * 65 + "\n")

    return demux_out_dir, crispresso_out_dir, be_summary_path

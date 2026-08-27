import os
import sys
import tempfile
import zipfile
import shutil
import time
import re
import json
import multiprocessing
import xml.etree.ElementTree as ET
from collections import defaultdict
from typing import Dict, List, Tuple, Optional, Callable, Any
import pandas as pd

from core.platform_runner import global_runner, win_to_wsl_path, is_windows

def rc(seq: str) -> str:
    """Reverse complement of a DNA sequence."""
    comp = {'A': 'T', 'T': 'A', 'C': 'G', 'G': 'C',
            'a': 't', 't': 'a', 'c': 'g', 'g': 'c', 'N': 'N', 'n': 'n'}
    return ''.join(comp.get(b, 'N') for b in reversed(seq))

def get_optimal_thread_count() -> int:
    """Calculate optimal CPU process/thread count for parallel alignment."""
    try:
        cpu_count = multiprocessing.cpu_count()
        return max(2, cpu_count - 2)
    except Exception:
        return 4

# Standard and degenerate IUPAC DNA base mapping
IUPAC_DNA_MAP = {
    'A': {'A'}, 'C': {'C'}, 'G': {'G'}, 'T': {'T'}, 'U': {'T'},
    'R': {'A', 'G'}, 'Y': {'C', 'T'}, 'S': {'C', 'G'}, 'W': {'A', 'T'},
    'K': {'G', 'T'}, 'M': {'A', 'C'}, 'B': {'C', 'G', 'T'},
    'D': {'A', 'G', 'T'}, 'H': {'A', 'C', 'T'}, 'V': {'A', 'C', 'G'},
    'N': {'A', 'C', 'G', 'T'}
}
BASE_ROW_MAP = {'A': 0, 'C': 1, 'G': 2, 'T': 3}

def parse_crispresso_sample_sheet(xlsx_path: str) -> List[Dict[str, str]]:
    """
    Parse CRISPResso batch analysis sample sheet (.xlsx).
    Flexibly supports columns:
    - 样品名 (Sample Name)
    - 描述 (Description)
    - sg / sgRNA
    - 原始序列 / Amplicon (avoid matching 索引序列!)
    - 原始碱基 / base_from (Optional for BE, default C)
    - 修改后碱基 / base_to (Optional for BE, default T, supports any IUPAC letter code)
    - 供体序列 / Donor (Optional for HDR/PE)
    """
    if not os.path.exists(xlsx_path):
        raise FileNotFoundError(f"Excel 文件不存在: {xlsx_path}")

    samples = []
    
    try:
        df = pd.read_excel(xlsx_path)
        col_name = next((c for c in df.columns if '样品' in str(c) or 'Sample' in str(c) or 'sample' in str(c)), df.columns[0])
        col_desc = next((c for c in df.columns if '描述' in str(c) or 'Desc' in str(c)), None)
        col_sg = next((c for c in df.columns if 'sg' in str(c).lower() or 'gRNA' in str(c) or 'guide' in str(c).lower()), None)
        
        # Strict Amplicon matching avoiding '索引'
        col_amp = next((c for c in df.columns if ('原始序列' in str(c) or '扩增子' in str(c) or 'amplicon' in str(c).lower()) and '索引' not in str(c)), None)
        if not col_amp:
            col_amp = next((c for c in df.columns if '序列' in str(c) and '索引' not in str(c)), None)
            
        col_base_from = next((c for c in df.columns if '原始碱基' in str(c) or ('from' in str(c).lower() and 'base' in str(c).lower())), None)
        col_base_to = next((c for c in df.columns if '修改后碱基' in str(c) or ('to' in str(c).lower() and 'base' in str(c).lower())), None)
        col_donor = next((c for c in df.columns if '供体' in str(c) or 'Donor' in str(c) or 'PE' in str(c) or 'HDR' in str(c)), None)
        
        for _, row in df.iterrows():
            s_name = str(row[col_name]).strip() if pd.notna(row[col_name]) else ""
            if not s_name or s_name.lower() == 'nan':
                continue
                
            s_desc = str(row[col_desc]).strip() if col_desc and pd.notna(row[col_desc]) else ""
            s_sg = str(row[col_sg]).strip().upper() if col_sg and pd.notna(row[col_sg]) else ""
            s_amp = str(row[col_amp]).strip().upper() if col_amp and pd.notna(row[col_amp]) else ""
            raw_from = str(row[col_base_from]).strip().upper() if col_base_from and pd.notna(row[col_base_from]) else ""
            raw_to = str(row[col_base_to]).strip().upper() if col_base_to and pd.notna(row[col_base_to]) else ""
            s_donor = str(row[col_donor]).strip().upper() if col_donor and pd.notna(row[col_donor]) else ""
            
            if raw_from and raw_from.lower() != 'nan' and raw_to and raw_to.lower() != 'nan':
                s_base_from = raw_from
                s_base_to = raw_to
            else:
                desc_upper = s_desc.upper()
                if desc_upper.startswith("ABE") or "ABE" in desc_upper:
                    s_base_from = "A"
                    s_base_to = "G"
                elif desc_upper.startswith("CBE") or "CBE" in desc_upper:
                    s_base_from = "C"
                    s_base_to = "T"
                else:
                    s_base_from = raw_from if raw_from and raw_from.lower() != 'nan' else "C"
                    s_base_to = raw_to if raw_to and raw_to.lower() != 'nan' else "T"
            
            samples.append({
                'name': s_name,
                'desc': s_desc,
                'sg': s_sg,
                'amplicon': s_amp,
                'base_from': s_base_from,
                'base_to': s_base_to,
                'donor': s_donor
            })
            
        if samples:
            return samples
    except Exception:
        pass

    return samples

def find_sample_fastq_pairs(fastq_dir: str, sample_name: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Find R1 and R2 FASTQ files matching exact sample_name prefix in fastq_dir.
    Uses strict boundary matching so sample 'a1' does NOT accidentally match 'a11' or 'a12'.
    """
    r1 = r2 = None
    if not os.path.exists(fastq_dir):
        return None, None
        
    pattern = re.compile(rf"^{re.escape(sample_name)}([._\-].*)?$", re.IGNORECASE)
    
    for f in sorted(os.listdir(fastq_dir)):
        if not (f.endswith('.fq.gz') or f.endswith('.fastq.gz') or f.endswith('.fq') or f.endswith('.fastq')):
            continue
        
        base_name = f.split('.fq')[0].split('.fastq')[0]
        if pattern.match(base_name):
            if any(s in f for s in ['_1.fq', '_R1.fq', '_1.fastq', '_R1.fastq', '-1.fq', '-1.fastq', '.1.fq', '.1.fastq']):
                r1 = os.path.abspath(os.path.join(fastq_dir, f))
            elif any(s in f for s in ['_2.fq', '_R2.fq', '_2.fastq', '_R2.fastq', '-2.fq', '-2.fastq', '.2.fq', '.2.fastq']):
                r2 = os.path.abspath(os.path.join(fastq_dir, f))
                
    return r1, r2

def process_nhej_cleavage_file(filepath: str, sample_name: str) -> Dict[str, Any]:
    """Parse Alleles_frequency_table_around_sgRNA file for NHEJ frameshift & indel stats."""
    wt_allele = []
    n3_1_deleted = []
    n3_2_deleted = []
    n3_deleted = []
    n3_1_inserted = []
    n3_2_inserted = []
    n3_inserted = []
    substitution = []

    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            if line.startswith("Aligned_Sequence"):
                continue
            line = line.strip()
            if not line:
                continue
            line_list = line.split('\t')
            if len(line_list) < 8:
                continue
            unedited = line_list[2].strip().upper()
            try:
                n_del = int(line_list[3])
                n_ins = int(line_list[4])
                n_mut = int(line_list[5])
                n_reads = int(line_list[-2])
            except (ValueError, IndexError):
                continue

            if unedited == "TRUE":
                wt_allele.append(n_reads)
                continue
            if unedited == "FALSE":
                if n_del > 0 and n_ins == 0:
                    mod = n_del % 3
                    if mod == 1: n3_1_deleted.append(n_reads)
                    elif mod == 2: n3_2_deleted.append(n_reads)
                    else: n3_deleted.append(n_reads)
                    continue
                if n_del == 0 and n_ins > 0:
                    mod = n_ins % 3
                    if mod == 1: n3_1_inserted.append(n_reads)
                    elif mod == 2: n3_2_inserted.append(n_reads)
                    else: n3_inserted.append(n_reads)
                    continue
                if n_del > 0 and n_ins > 0:
                    delta = n_del - n_ins
                    if delta > 0:
                        mod = delta % 3
                        if mod == 1: n3_1_deleted.append(n_reads)
                        elif mod == 2: n3_2_deleted.append(n_reads)
                        else: n3_deleted.append(n_reads)
                    elif delta < 0:
                        mod = abs(delta) % 3
                        if mod == 1: n3_1_inserted.append(n_reads)
                        elif mod == 2: n3_2_inserted.append(n_reads)
                        else: n3_inserted.append(n_reads)
                    continue
                if n_del == 0 and n_ins == 0 and n_mut > 0:
                    substitution.append(n_reads)
                    continue

    nwt = sum(wt_allele)
    n_d1 = sum(n3_1_deleted); n_d2 = sum(n3_2_deleted); n_d3 = sum(n3_deleted)
    n_i1 = sum(n3_1_inserted); n_i2 = sum(n3_2_inserted); n_i3 = sum(n3_inserted)
    n_sub = sum(substitution)

    total = nwt + n_d1 + n_d2 + n_d3 + n_i1 + n_i2 + n_i3 + n_sub
    n_indels = n_d1 + n_d2 + n_d3 + n_i1 + n_i2 + n_i3
    n_indels_non3n = n_d1 + n_d2 + n_i1 + n_i2

    pct_total = (n_indels / total) if total > 0 else 0.0
    pct_non3n = (n_indels_non3n / total) if total > 0 else 0.0
    denominator = nwt + n_indels
    pct_without_subs = (n_indels / denominator) if denominator > 0 else 0.0

    return {
        "Sample": sample_name,
        "wt_allele": nwt,
        "3n+1_del": n_d1, "3n+2_del": n_d2, "3n_del": n_d3,
        "3n+1_insert": n_i1, "3n+2_insert": n_i2, "3n_insert": n_i3,
        "Substitutions": n_sub,
        "TotalIndels": pct_total,
        "Indels_non3n": pct_non3n,
        "Indels_without_subs": pct_without_subs,
    }

def summarize_nhej_batch(samples: List[Dict[str, str]], output_dir: str, log_callback: Optional[Callable[[str], None]] = None) -> str:
    """Summarize NHEJ results using cleavage_sum_QQC.py logic with date prefix and numeric percentage formatting."""
    results = []
    sample_desc = {s['name']: s['desc'] for s in samples}

    for s in samples:
        s_name = s['name']
        sample_dir = os.path.join(output_dir, s_name)
        if not os.path.exists(sample_dir):
            if os.path.exists(os.path.join(output_dir, "CRISPResso_Output", s_name)):
                sample_dir = os.path.join(output_dir, "CRISPResso_Output", s_name)
            else:
                candidates = [os.path.join(output_dir, d) for d in os.listdir(output_dir) if os.path.isdir(os.path.join(output_dir, d)) and (d == s_name or d.startswith(f"{s_name}_") or f"_on_{s_name}_" in d or f"CRISPResso_on_{s_name}" in d)]
                if candidates:
                    sample_dir = candidates[0]
                else:
                    continue

        subfolders = [os.path.join(sample_dir, f) for f in os.listdir(sample_dir) if os.path.isdir(os.path.join(sample_dir, f))]
        target_dir = subfolders[0] if subfolders else sample_dir

        allele_file = None
        if os.path.exists(target_dir):
            for f in os.listdir(target_dir):
                if f.endswith('.txt') and 'Alleles_frequency_table_around_sgRNA' in f:
                    allele_file = os.path.join(target_dir, f)
                    break

        if allele_file and os.path.exists(allele_file):
            try:
                row = process_nhej_cleavage_file(allele_file, s_name)
                row["描述"] = sample_desc.get(s_name, "")
                results.append(row)
                if log_callback:
                    log_callback(f"[INFO] 成功提取 NHEJ 样本数据: {s_name}\n")
            except Exception as e:
                print(f"Error parsing NHEJ cleavage for {s_name}: {e}")

    today_date = time.strftime("%Y%m%d")
    outname = f"{today_date}_NHEJ_Cleavage_分析结果汇总.xlsx"
    outpath = os.path.join(output_dir, outname)

    if results:
        df_res = pd.DataFrame(results)
        cols = ["Sample", "描述", "wt_allele", "3n+1_del", "3n+2_del", "3n_del",
                "3n+1_insert", "3n+2_insert", "3n_insert", "Substitutions",
                "TotalIndels", "Indels_non3n", "Indels_without_subs"]
        existing_cols = [c for c in cols if c in df_res.columns]
        df_res = df_res[existing_cols]
        
        try:
            with pd.ExcelWriter(outpath, engine='openpyxl') as writer:
                df_res.to_excel(writer, index=False, sheet_name="NHEJ Summary")
                ws = writer.sheets["NHEJ Summary"]
                pct_cols = ["TotalIndels", "Indels_non3n", "Indels_without_subs"]
                col_indices = [df_res.columns.get_loc(c) + 1 for c in pct_cols if c in df_res.columns]
                for row in range(2, len(df_res) + 2):
                    for col_idx in col_indices:
                        cell = ws.cell(row=row, column=col_idx)
                        if cell.value is not None and isinstance(cell.value, (int, float)):
                            cell.number_format = '0.00%'
        except PermissionError:
            outpath = os.path.join(output_dir, f"{today_date}_NHEJ_Cleavage_分析结果汇总_最新.xlsx")
            df_res.to_excel(outpath, index=False)

        return outpath
    else:
        df_empty = pd.DataFrame(columns=["Sample", "描述", "%TotalIndels"])
        df_empty.to_excel(outpath, index=False)
        return outpath

def summarize_be_batch(samples: List[Dict[str, str]], output_dir: str, log_callback: Optional[Callable[[str], None]] = None) -> str:
    """
    Summarize BE results dynamically matching sgRNA length (1..N and u1..uN).
    - Supports arbitrary ATCG and any degenerate IUPAC DNA letter codes (R, Y, S, W, K, M, B, D, H, V, N).
    - Sheet 1: BE Base Editing Window Efficiencies (1..N & u1..uN).
    - Sheet 2: BE Indel & Frameshift Breakdown.
    """
    records_be = []
    records_indel = []
    max_sg_len = 20

    for s in samples:
        s_name = s['name']
        s_desc = s['desc']
        s_sg = s['sg']
        s_amp = s['amplicon']
        
        user_specified_base = bool(s.get('base_from') and s.get('base_to'))
        s_base_from = str(s.get('base_from', 'C')).strip().upper()
        s_base_to = str(s.get('base_to', 'T')).strip().upper()

        sg_len = len(s_sg) if s_sg else 20
        if sg_len > max_sg_len:
            max_sg_len = sg_len

        sample_dir = os.path.join(output_dir, s_name)
        if not os.path.exists(sample_dir):
            if os.path.exists(os.path.join(output_dir, "CRISPResso_Output", s_name)):
                sample_dir = os.path.join(output_dir, "CRISPResso_Output", s_name)
            else:
                candidates = [os.path.join(output_dir, d) for d in os.listdir(output_dir) if os.path.isdir(os.path.join(output_dir, d)) and (d == s_name or d.startswith(f"{s_name}_") or f"_on_{s_name}_" in d or f"CRISPResso_on_{s_name}" in d)]
                if candidates:
                    sample_dir = candidates[0]

        record_be = {
            '样品名': s_name,
            '描述': s_desc,
            '原始碱基': s_base_from,
            '修改后碱基': s_base_to,
            '测序深度': 0
        }
        for p in range(1, sg_len + 1):
            record_be[p] = None
            record_be[f"u{p}"] = 0.0

        record_indel = {
            'Sample': s_name,
            '描述': s_desc,
            'wt_allele': 0,
            '3n+1_del': 0, '3n+2_del': 0, '3n_del': 0,
            '3n+1_insert': 0, '3n+2_insert': 0, '3n_insert': 0,
            'Substitutions': 0,
            'TotalIndels': 0.0,
            'Indels_non3n': 0.0,
            'Indels_without_subs': 0.0
        }

        if not os.path.exists(sample_dir):
            records_be.append(record_be)
            records_indel.append(record_indel)
            continue

        subfolders = [os.path.join(sample_dir, f) for f in os.listdir(sample_dir) if os.path.isdir(os.path.join(sample_dir, f))]
        target_dir = subfolders[0] if subfolders else sample_dir

        sg_table_file = None
        sub_table_file = None
        info_file = None
        allele_file = None

        if os.path.exists(target_dir):
            for f in os.listdir(target_dir):
                if 'Selected_nucleotide_frequency_table_around_sgRNA' in f and f.endswith('.txt'):
                    sg_table_file = os.path.join(target_dir, f)
                elif f == 'Quantification_window_substitution_frequency_table.txt':
                    sub_table_file = os.path.join(target_dir, f)
                elif f == 'CRISPResso2_info.json':
                    info_file = os.path.join(target_dir, f)
                elif 'Alleles_frequency_table_around_sgRNA' in f and f.endswith('.txt'):
                    allele_file = os.path.join(target_dir, f)

        # Auto-detect base_from / base_to from output table or description if not explicitly set in Excel
        if not user_specified_base:
            if sg_table_file and os.path.exists(sg_table_file):
                try:
                    df_sg_head = pd.read_csv(sg_table_file, sep='\t', nrows=1)
                    num_cols = [c for c in df_sg_head.columns if c and c[0] in 'ACGT' and c[1:].isdigit()]
                    if num_cols:
                        s_base_from = num_cols[0][0]
                        s_base_to = 'G' if s_base_from == 'A' else 'T' if s_base_from == 'C' else 'A' if s_base_from == 'G' else 'C'
                        record_be['原始碱基'] = s_base_from
                        record_be['修改后碱基'] = s_base_to
                except Exception:
                    pass
            elif 'ABE' in s_desc.upper() or 'ABE' in s_name.upper():
                s_base_from = 'A'
                s_base_to = 'G'
                record_be['原始碱基'] = s_base_from
                record_be['修改后碱基'] = s_base_to

        # Resolve IUPAC base sets for target and unspecified conversions
        s_base_from_clean = s_base_from.strip().upper() if s_base_from else 'A'
        s_base_to_clean = s_base_to.strip().upper() if s_base_to else 'G'
        from_bases = IUPAC_DNA_MAP.get(s_base_from_clean, {s_base_from_clean})
        to_bases = IUPAC_DNA_MAP.get(s_base_to_clean, {s_base_to_clean})

        target_bases = to_bases - from_bases if (to_bases - from_bases) else to_bases
        unspec_bases = {'A', 'C', 'G', 'T'} - from_bases - to_bases

        # 1. Parse Indel & Frameshift breakdown directly from Alleles_frequency_table_around_sgRNA
        if allele_file and os.path.exists(allele_file):
            try:
                row_ind = process_nhej_cleavage_file(allele_file, s_name)
                row_ind['描述'] = s_desc
                record_indel = row_ind
            except Exception as e:
                print(f"Error parsing Indel stats in BE folder for {s_name}: {e}")

        # 2. Determine exact offset of plot window relative to sgRNA start
        sg_start_exact = None
        if s_sg and s_amp:
            s_sg_clean = s_sg.strip().upper()
            s_amp_clean = s_amp.strip().upper()
            if s_sg_clean not in s_amp_clean and s_sg_clean in rc(s_amp_clean):
                s_amp_clean = rc(s_amp_clean)
            idx = s_amp_clean.find(s_sg_clean)
            if idx != -1:
                sg_start_exact = idx

        offset = None
        if info_file and os.path.exists(info_file):
            try:
                with open(info_file, 'r', encoding='utf-8') as f_inf:
                    info_data = json.load(f_inf)
                ref_dict = info_data.get('results', {}).get('refs', {}).get('Reference', {})
                if not ref_dict and 'refs' in info_data.get('results', {}):
                    first_k = list(info_data['results']['refs'].keys())[0]
                    ref_dict = info_data['results']['refs'][first_k]
                
                plot_idxs = ref_dict.get('sgRNA_plot_idxs', [])
                sg_intervals = ref_dict.get('sgRNA_intervals', [])
                if plot_idxs:
                    plot_start = int(plot_idxs[0][0])
                    if sg_intervals:
                        sg_start_info = int(sg_intervals[0][0])
                        offset = int(plot_start - sg_start_info)
                    elif sg_start_exact is not None:
                        offset = int(plot_start - sg_start_exact)
            except Exception as e:
                print(f"Error reading info json offset for {s_name}: {e}")

        # Gap-matching fallback if info.json offset is not present
        if offset is None and sg_table_file and os.path.exists(sg_table_file):
            try:
                df_temp = pd.read_csv(sg_table_file, sep='\t')
                sg_target_pos = [i + 1 for i, char in enumerate(s_sg) if char in from_bases] if s_sg else []
                table_num_cols = [(int(c[1:]), c) for c in df_temp.columns if c and c[0] in from_bases and c[1:].isdigit()]
                if sg_target_pos and table_num_cols:
                    sg_gaps = [sg_target_pos[i+1] - sg_target_pos[i] for i in range(len(sg_target_pos)-1)]
                    for start_i in range(len(table_num_cols) - len(sg_target_pos) + 1):
                        candidate_cols = table_num_cols[start_i : start_i + len(sg_target_pos)]
                        cand_gaps = [candidate_cols[i+1][0] - candidate_cols[i][0] for i in range(len(candidate_cols)-1)]
                        if cand_gaps == sg_gaps:
                            offset = int(candidate_cols[0][0] - sg_target_pos[0])
                            break
            except Exception:
                pass

        if sg_table_file and os.path.exists(sg_table_file) and offset is not None:
            try:
                df_sg = pd.read_csv(sg_table_file, sep='\t')
                
                for col in df_sg.columns:
                    col_base = col[0] if len(col) > 1 and col[1:].isdigit() else None
                    if col_base and (col_base in from_bases or col_base == s_base_from_clean) and col[1:].isdigit():
                        K = int(col[1:])
                        sg_pos = K + offset
                        if 1 <= sg_pos <= sg_len and (not s_sg or s_sg[sg_pos - 1] in from_bases):
                            col_series = df_sg[col]
                            all_reads = pd.to_numeric(col_series, errors='coerce').sum()
                            if all_reads > 0:
                                record_be['测序深度'] = int(all_reads)
                                target_reads = sum(float(col_series.iloc[BASE_ROW_MAP[b]]) for b in target_bases if b in BASE_ROW_MAP)
                                eff_ratio = target_reads / float(all_reads)
                                record_be[sg_pos] = eff_ratio

            except Exception as e:
                print(f"Error parsing BE sg table for {s_name}: {e}")

        if sub_table_file and os.path.exists(sub_table_file) and offset is not None:
            try:
                df_sub = pd.read_csv(sub_table_file, sep="\t")
                total_depth = record_be['测序深度']
                for pos in range(1, sg_len + 1):
                    col_idx = pos - offset
                    if 0 <= col_idx < len(df_sub.columns) and total_depth > 0:
                        col_series = pd.to_numeric(df_sub.iloc[:, col_idx], errors='coerce').fillna(0)
                        unspec_cnt = sum(float(col_series.iloc[BASE_ROW_MAP[b]]) for b in unspec_bases if b in BASE_ROW_MAP)
                        if unspec_cnt < 0:
                            unspec_cnt = 0
                        unspec_ratio = unspec_cnt / float(total_depth)
                        record_be[f"u{pos}"] = unspec_ratio
                    else:
                        record_be[f"u{pos}"] = 0.0
            except Exception as e:
                print(f"Error parsing BE sub table for {s_name}: {e}")

        if log_callback:
            log_callback(f"[INFO] 成功提取 BE 样本数据: {s_name}\n")

        records_be.append(record_be)
        records_indel.append(record_indel)

    today_date = time.strftime("%Y%m%d")
    outname = f"{today_date}_BE_分析结果汇总.xlsx"
    outpath = os.path.join(output_dir, outname)

    if records_be:
        df_be = pd.DataFrame(records_be)
        df_be[' '] = '' # Blank visual spacer column
        
        base_cols = ['样品名', '描述', '原始碱基', '修改后碱基', '测序深度']
        all_pos = [p for p in range(1, max_sg_len + 1) if p in df_be.columns]
        all_unspec = [f"u{p}" for p in range(1, max_sg_len + 1) if f"u{p}" in df_be.columns]
        
        ordered_be_cols = base_cols + all_pos + [' '] + all_unspec
        existing_be_cols = [c for c in ordered_be_cols if c in df_be.columns]
        df_be = df_be[existing_be_cols]

        df_indel = pd.DataFrame(records_indel)
        indel_cols = ["Sample", "描述", "wt_allele", "3n+1_del", "3n+2_del", "3n_del",
                      "3n+1_insert", "3n+2_insert", "3n_insert", "Substitutions",
                      "TotalIndels", "Indels_non3n", "Indels_without_subs"]
        existing_ind_cols = [c for c in indel_cols if c in df_indel.columns]
        df_indel = df_indel[existing_ind_cols]

        try:
            with pd.ExcelWriter(outpath, engine='openpyxl') as writer:
                # Write Sheet 1: BE Base Editing Window Efficiencies
                df_be.to_excel(writer, index=False, sheet_name="BE 碱基编辑效率汇总")
                ws_be = writer.sheets["BE 碱基编辑效率汇总"]
                percentage_be_cols = all_pos + all_unspec
                col_be_indices = [df_be.columns.get_loc(c) + 1 for c in percentage_be_cols if c in df_be.columns]
                for row in range(2, len(df_be) + 2):
                    for col_idx in col_be_indices:
                        cell = ws_be.cell(row=row, column=col_idx)
                        if cell.value is not None and isinstance(cell.value, (int, float)):
                            cell.number_format = '0.00%'

                # Write Sheet 2: BE Indel & Frameshift Breakdown
                df_indel.to_excel(writer, index=False, sheet_name="BE Indel与移码分析")
                ws_ind = writer.sheets["BE Indel与移码分析"]
                percentage_ind_cols = ["TotalIndels", "Indels_non3n", "Indels_without_subs"]
                col_ind_indices = [df_indel.columns.get_loc(c) + 1 for c in percentage_ind_cols if c in df_indel.columns]
                for row in range(2, len(df_indel) + 2):
                    for col_idx in col_ind_indices:
                        cell = ws_ind.cell(row=row, column=col_idx)
                        if cell.value is not None and isinstance(cell.value, (int, float)):
                            cell.number_format = '0.00%'

        except PermissionError:
            outpath = os.path.join(output_dir, f"{today_date}_BE_分析结果汇总_最新.xlsx")
            with pd.ExcelWriter(outpath, engine='openpyxl') as writer:
                df_be.to_excel(writer, index=False, sheet_name="BE 碱基编辑效率汇总")
                df_indel.to_excel(writer, index=False, sheet_name="BE Indel与移码分析")

        return outpath
    else:
        df_empty = pd.DataFrame(columns=['样品名', '描述', '原始碱基', '修改后碱基', '测序深度'])
        df_empty.to_excel(outpath, index=False)
        return outpath

def run_crispresso_batch_pipeline(
    excel_path: str,
    fastq_dir: str,
    output_dir: str,
    mode: str = "NHEJ",
    quant_window: int = 10,
    cleavage_offset: int = -3,
    min_read_qual: int = 30,
    exclude_left: int = 15,
    exclude_right: int = 15,
    plot_window: int = 20,
    log_callback: Optional[Callable[[str], None]] = None,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> Tuple[List[str], str]:
    """
    Run CRISPResso2 batch analysis with exact sample FASTQ matching, multi-core CPU acceleration,
    automatic strand orientation correction (RC), and automatic edge-case retry.
    """
    if log_callback:
        log_callback("=" * 60 + "\n")
        log_callback(f"  CRISPResso2 批量基因编辑效率分析启动 [{mode} 模式]\n")
        log_callback("=" * 60 + "\n")

    excel_path = os.path.abspath(excel_path)
    fastq_dir = os.path.abspath(fastq_dir)
    output_dir = os.path.abspath(output_dir)

    samples = parse_crispresso_sample_sheet(excel_path)
    total_samples = len(samples)
    
    threads = get_optimal_thread_count()
    if log_callback:
        log_callback(f"[INFO] 从表格共解析到 {total_samples} 个待分析样本 | 多核 CPU 加速已启用 ({threads} 线程)\n")

    os.makedirs(output_dir, exist_ok=True)
    processed_dirs = []

    for s_idx, sample in enumerate(samples, start=1):
        if progress_callback:
            progress_callback(s_idx - 1, total_samples)
            
        s_name = sample['name']
        s_desc = sample['desc']
        s_sg = sample['sg']
        s_amp = sample['amplicon']
        s_base_from = sample['base_from']
        s_base_to = sample['base_to']
        s_donor = sample['donor']
        
        # Auto reverse-complement amplicon if sgRNA is on the non-editing strand (rc(amplicon))
        if s_sg and s_amp:
            s_sg_clean = s_sg.strip().upper()
            s_amp_clean = s_amp.strip().upper()
            if s_sg_clean not in s_amp_clean and s_sg_clean in rc(s_amp_clean):
                s_amp = rc(s_amp_clean)
                if log_callback:
                    log_callback(f"[INFO] 样本 {s_name} 的 sgRNA 位于 Amplicon 反向互补链上，已自动修正链方向 (Reverse Complement)！\n")

        is_be_mode = ("BE" in mode or mode == "Base Editing (BE)")

        be_center_idx = None
        be_sg_len = len(s_sg) if s_sg else 20
        if is_be_mode and s_sg and s_amp:
            s_sg_clean = s_sg.strip().upper()
            s_amp_clean = s_amp.strip().upper()
            idx_found = s_amp_clean.find(s_sg_clean)
            if idx_found == -1:
                idx_found = s_amp_clean.find(rc(s_sg_clean))
            if idx_found != -1:
                be_center_idx = idx_found + be_sg_len // 2 - 1

        if log_callback:
            log_callback(f"\n[{s_idx}/{total_samples}] 正在处理样本: {s_name} ({s_desc})\n")

        r1_fastq, r2_fastq = find_sample_fastq_pairs(fastq_dir, s_name)
        if not r1_fastq:
            if log_callback:
                log_callback(f"[WARN] 样本 {s_name} 在 {fastq_dir} 中找不到对应的 FASTQ 文件，跳过！\n")
            continue

        sample_out_dir = os.path.join(output_dir, s_name)
        os.makedirs(sample_out_dir, exist_ok=True)

        cmd = [
            "CRISPResso",
            "--fastq_r1", win_to_wsl_path(r1_fastq) if is_windows() else r1_fastq
        ]
        if r2_fastq:
            cmd.extend(["--fastq_r2", win_to_wsl_path(r2_fastq) if is_windows() else r2_fastq])

        cmd.extend([
            "--amplicon_seq", s_amp,
            "--guide_seq", s_sg,
            "--output_folder", win_to_wsl_path(sample_out_dir) if is_windows() else sample_out_dir,
            "--min_average_read_quality", str(min_read_qual),
            "--exclude_bp_from_left", str(exclude_left),
            "--exclude_bp_from_right", str(exclude_right),
            "--n_processes", str(threads)
        ])

        if is_be_mode and be_center_idx is not None:
            cmd.extend([
                "--quantification_window_center", str(be_center_idx),
                "--cleavage_offset", "0",
                "--plot_window_size", str(be_sg_len),
                "--quantification_window_size", str(be_sg_len)
            ])
        else:
            cmd.extend([
                "--quantification_window_size", str(quant_window),
                "--cleavage_offset", str(cleavage_offset),
                "--plot_window_size", str(plot_window)
            ])

        if is_be_mode:
            cmd.append("--base_editor_output")
            if s_base_from and s_base_to:
                cmd.extend(["--conversion_nuc_from", s_base_from, "--conversion_nuc_to", s_base_to])
        elif mode in ["HDR", "Prime Editing (PE)"] and s_donor:
            cmd.extend(["--expected_hdr_amplicon_seq", s_donor])

        ret_code, out_text = global_runner.run_cmd(cmd, log_callback=log_callback)

        # Auto-retry if CRISPResso failed due to quantification window being excluded by left/right exclude parameters
        if ret_code != 0 and ("excluded" in out_text.lower() or "parameter error" in out_text.lower()):
            if log_callback:
                log_callback(f"[WARN] 样本 {s_name} sgRNA 位于 Amplicon 边缘被引物屏蔽机制覆盖，正在自动触发降级重试 (--exclude_bp_from_left 0 --exclude_bp_from_right 0)...\n")
            
            retry_cmd = []
            skip_next = False
            for arg_idx, arg in enumerate(cmd):
                if skip_next:
                    skip_next = False
                    continue
                if arg in ["--exclude_bp_from_left", "--exclude_bp_from_right"]:
                    retry_cmd.extend([arg, "0"])
                    skip_next = True
                else:
                    retry_cmd.append(arg)
                    
            ret_code, out_text = global_runner.run_cmd(retry_cmd, log_callback=log_callback)

        if ret_code == 0:
            if log_callback:
                log_callback(f"[OK] 样本 {s_name} 分析完成！\n")
            processed_dirs.append(sample_out_dir)
        else:
            if log_callback:
                log_callback(f"[FAIL] 样本 {s_name} 分析失败 (Exit code: {ret_code})\n")

    if progress_callback:
        progress_callback(total_samples, total_samples)

    today_date = time.strftime("%Y%m%d")
    
    if mode == "NHEJ":
        summary_excel_path = summarize_nhej_batch(samples, output_dir)
    elif mode == "Base Editing (BE)":
        summary_excel_path = summarize_be_batch(samples, output_dir)
    else:
        summary_excel_path = os.path.join(output_dir, f"{today_date}_HDR_PE_分析结果汇总.xlsx")
        summary_records = []
        for s in samples:
            s_name = s['name']
            s_out_dir = os.path.join(output_dir, s_name)
            stats = parse_crispresso_summary_output(s_out_dir) if os.path.exists(s_out_dir) else {'editing_efficiency': 'N/A', 'reads_total': 0, 'reads_aligned': 0}
            summary_records.append({
                '样品名': s_name,
                '描述': s['desc'],
                '编辑模式': mode,
                '编辑效率 %': stats['editing_efficiency'],
                '总读数 (Reads)': stats['reads_total'],
                '比对读数 (Aligned)': stats['reads_aligned']
            })
        df_sum = pd.DataFrame(summary_records)
        df_sum.to_excel(summary_excel_path, index=False)

    if log_callback:
        log_callback(f"\n[OK] 批量分析完成！汇总表格已导出至:\n  {summary_excel_path}\n")

    return processed_dirs, summary_excel_path

def run_summary_only_pipeline(
    excel_path: str,
    crispresso_dir: str,
    output_dir: str,
    edit_type: str = "Base Editing (BE)",
    log_callback: Optional[Callable[[str], None]] = None,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> str:
    """
    Execute ONLY the data summary step from existing CRISPResso2 output directories.
    Parses the sample sheet, extracts substitution & indel data from crispresso_dir,
    and writes the summary Excel workbook into output_dir.
    """
    if log_callback:
        log_callback(f"[INFO] 正在解析分析信息表: {excel_path}\n")

    # Try cql parsing first, fallback to standard crispresso sheet
    samples = []
    try:
        from core.cql_engine import parse_cql_sample_sheet
        samples = parse_cql_sample_sheet(excel_path)
    except Exception:
        pass
    if not samples:
        samples = parse_crispresso_sample_sheet(excel_path)

    if not samples:
        raise ValueError("未能从 Excel 表格中解析出有效样本，请检查表头或内容！")

    if log_callback:
        log_callback(f"[INFO] 成功载入 {len(samples)} 个样本条目。\n")
        log_callback(f"[INFO] 正在从结果目录提取数据: {crispresso_dir}\n")

    os.makedirs(output_dir, exist_ok=True)

    # Check if samples are BE or NHEJ
    be_samples = [s for s in samples if s.get('mode') == 'Base Editing (BE)']
    nhej_samples = [s for s in samples if s.get('mode') != 'Base Editing (BE)']

    summary_paths = []
    if "BE" in edit_type or be_samples:
        target_be = be_samples if be_samples else samples
        res_be = summarize_be_batch(target_be, crispresso_dir, log_callback=log_callback)
        if res_be and os.path.exists(res_be):
            final_be = os.path.join(output_dir, os.path.basename(res_be))
            if os.path.abspath(res_be) != os.path.abspath(final_be):
                shutil.copy2(res_be, final_be)
            summary_paths.append(final_be)
            if log_callback:
                log_callback(f"[OK] BE 分析汇总报表已生成: {final_be}\n")

    if ("NHEJ" in edit_type or "HDR" in edit_type or "PE" in edit_type or nhej_samples) and ("BE" not in edit_type or nhej_samples):
        target_nhej = nhej_samples if nhej_samples else samples
        res_nhej = summarize_nhej_batch(target_nhej, crispresso_dir, log_callback=log_callback)
        if res_nhej and os.path.exists(res_nhej):
            final_nhej = os.path.join(output_dir, os.path.basename(res_nhej))
            if os.path.abspath(res_nhej) != os.path.abspath(final_nhej):
                shutil.copy2(res_nhej, final_nhej)
            summary_paths.append(final_nhej)
            if log_callback:
                log_callback(f"[OK] NHEJ/HDR 分析汇总报表已生成: {final_nhej}\n")

    if progress_callback:
        progress_callback(1, 1)

    return "\n".join(summary_paths) if summary_paths else ""

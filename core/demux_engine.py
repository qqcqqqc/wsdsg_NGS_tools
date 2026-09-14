import os
import sys
import tempfile
import zipfile
import shutil
import re
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

def parse_excel_sample_sheet(xlsx_path: str) -> Dict[str, List[Dict[str, str]]]:
    """
    Parse sample sheet Excel file (.xlsx) into a dict grouped by library/pool name:
    {
       'Pool1': [
           {'name': 'Sample1', 'idx1': 'GAG', 'idx2': 'CAG'},
           ...
       ]
    }
    Flexibly supports dynamic headers and legacy index fallback.
    """
    if not os.path.exists(xlsx_path):
        raise FileNotFoundError(f"Excel 文件不存在: {xlsx_path}")

    lib_samples = defaultdict(list)

    try:
        df = pd.read_excel(xlsx_path)
        col_name = next((c for c in df.columns if '样品' in str(c) or 'Sample' in str(c) or 'sample' in str(c)), None)
        col_pool = next((c for c in df.columns if '库' in str(c) or 'Pool' in str(c) or 'Library' in str(c) or 'library' in str(c)), None)
        col_idx1 = next((c for c in df.columns if '索引1' in str(c) or 'idx1' in str(c).lower() or 'Index1' in str(c) or '索引序列1' in str(c)), None)
        col_idx2 = next((c for c in df.columns if '索引2' in str(c) or 'idx2' in str(c).lower() or 'Index2' in str(c) or '索引序列2' in str(c)), None)

        if col_name and col_idx1 and col_idx2:
            for _, row in df.iterrows():
                name = str(row[col_name]).strip() if pd.notna(row[col_name]) else ""
                raw_pool = str(row[col_pool]).strip() if col_pool and pd.notna(row[col_pool]) else ""
                if not raw_pool or raw_pool.lower() == 'nan':
                    raw_pool = "Default_Pool"
                idx1 = str(row[col_idx1]).strip() if pd.notna(row[col_idx1]) else ""
                idx2 = str(row[col_idx2]).strip() if pd.notna(row[col_idx2]) else ""

                if name and name.lower() != 'nan' and idx1 and idx2 and idx1.lower() != 'nan' and idx2.lower() != 'nan':
                    raw_pools = [p.strip() for p in re.split(r'[,，;；]+', raw_pool) if p.strip()]
                    seen_pools = set()
                    pools = []
                    for p in raw_pools:
                        if p not in seen_pools:
                            seen_pools.add(p)
                            pools.append(p)
                    if not pools:
                        pools = ["Default_Pool"]

                    clean_pool_tag = "_".join(pools)
                    target_base = f"{name}_on_{clean_pool_tag}"

                    sample_item = {
                        'name': name,
                        'idx1': idx1,
                        'idx2': idx2,
                        'pools': pools,
                        'clean_pool_tag': clean_pool_tag,
                        'target_base': target_base,
                    }
                    for p in pools:
                        lib_samples[p].append(sample_item)
            if lib_samples:
                return dict(lib_samples)
    except Exception as e:
        print(f"Dynamic header parsing failed: {e}")

    # Fallback to positional parsing for legacy templates...
    try:
        import openpyxl
        wb = openpyxl.load_workbook(xlsx_path, data_only=True)
        sheet = wb.active
        
        for row in sheet.iter_rows(min_row=2, values_only=True):
            if not row or len(row) < 4:
                continue
            name = str(row[1]).strip() if row[1] is not None else ""
            raw_pool = str(row[3]).strip() if row[3] is not None else "Default_Pool"
            idx1 = str(row[5]).strip() if len(row) > 5 and row[5] is not None else ""
            idx2 = str(row[7]).strip() if len(row) > 7 and row[7] is not None else ""
            
            if not name or name == 'None':
                continue
                
            if idx1 and idx2 and idx1 != 'None' and idx2 != 'None':
                raw_pools = [p.strip() for p in re.split(r'[,，;；]+', raw_pool) if p.strip()]
                seen_pools = set()
                pools = []
                for p in raw_pools:
                    if p not in seen_pools:
                        seen_pools.add(p)
                        pools.append(p)
                if not pools:
                    pools = ["Default_Pool"]

                clean_pool_tag = "_".join(pools)
                target_base = f"{name}_on_{clean_pool_tag}"

                sample_item = {
                    'name': name,
                    'idx1': idx1,
                    'idx2': idx2,
                    'pools': pools,
                    'clean_pool_tag': clean_pool_tag,
                    'target_base': target_base,
                }
                for p in pools:
                    lib_samples[p].append(sample_item)
        if lib_samples:
            return dict(lib_samples)
    except Exception:
        pass

    return dict(lib_samples)

def find_library_fastq_pairs(fastq_dir: str, lib_name: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Find R1 and R2 FASTQ files for a given library in fastq_dir with smart prefix/token fuzzy matching.
    Supports matching when user enters: 'BEV1-LJG7071', 'BEV1', 'BEV1-LJG7071_L1', etc.
    """
    if not os.path.exists(fastq_dir):
        return None, None
        
    all_fq_files = [f for f in sorted(os.listdir(fastq_dir)) if f.endswith('.fq.gz') or f.endswith('.fastq.gz') or f.endswith('.fq') or f.endswith('.fastq')]
    if not all_fq_files:
        return None, None

    matching_files = []
    
    if lib_name and lib_name != 'Default_Pool':
        lib_lower = lib_name.lower()
        
        # Priority 1: Exact token boundary match (e.g. CR1 matches CR1-xxx, CR1_xxx, but NOT CR10-xxx)
        boundary_pattern = re.compile(rf"(?:^|[_\-.])({re.escape(lib_lower)})(?:[_\-.]|$)", re.IGNORECASE)
        matching_files = [f for f in all_fq_files if boundary_pattern.search(f)]
        
        # Priority 2: Exact substring match
        if not matching_files:
            matching_files = [f for f in all_fq_files if lib_lower in f.lower()]
        
        # Priority 3: Token match (split by - or _)
        if not matching_files:
            tokens = [t for t in re.split(r'[-_.]', lib_lower) if len(t) >= 2]
            for token in tokens:
                matched = [f for f in all_fq_files if token in f.lower()]
                if matched:
                    matching_files = matched
                    break

        # Priority 4: Check if FASTQ filename prefix is contained inside lib_name
        if not matching_files:
            for f in all_fq_files:
                f_prefix = re.split(r'[_.-](?:R?1|R?2|001)', f, flags=re.IGNORECASE)[0].lower()
                if len(f_prefix) >= 2 and (f_prefix in lib_lower or lib_lower in f_prefix):
                    matching_files.append(f)

    # Fallback Priority 5: Single library folder fallback
    if not matching_files:
        matching_files = all_fq_files

    r1 = r2 = None
    for f in matching_files:
        if any(suffix in f for suffix in ['_1.fq', '_R1.fq', '_1.fastq', '_R1.fastq', '-1.fq', '-1.fastq', '.1.fq', '.1.fastq']):
            r1 = os.path.abspath(os.path.join(fastq_dir, f))
        elif any(suffix in f for suffix in ['_2.fq', '_R2.fq', '_2.fastq', '_R2.fastq', '-2.fq', '-2.fastq', '.2.fq', '.2.fastq']):
            r2 = os.path.abspath(os.path.join(fastq_dir, f))
            
    return r1, r2

def get_optimal_temp_dir() -> str:
    """
    Returns optimal temp directory for demux temporary output files.
    Prefers /dev/shm (RAM disk) on Linux/WSL if free space >= 2GB,
    otherwise uses default system temporary directory.
    """
    dev_shm = "/dev/shm"
    if os.path.exists(dev_shm) and os.access(dev_shm, os.W_OK):
        try:
            stat = shutil.disk_usage(dev_shm)
            if stat.free > 2 * 1024 * 1024 * 1024:
                tmp_dir = os.path.join(dev_shm, "ngs_demux_ram")
                os.makedirs(tmp_dir, exist_ok=True)
                return tmp_dir
        except Exception:
            pass
            
    tmp_dir = tempfile.mkdtemp(prefix="ngs_demux_")
    return os.path.abspath(tmp_dir)

def create_bidirectional_barcodes_fasta(lib: str, samples: List[Dict[str, str]], tmp_dir: str) -> Tuple[str, str]:
    """Generate dual-direction FASTA barcode files for cutadapt matching."""
    r1_fa = os.path.abspath(os.path.join(tmp_dir, f".barcodes_R1_{lib}.fa"))
    r2_fa = os.path.abspath(os.path.join(tmp_dir, f".barcodes_R2_{lib}.fa"))
    
    with open(r1_fa, 'w') as f1, open(r2_fa, 'w') as f2:
        for s in samples:
            base_name = f"{s['name']}_on_{lib}"
            c_idx1 = s['idx1'].strip().upper()
            c_idx2 = s['idx2'].strip().upper()
            
            name_fwd = f"{base_name}_FWD"
            f1.write(f">{name_fwd}\n{c_idx1}\n")
            f2.write(f">{name_fwd}\n{c_idx2}\n")
            
            name_rev = f"{base_name}_REV"
            f1.write(f">{name_rev}\n{c_idx2}\n")
            f2.write(f">{name_rev}\n{c_idx1}\n")
            
    return r1_fa, r2_fa

def run_demux_pipeline(
    excel_path: str,
    fastq_dir: str,
    output_dir: str,
    error_rate: float = 0.0,
    no_indels: bool = True,
    log_callback: Optional[Callable[[str], None]] = None,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> List[str]:
    """
    Run complete non-directional UDI demultiplexing pipeline.
    Returns list of generated sample fastq output files.
    """
    if log_callback:
        log_callback("=" * 60 + "\n")
        log_callback("  NGS Fastq 双端 UDI 拆分引擎启动\n")
        log_callback("=" * 60 + "\n")

    excel_path = os.path.abspath(excel_path)
    fastq_dir = os.path.abspath(fastq_dir)
    output_dir = os.path.abspath(output_dir)

    lib_samples = parse_excel_sample_sheet(excel_path)
    total_libs = len(lib_samples)
    
    multi_pool_samples = set()
    all_target_bases = set()
    for samples in lib_samples.values():
        for s in samples:
            t_base = s.get('target_base', f"{s['name']}_on_Default_Pool")
            all_target_bases.add(t_base)
            if len(s.get('pools', [])) > 1:
                multi_pool_samples.add((s['name'], s['clean_pool_tag']))

    if log_callback:
        log_callback(f"[INFO] 识别到文库数: {total_libs}\n")
        for lib, samples in lib_samples.items():
            log_callback(f"  ├ 文库 {lib}: {len(samples)} 个 UDI 样本\n")
        if multi_pool_samples:
            log_callback(f"  [智能跨库合并] 发现 {len(multi_pool_samples)} 个跨多文库样本，拆分时将自动汇入同一 FASTQ：\n")
            for s_name, pool_tag in sorted(multi_pool_samples):
                log_callback(f"    - {s_name} -> 跨库标签 [{pool_tag}]\n")

    os.makedirs(output_dir, exist_ok=True)
    # 预先清理本次运行的目标输出文件，杜绝断点重跑或重新执行时 'ab' 追加写入脏数据
    for t_base in all_target_bases:
        for r_ext in ['_R1.fastq.gz', '_R2.fastq.gz']:
            f_path = os.path.join(output_dir, f"{t_base}{r_ext}")
            if os.path.exists(f_path):
                try:
                    os.remove(f_path)
                except Exception:
                    pass

    for lib_idx, (lib, samples) in enumerate(lib_samples.items(), start=1):
        if progress_callback:
            progress_callback(lib_idx - 1, total_libs)
            
        r1_fastq, r2_fastq = find_library_fastq_pairs(fastq_dir, lib)
        if not r1_fastq or not r2_fastq:
            if log_callback:
                log_callback(f"[WARN] 找不到文库 {lib} 对应的 FASTQ 双端文件，跳过！\n")
            continue
            
        if log_callback:
            log_callback(f"\n[RUN] 正在拆分文库: {lib} ({len(samples)} 样本, 双端强校验模式)...\n")
            log_callback(f"  ├ R1: {os.path.basename(r1_fastq)}\n")
            log_callback(f"  └ R2: {os.path.basename(r2_fastq)}\n")

        tmp_dir = get_optimal_temp_dir()
        if log_callback:
            log_callback(f"  [I/O 策略] 使用临时缓存目录: {tmp_dir}\n")

        # 聚类共用相同 Barcode 配对的样本（多 sg 同扩增子）
        barcode_groups = defaultdict(list)
        for s in samples:
            b_key = (s['idx1'].strip().upper(), s['idx2'].strip().upper())
            rev_key = (b_key[1], b_key[0])
            if rev_key in barcode_groups:
                barcode_groups[rev_key].append(s)
            else:
                barcode_groups[b_key].append(s)

        unique_samples = [group[0] for group in barcode_groups.values()]
        shared_cnt = len(samples) - len(unique_samples)
        if log_callback and shared_cnt > 0:
            log_callback(f"  [智能识别] 发现 {shared_cnt} 个共用 Barcode 扩增子的样本（多 sg 同扩增子），拆分后将自动同步产出对应 FASTQ\n")

        try:
            r1_fa, r2_fa = create_bidirectional_barcodes_fasta(lib, unique_samples, tmp_dir)
            
            out_r1_pattern = os.path.abspath(os.path.join(tmp_dir, "{name}_R1.fastq.gz"))
            out_r2_pattern = os.path.abspath(os.path.join(tmp_dir, "{name}_R2.fastq.gz"))
            
            # 动态计算该文库中最小的 Index 长度，作为 -O 最小重叠阈值，杜绝短片段假阳性同时允许前缀剔除容错
            min_barcode_len = min(min(len(s['idx1'].strip()), len(s['idx2'].strip())) for s in samples) if samples else 10

            cmd = [
                "cutadapt",
                "-j", "0",
                "-e", str(error_rate),
                "-O", str(min_barcode_len)
            ]
            if no_indels:
                cmd.append("--no-indels")
                
            cmd.extend([
                "--pair-adapters",
                "-g", f"file:{win_to_wsl_path(r1_fa) if is_windows() else r1_fa}",
                "-G", f"file:{win_to_wsl_path(r2_fa) if is_windows() else r2_fa}",
                "-o", win_to_wsl_path(out_r1_pattern) if is_windows() else out_r1_pattern,
                "-p", win_to_wsl_path(out_r2_pattern) if is_windows() else out_r2_pattern,
                win_to_wsl_path(r1_fastq) if is_windows() else r1_fastq,
                win_to_wsl_path(r2_fastq) if is_windows() else r2_fastq
            ])
            
            ret_code, out_text = global_runner.run_cmd(cmd, log_callback=log_callback)
            
            if ret_code == 0:
                if log_callback:
                    log_callback(f"[OK] {lib} cutadapt 拆分完成，正在合并双向 Reads 并写入/同步样本 FASTQ...\n")
                
                merged_count = 0
                for group in barcode_groups.values():
                    primary_s = group[0]
                    base_name = f"{primary_s['name']}_on_{lib}"
                    fwd_r1 = os.path.join(tmp_dir, f"{base_name}_FWD_R1.fastq.gz")
                    rev_r1 = os.path.join(tmp_dir, f"{base_name}_REV_R1.fastq.gz")
                    fwd_r2 = os.path.join(tmp_dir, f"{base_name}_FWD_R2.fastq.gz")
                    rev_r2 = os.path.join(tmp_dir, f"{base_name}_REV_R2.fastq.gz")
                    
                    part_r1_chunks = []
                    part_r2_chunks = []
                    
                    if os.path.exists(fwd_r1) and os.path.getsize(fwd_r1) > 50:
                        with open(fwd_r1, 'rb') as in1:
                            part_r1_chunks.append(in1.read())
                        with open(fwd_r2, 'rb') as in2:
                            part_r2_chunks.append(in2.read())
                            
                    if os.path.exists(rev_r1) and os.path.getsize(rev_r1) > 50:
                        # 保证链方向与引物位置完全一致：
                        # 正向中 fwd_r1 对应 Index1/Primer1，fwd_r2 对应 Index2/Primer2
                        # 反向中 rev_r2 对应 Index1/Primer1，rev_r1 对应 Index2/Primer2
                        # 故合并时将 rev_r2 汇入 target_r1，rev_r1 汇入 target_r2
                        with open(rev_r2, 'rb') as in2:
                            part_r1_chunks.append(in2.read())
                        with open(rev_r1, 'rb') as in1:
                            part_r2_chunks.append(in1.read())
                            
                    if part_r1_chunks and part_r2_chunks:
                        # 对于该 Barcode 组下的所有样本（包含共享同一扩增子的多个 sg 样本）
                        for s in group:
                            target_base = s.get('target_base', f"{s['name']}_on_{lib}")
                            target_r1 = os.path.join(output_dir, f"{target_base}_R1.fastq.gz")
                            target_r2 = os.path.join(output_dir, f"{target_base}_R2.fastq.gz")
                            
                            # 使用 'ab' 二进制追加模式写出，支持单库写入及跨多库流式无缝合并
                            with open(target_r1, 'ab') as out1, open(target_r2, 'ab') as out2:
                                for c in part_r1_chunks:
                                    out1.write(c)
                                for c in part_r2_chunks:
                                    out2.write(c)
                                    
                            merged_count += 1
                            if log_callback:
                                if s is not primary_s:
                                    log_callback(f"  ├ [共享扩增子] 样本 {s['name']} 与 {primary_s['name']} 共享同一扩增子，已自动同步写出/汇入 {os.path.basename(target_r1)}\n")
                                elif len(s.get('pools', [])) > 1:
                                    log_callback(f"  ├ [跨库合并] 样本 {s['name']} (跨库: {s['clean_pool_tag']}) 文库 {lib} 数据已汇入 {os.path.basename(target_r1)}\n")
                        
                if log_callback:
                    log_callback(f"[OK] 文库 {lib} 成功处理 {merged_count} 个样本条目\n")
            else:
                if log_callback:
                    log_callback(f"[FAIL] 文库 {lib} 拆分失败 (Exit code: {ret_code})\n")
                    
        finally:
            if os.path.exists(tmp_dir):
                try:
                    shutil.rmtree(tmp_dir)
                except Exception:
                    pass

    # 汇总有效输出文件并清理空文件
    generated_files = []
    for t_base in sorted(all_target_bases):
        r1 = os.path.join(output_dir, f"{t_base}_R1.fastq.gz")
        r2 = os.path.join(output_dir, f"{t_base}_R2.fastq.gz")
        if os.path.exists(r1) and os.path.exists(r2):
            if os.path.getsize(r1) > 50 and os.path.getsize(r2) > 50:
                generated_files.extend([r1, r2])
            else:
                try: os.remove(r1)
                except Exception: pass
                try: os.remove(r2)
                except Exception: pass

    if progress_callback:
        progress_callback(total_libs, total_libs)

    if log_callback:
        multi_info = f"（包含 {len(multi_pool_samples)} 个跨库合并样本）" if multi_pool_samples else ""
        log_callback(f"\n[COMPLETE] 全部拆分工作完成！共生成 {len(generated_files)} 个 FASTQ.GZ 文件{multi_info}。\n")

    return generated_files

# -*- coding: utf-8 -*-
import os, sys, json, zipfile, argparse

def refine_single_run(run_dir, plot_left=0, plot_right=0):
    if plot_left < 0 or plot_right < 0:
        return True
    info_path = os.path.join(run_dir, 'CRISPResso2_info.json')
    if not os.path.exists(info_path):
        candidates = [
            os.path.join(run_dir, d) for d in os.listdir(run_dir)
            if os.path.isdir(os.path.join(run_dir, d)) and os.path.exists(os.path.join(run_dir, d, 'CRISPResso2_info.json'))
        ]
        if candidates:
            run_dir = candidates[0]
            info_path = os.path.join(run_dir, 'CRISPResso2_info.json')
        else:
            print('[WARN] No CRISPResso2_info.json found in ' + str(run_dir))
            return False
    try:
        import matplotlib
        matplotlib.use('Agg')
        import pandas as pd
        from CRISPResso2 import CRISPRessoPlot as cp
    except ImportError as e:
        print('[WARN] Failed to import CRISPResso2 modules: ' + str(e))
        return False

    with open(info_path, 'r', encoding='utf-8') as f:
        info = json.load(f)
    refs_data = info.get('results', {}).get('refs', {})
    if not refs_data:
        return False

    nuc_table_path = os.path.join(run_dir, 'Nucleotide_percentage_table.txt')
    mod_table_path = os.path.join(run_dir, 'Modification_count_vectors.txt')
    has_nuc_data = os.path.exists(nuc_table_path) and os.path.exists(mod_table_path)
    zip_path = os.path.join(run_dir, 'Alleles_frequency_table.zip')
    has_zip_data = os.path.exists(zip_path)

    for ref_name, ref in refs_data.items():
        ref_seq = ref.get('sequence', '')
        ref_len = len(ref_seq)
        sg_intervals = ref.get('sgRNA_intervals', [])
        if not ref_seq or not sg_intervals:
            continue
        for i, (sg_start, sg_end) in enumerate(sg_intervals):
            st = max(0, sg_start - plot_left)
            en = min(ref_len - 1, sg_end + plot_right)
            ref_sub_seq = ref_seq[st : en + 1]

            if has_nuc_data and 'plot_2b_roots' in ref and i < len(ref['plot_2b_roots']):
                try:
                    root_name = ref['plot_2b_roots'][i]
                    plot_root = os.path.join(run_dir, root_name)
                    nuc_df = pd.read_csv(nuc_table_path, sep='	', index_col=0)
                    nuc_df_for_plot = nuc_df.reset_index()
                    nuc_df_for_plot.columns.values[0] = 'Nucleotide'
                    nuc_df_for_plot.insert(0, 'Batch', ref_name)

                    mod_df = pd.read_csv(mod_table_path, sep='	', index_col=0)
                    tot = float(mod_df.loc['Total'].iloc[0])
                    mod_pct_df = mod_df.copy().astype(float) / tot
                    mod_pct_df.loc['Total'] = tot
                    mod_pct_df = mod_pct_df.reset_index()
                    mod_pct_df.columns.values[0] = 'Modification'
                    mod_pct_df.insert(0, 'Batch', ref_name)

                    sel_cols = [0, 1] + list(range(st + 2, en + 3))
                    sub_nuc = nuc_df_for_plot.iloc[:, sel_cols].copy()
                    sub_mod = mod_pct_df.iloc[:, sel_cols].copy()
                    sub_nuc.columns = ['Batch', 'Nucleotide'] + list(ref_sub_seq)
                    sub_mod.columns = ['Batch', 'Modification'] + list(ref_sub_seq)

                    new_sg_intervals = [(sg_start - st, sg_end - st)]
                    new_include_idx = None
                    if 'sgRNA_include_idxs' in ref and i < len(ref['sgRNA_include_idxs']):
                        new_include_idx = [x - st for x in ref['sgRNA_include_idxs'][i]]

                    cp.plot_nucleotide_quilt(
                        nuc_pct_df=sub_nuc,
                        mod_pct_df=sub_mod,
                        fig_filename_root=plot_root,
                        save_also_png=True,
                        sgRNA_intervals=new_sg_intervals,
                        sgRNA_names=ref.get('sgRNA_names', []),
                        sgRNA_mismatches=ref.get('sgRNA_mismatches', []),
                        quantification_window_idxs=new_include_idx
                    )
                    print('[REFINED] Updated Figure 2b: ' + root_name)
                except Exception as e:
                    print('[WARN] Failed Figure 2b: ' + str(e))

            if has_zip_data and 'plot_9_roots' in ref and i < len(ref['plot_9_roots']):
                try:
                    root_name = ref['plot_9_roots'][i]
                    plot_root = os.path.join(run_dir, root_name)
                    zf = zipfile.ZipFile(zip_path)
                    df_alleles = pd.read_csv(zf.open('Alleles_frequency_table.txt'), sep='	')
                    df_ref = df_alleles.loc[df_alleles['Reference_Name'] == ref_name]

                    def slice_row(row):
                        r_seq = row['Reference_Sequence']
                        a_seq = row['Aligned_Sequence']
                        pos = 0; st_idx = -1; en_idx = -1
                        for idx, c in enumerate(r_seq):
                            if c != '-':
                                if pos == st: st_idx = idx
                                if pos == en: en_idx = idx; break
                                pos += 1
                        if st_idx == -1: st_idx = 0
                        if en_idx == -1: en_idx = len(r_seq) - 1
                        sub_aln = a_seq[st_idx : en_idx + 1]
                        sub_ref = r_seq[st_idx : en_idx + 1]
                        is_unedited = (sub_aln == sub_ref)
                        n_del = sub_aln.count('-')
                        n_ins = sub_ref.count('-')
                        n_mut = sum(1 for a, r in zip(sub_aln, sub_ref) if a != r and a != '-' and r != '-')
                        return sub_aln, sub_ref, is_unedited, n_del, n_ins, n_mut, row['#Reads'], row['%Reads']

                    sliced_data = [slice_row(r) for _, r in df_ref.iterrows()]
                    df_around = pd.DataFrame(
                        sliced_data,
                        columns=['Aligned_Sequence', 'Reference_Sequence', 'Unedited', 'n_deleted', 'n_inserted', 'n_mutated', '#Reads', '%Reads']
                    )
                    txt_filename = plot_root.replace('9.', '') + '.txt'
                    if not txt_filename.endswith('.txt'):
                        txt_filename += '.txt'
                    df_around.to_csv(txt_filename, sep='	', index=False)

                    df_grouped = df_around.groupby(['Aligned_Sequence', 'Reference_Sequence']).agg({
                        '#Reads': 'sum', '%Reads': 'sum', 'Unedited': 'first',
                        'n_deleted': 'first', 'n_inserted': 'first', 'n_mutated': 'first'
                    }).reset_index().set_index('Aligned_Sequence')
                    df_grouped.sort_values(by=['#Reads', 'Aligned_Sequence', 'Reference_Sequence'], inplace=True, ascending=[False, True, True])

                    new_sgRNA_intervals = [(sg_start - st, sg_end - st)]
                    cut_point = ref['sgRNA_cut_points'][i] if ('sgRNA_cut_points' in ref and i < len(ref['sgRNA_cut_points'])) else None
                    plot_cut_point = ref['sgRNA_plot_cut_points'][i] if ('sgRNA_plot_cut_points' in ref and i < len(ref['sgRNA_plot_cut_points'])) else True
                    pass_cut_point = (cut_point is not None and st <= cut_point <= en)
                    new_cut_point = (cut_point - st) if pass_cut_point else None

                    prepped_df_alleles, annotations, y_labels, insertion_dict, per_element_annot_kws, is_reference = cp.prep_alleles_table(
                        df_grouped, ref_sub_seq, 50, 0.2
                    )
                    cp.plot_alleles_table_prepped(
                        reference_seq=ref_sub_seq,
                        prepped_df_alleles=prepped_df_alleles,
                        annotations=annotations,
                        y_labels=y_labels,
                        insertion_dict=insertion_dict,
                        per_element_annot_kws=per_element_annot_kws,
                        is_reference=is_reference,
                        fig_filename_root=plot_root,
                        SAVE_ALSO_PNG=True,
                        plot_cut_point=plot_cut_point,
                        cut_point_ind=new_cut_point,
                        sgRNA_intervals=new_sgRNA_intervals,
                        sgRNA_names=ref.get('sgRNA_names', [])
                    )
                    print('[REFINED] Updated Figure 9: ' + root_name)
                except Exception as e:
                    print('[WARN] Failed Figure 9: ' + str(e))
    return True

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run_dir', required=True)
    parser.add_argument('--plot_left', type=int, default=0)
    parser.add_argument('--plot_right', type=int, default=0)
    args = parser.parse_args()
    refine_single_run(args.run_dir, args.plot_left, args.plot_right)

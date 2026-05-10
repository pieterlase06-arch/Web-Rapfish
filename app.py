import os
import sys
import subprocess

# ==========================================
# SISTEM AUTO-INSTALLER
# ==========================================
def pastikan_library_lengkap():
    library_wajib = {
        'flask': 'Flask',
        'pandas': 'pandas',
        'numpy': 'numpy',
        'sklearn': 'scikit-learn',
        'xlsxwriter': 'xlsxwriter',
        'openpyxl': 'openpyxl',
        'xlrd': 'xlrd'
    }
    for modul, nama_pip in library_wajib.items():
        try:
            __import__(modul)
        except ImportError:
            print(f"[*] Menginstal otomatis library: {nama_pip}...")
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', nama_pip])

pastikan_library_lengkap()

from flask import Flask, request, jsonify, render_template, send_file
import pandas as pd
import numpy as np
from sklearn.manifold import MDS
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import pairwise_distances
import io
import traceback

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

# Fungsi Rotasi Procrustes
def rotate_and_scale(coords):
    good = coords[0]
    bad = coords[-1]
    translated = coords - bad
    angle = np.arctan2(translated[0][1], translated[0][0])
    c, s = np.cos(-angle), np.sin(-angle)
    R = np.array(((c, -s), (s, c)))
    rotated = translated.dot(R.T)
    scale_factor = 100.0 / rotated[0, 0] if rotated[0, 0] != 0 else 1.0
    scaled = rotated * scale_factor
    return scaled, rotated

@app.route('/analyze', methods=['POST'])
def analyze():
    if 'file' not in request.files:
        return jsonify({"status": "error", "error": "Tidak ada file"})
    file = request.files['file']
    filename = file.filename
    
    try:
        param_start_text_col = int(request.form.get('start_text_col', 1))
        param_end_text_col = int(request.form.get('end_text_col', 2))
        param_start_score_col = int(request.form.get('start_score_col', 3))
        param_end_score_col = request.form.get('end_score_col', '').strip()
        param_start_row = int(request.form.get('start_row', 2))
        param_end_row = int(request.form.get('end_row', 18))
        mc_iter = int(request.form.get('mc_iterations', 50))

        start_text_col = param_start_text_col - 1
        start_score_col = param_start_score_col - 1
        start_row = param_start_row - 2
        end_row = param_end_row - 1 

        if start_row < 0: start_row = 0

        print(f"\n[1/5] Memproses File: {filename}")
        if filename.endswith('.csv'):
            df = pd.read_csv(file)
        elif filename.endswith(('.xls', '.xlsx')):
            mesin = 'xlrd' if filename.endswith('.xls') else 'openpyxl'
            xls = pd.ExcelFile(file, engine=mesin)
            sheet_target = xls.sheet_names[0]
            df = pd.read_excel(xls, sheet_name=sheet_target)
        
        end_row = min(end_row, len(df))
        df_sliced = df.iloc[start_row:end_row].copy()
        labels = df_sliced.iloc[:, start_text_col].astype(str).tolist()

        if param_end_score_col:
            end_score_col = min(int(param_end_score_col), len(df.columns))
            raw_data = df_sliced.iloc[:, start_score_col:end_score_col].copy()
        else:
            raw_data = df_sliced.iloc[:, start_score_col:].copy()
        
        for col in raw_data.columns:
            raw_str = raw_data[col].astype(str).str.replace(',', '.', regex=False)
            raw_data[col] = pd.to_numeric(raw_str, errors='coerce')
        
        data_to_process = raw_data.fillna(0.0).astype(float)
        valid_cols = (data_to_process != 0).any(axis=0)
        data_to_process = data_to_process.loc[:, valid_cols]
        
        if data_to_process.empty or len(data_to_process) < 2:
            return jsonify({"status": "error", "error": "Data kosong setelah dipotong."})
        
        max_vals, min_vals = data_to_process.max(axis=0), data_to_process.min(axis=0)
        for col in data_to_process.columns:
            if max_vals[col] == min_vals[col]: max_vals[col] += 0.01

        data_with_anchors = pd.concat([pd.DataFrame([max_vals], columns=data_to_process.columns), data_to_process, pd.DataFrame([min_vals], columns=data_to_process.columns)], ignore_index=True)
        
        scaler = MinMaxScaler()
        scaled_data = np.nan_to_num(scaler.fit_transform(data_with_anchors))
        
        print("[3/5] SIMULASI ALSCAL SPSS...")
        dist_matrix = pairwise_distances(scaled_data, metric='euclidean')
        
        # MDS configuration closer to classic Rapfish (Metric MDS)
        mds = MDS(n_components=2, dissimilarity='precomputed', random_state=42, n_init=20, max_iter=2000, eps=1e-7)
        raw_coords = mds.fit_transform(dist_matrix)
        
        # Calculate Kruskal's Stress-1
        fitted_dist = pairwise_distances(raw_coords, metric='euclidean')
        mask = np.triu(np.ones(dist_matrix.shape), k=1).astype(bool)
        
        # Original distances (d_ij) and fitted distances (hat_d_ij)
        d_ij = dist_matrix[mask]
        hat_d_ij = fitted_dist[mask]
        
        stress_1 = np.sqrt(np.sum((hat_d_ij - d_ij)**2) / np.sum(d_ij**2))
        stress = round(float(stress_1), 4)
        
        # Calculate Squared Correlation (RSQ)
        correlation_matrix = np.corrcoef(d_ij, hat_d_ij)
        rsq = round(float(correlation_matrix[0, 1]**2), 4)

        scaled_coords, rotated_coords = rotate_and_scale(raw_coords)
        
        labels_with_anchors = ["GOOD"] + labels + ["BAD"]
        rap_full_data = []
        for i in range(len(labels_with_anchors)):
            rap_full_data.append({
                "label": labels_with_anchors[i],
                "raw_x": round(float(raw_coords[i][0]), 4), "raw_y": round(float(raw_coords[i][1]), 4),
                "rot_x": round(float(rotated_coords[i][0]), 4), "rot_y": round(float(rotated_coords[i][1]), 4),
                "scl_x": round(float(scaled_coords[i][0]), 4), "scl_y": round(float(scaled_coords[i][1]), 4)
            })

        final_coords = [{"label": labels[i-1], "x": round(float(scaled_coords[i][0]), 3), "y": round(float(scaled_coords[i][1]), 3)} for i in range(1, len(scaled_coords) - 1)]
        distances = [{"titik1": labels[i-1], "titik2": labels[j-1], "jarak": round(float(dist_matrix[i][j]), 3)} for i in range(1, len(labels)+1) for j in range(i+1, len(labels)+1)]

        print(f"[4/5] Menghitung Leverage Matriks SPSS...")
        leverage_results = []
        leverage_scores_dict = {}
        base_scores = [pt['x'] for pt in final_coords]
        attrs = data_to_process.columns.tolist()

        for col_idx in range(len(attrs)):
            attr_name = str(attrs[col_idx])
            temp_scaled = np.delete(scaled_data, col_idx, axis=1)
            temp_dist = pairwise_distances(temp_scaled, metric='euclidean')
            temp_coords = mds.fit_transform(temp_dist)
            temp_scl, _ = rotate_and_scale(temp_coords)
            
            scores_when_removed = [float(temp_scl[i][0]) for i in range(1, len(temp_scl) - 1)]
            leverage_scores_dict[attr_name] = scores_when_removed
            
            # Leverage is often expressed as the difference in sustainability score
            diffs = [scores_when_removed[i] - base_scores[i] for i in range(len(base_scores))]
            rms = np.sqrt(np.mean([d**2 for d in diffs]))
            leverage_results.append({"atribut": attr_name, "leverage": round(float(rms), 3)})
        
        leverage_matrix_data = []
        for i, label in enumerate(labels):
            row = {"label": label}
            for attr in attrs:
                row[str(attr)] = round(leverage_scores_dict[str(attr)][i], 4)
            leverage_matrix_data.append(row)

        leverage_results_sorted = sorted(leverage_results, key=lambda k: k['leverage'], reverse=True)

        print(f"[5/5] Menghitung Monte Carlo ({mc_iter} iterasi)...")
        mc_results = []
        mc_grouped = {label: {'x': [], 'y': []} for label in labels}
        
        mc_matrix_excel = []

        for _ in range(mc_iter):
            # Normal distribution of error as per Rapfish manual (approx 25% of range)
            noise = np.random.normal(0, 0.05, scaled_data.shape)
            mc_dist = pairwise_distances(scaled_data + noise, metric='euclidean')
            mc_scl, _ = rotate_and_scale(mds.fit_transform(mc_dist))
            
            iter_row = {}
            for i in range(1, len(mc_scl)-1):
                lbl, x_val, y_val = labels[i-1], float(mc_scl[i][0]), float(mc_scl[i][1])
                mc_results.append({"label": lbl, "x": round(x_val, 3), "y": round(y_val, 3)})
                mc_grouped[lbl]['x'].append(x_val)
                mc_grouped[lbl]['y'].append(y_val)
                iter_row[lbl] = round(x_val, 4)
            mc_matrix_excel.append(iter_row)

        mc_summary = []
        mc_distributions = {} # For Histogram
        for lbl in labels:
            x_arr, y_arr = mc_grouped[lbl]['x'], mc_grouped[lbl]['y']
            if not x_arr: continue
            
            # Store full X distribution for histograms
            mc_distributions[lbl] = [round(val, 2) for val in x_arr]
            
            med_x, med_y = np.median(x_arr), np.median(y_arr)
            x_2_5, x_97_5, y_2_5, y_97_5 = np.percentile(x_arr, 2.5), np.percentile(x_arr, 97.5), np.percentile(y_arr, 2.5), np.percentile(y_arr, 97.5)
            x_25, x_75, y_25, y_75 = np.percentile(x_arr, 25), np.percentile(x_arr, 75), np.percentile(y_arr, 25), np.percentile(y_arr, 75)

            mc_summary.append({
                "label": lbl, "med_x": round(med_x, 3), "med_y": round(med_y, 3),
                "x_minus_95": round(med_x - x_2_5, 3), "x_plus_95": round(x_97_5 - med_x, 3),
                "y_minus_95": round(med_y - y_2_5, 3), "y_plus_95": round(y_97_5 - med_y, 3),
                "x_minus_50": round(med_x - x_25, 3),  "x_plus_50": round(x_75 - med_x, 3),
                "y_minus_50": round(med_y - y_25, 3),  "y_plus_50": round(y_75 - med_y, 3),
                "x2_5": round(x_2_5, 3), "x97_5": round(x_97_5, 3),
                "y2_5": round(y_2_5, 3), "y97_5": round(y_97_5, 3),
                "x25": round(x_25, 3), "x75": round(x_75, 3),
                "y25": round(y_25, 3), "y75": round(y_75, 3)
            })

        params_info = {
            "Start text col.": param_start_text_col,
            "End text col.": param_end_text_col,
            "Start score col.": param_start_score_col,
            "End score col.": param_end_score_col if param_end_score_col else len(df.columns),
            "Start row": param_start_row,
            "End row": param_end_row,
            "No of Iterations": mc_iter
        }

        print("Selesai! Mengirim ke web...")
        return jsonify({
            "status": "success",
            "rap_analysis": final_coords,
            "rap_full_data": rap_full_data,
            "distances": distances,
            "leverage": leverage_results_sorted,
            "leverage_matrix": leverage_matrix_data,
            "leverage_raw_results": leverage_results, 
            "monte_carlo": mc_results,
            "mc_matrix": mc_matrix_excel, 
            "mc_summary": mc_summary,
            "mc_distributions": mc_distributions,
            "params_info": params_info,
            "stress": stress,
            "rsq": rsq
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"status": "error", "error": str(e)})

@app.route('/export_excel', methods=['POST'])
def export_excel():
    try:
        data = request.get_json(silent=True) or {}
        output = io.BytesIO()
        
        rap_full = data.get('rap_full_data', [])
        rap_front = data.get('rap_analysis', [])
        dist_data = data.get('distances', [])
        lev_front = data.get('leverage', [])
        lev_matrix = data.get('leverage_matrix', [])
        lev_raw = data.get('leverage_raw_results', [])
        mc_data = data.get('monte_carlo', [])
        mc_mat = data.get('mc_matrix', [])
        mc_sum = data.get('mc_summary', [])
        params_info = data.get('params_info', {})
        stress_val = data.get('stress', 0)
        rsq_val = data.get('rsq', 0)
        
        l_rap = max(1, len(rap_front))
        l_lev = max(1, len(lev_front))
        l_mc = max(1, len(mc_data))
        l_sum = max(1, len(mc_sum))
        
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            workbook = writer.book

            # ==========================================
            # 1. SHEET RAP ANALYSIS (Kloning Tabel SPSS)
            # ==========================================
            worksheet_rap = workbook.add_worksheet('RapAnalysis')
            writer.sheets['RapAnalysis'] = worksheet_rap
            
            worksheet_rap.write('B1', '2D MDS Results')
            worksheet_rap.write('E1', 'Rotated')
            worksheet_rap.write('H1', '& Flipped & Scaled')
            worksheet_rap.write('K1', 'RAPFISH PARAMETERS')
            
            headers = ['Fisheries', 'Dim 1', 'Dim 2', '', 'Dim 1', 'Dim 2', '', 'Score (X)', 'Dim 2']
            for col_num, head in enumerate(headers):
                worksheet_rap.write(1, col_num, head)
            
            for r_idx, row_dict in enumerate(rap_full):
                r = r_idx + 2
                worksheet_rap.write(r, 0, row_dict['label'])
                worksheet_rap.write(r, 1, row_dict['raw_x'])
                worksheet_rap.write(r, 2, row_dict['raw_y'])
                worksheet_rap.write(r, 4, row_dict['rot_x'])
                worksheet_rap.write(r, 5, row_dict['rot_y'])
                worksheet_rap.write(r, 7, row_dict['scl_x'])
                worksheet_rap.write(r, 8, row_dict['scl_y'])
            
            p_row = 1
            for k, v in params_info.items():
                worksheet_rap.write(p_row, 10, str(k))
                worksheet_rap.write(p_row, 11, v)
                p_row += 1
            worksheet_rap.write(p_row, 10, 'Stress')
            worksheet_rap.write(p_row, 11, stress_val)
            worksheet_rap.write(p_row + 1, 10, 'RSQ')
            worksheet_rap.write(p_row + 1, 11, rsq_val)
            
            last_idx = len(rap_full) + 1
            chart_rap = workbook.add_chart({'type': 'scatter'})
            chart_rap.add_series({
                'name': 'MDS Ordination',
                'categories': ['RapAnalysis', 2, 7, last_idx, 7], 
                'values':     ['RapAnalysis', 2, 8, last_idx, 8], 
                'marker': {'type': 'diamond', 'size': 8, 'fill': {'color': '#1a73e8'}},
                'data_labels': {'value': True, 'position': 'right'}
            })
            chart_rap.set_title({'name': 'MDS Ordination (RapAnalysis)'})
            chart_rap.set_x_axis({'name': 'Sustainability Score (0-100)', 'min': 0, 'max': 100})
            chart_rap.set_legend({'position': 'none'})
            chart_rap.set_size({'width': 720, 'height': 480})
            worksheet_rap.insert_chart('D25', chart_rap) 
            
            # ==========================================
            # 2. SHEET LEVERAGE (Matriks Skor per Atribut)
            # ==========================================
            df_lev_mat = pd.DataFrame(lev_matrix)
            if 'label' in df_lev_mat.columns:
                df_lev_mat.rename(columns={'label': 'Fisheries'}, inplace=True)
            
            # Menghitung SE dan RMS ke dalam baris Excel secara manual
            df_lev_mat.to_excel(writer, sheet_name='LeverageAttributes', index=False)
            worksheet_lev = writer.sheets['LeverageAttributes']
            
            last_row = len(df_lev_mat) + 1
            worksheet_lev.write(last_row, 0, 'Root Mean Square')
            for col_idx, lev_obj in enumerate(lev_raw):
                worksheet_lev.write(last_row, col_idx + 1, lev_obj['leverage'])
            
            chart_lev = workbook.add_chart({'type': 'bar'}) 
            # Menggunakan data dari hasil sorting untuk Grafik
            start_vert = last_row + 4
            df_lev_front = pd.DataFrame(lev_front)
            if not df_lev_front.empty:
                df_lev_front.rename(columns={'atribut': 'Atribut', 'leverage': 'RMS Error'}, inplace=True)
                df_lev_front.to_excel(writer, sheet_name='LeverageAttributes', startrow=start_vert, index=False)
                chart_lev.add_series({
                    'name': 'RMS Error',
                    'categories': ['LeverageAttributes', start_vert+1, 0, start_vert+l_lev, 0],
                    'values':     ['LeverageAttributes', start_vert+1, 1, start_vert+l_lev, 1],
                    'fill': {'color': '#e74c3c'}
                })
                chart_lev.set_title({'name': 'Leverage Attributes (Sensitivitas)'})
                chart_lev.set_y_axis({'reverse': True})
                chart_lev.set_legend({'position': 'none'})
                chart_lev.set_size({'width': 720, 'height': max(480, l_lev * 20)})
                worksheet_lev.insert_chart('N2', chart_lev)
            
            # ==========================================
            # 3. SHEET MONTE CARLO (Format Matrix Kolom Iterasi)
            # ==========================================
            df_mc_mat = pd.DataFrame(mc_mat)
            df_mc_mat.to_excel(writer, sheet_name='MonteCarlo', index=False)
            worksheet_mc = writer.sheets['MonteCarlo']
            
            cols_export = ['label', 'med_x', 'med_y', 'x_minus_95', 'x_plus_95', 'y_minus_95', 'y_plus_95', 'x_minus_50', 'x_plus_50', 'y_minus_50', 'y_plus_50']
            df_mc_sum = pd.DataFrame(mc_sum)
            # Tulis di jarak agak jauh dari matriks
            start_col_sum = len(df_mc_mat.columns) + 2
            (df_mc_sum[cols_export] if not df_mc_sum.empty else pd.DataFrame(columns=cols_export)).to_excel(writer, sheet_name='MonteCarlo', startcol=start_col_sum, index=False)
            
            # Tulis data X Y panjang (Untuk gambar scatter)
            start_col_raw = start_col_sum + 12
            df_mc = pd.DataFrame(mc_data)
            if 'label' in df_mc.columns: df_mc.rename(columns={'label': 'Lokasi', 'x': 'Score X', 'y': 'Dimensi Y'}, inplace=True)
            df_mc.to_excel(writer, sheet_name='MonteCarlo', startcol=start_col_raw, index=False)

            chart_mc_raw = workbook.add_chart({'type': 'scatter'})
            chart_mc_raw.add_series({
                'name': 'Semua Iterasi',
                'categories': ['MonteCarlo', 1, start_col_raw+1, l_mc, start_col_raw+1], 
                'values':     ['MonteCarlo', 1, start_col_raw+2, l_mc, start_col_raw+2],
                'marker': {'type': 'circle', 'size': 3, 'fill': {'color': '#bdc3c7'}, 'border': {'none': True}}
            })
            chart_mc_raw.set_title({'name': 'Rapfish Ordination - Monte Carlo Scatter Plot'})
            chart_mc_raw.set_x_axis({'name': 'Sustainability Score', 'min': 0, 'max': 100})
            chart_mc_raw.set_legend({'position': 'none'})
            chart_mc_raw.set_size({'width': 650, 'height': 350})
            worksheet_mc.insert_chart(f'A{len(df_mc_mat)+5}', chart_mc_raw)

            chart_mc_95 = workbook.add_chart({'type': 'scatter'})
            chart_mc_95.add_series({
                'name': 'Median (95% CI)',
                'categories': ['MonteCarlo', 1, start_col_sum+1, l_sum, start_col_sum+1], 
                'values':     ['MonteCarlo', 1, start_col_sum+2, l_sum, start_col_sum+2],
                'marker': {'type': 'circle', 'size': 6, 'fill': {'color': '#2980b9'}},
                'x_error_bars': {'type': 'custom', 'minus_values': ['MonteCarlo', 1, start_col_sum+3, l_sum, start_col_sum+3], 'plus_values':  ['MonteCarlo', 1, start_col_sum+4, l_sum, start_col_sum+4]},
                'y_error_bars': {'type': 'custom', 'minus_values': ['MonteCarlo', 1, start_col_sum+5, l_sum, start_col_sum+5], 'plus_values':  ['MonteCarlo', 1, start_col_sum+6, l_sum, start_col_sum+6]}
            })
            chart_mc_95.set_title({'name': 'Rapfish Ordination Monte Carlo (95% CI Error Bars)'})
            chart_mc_95.set_x_axis({'name': 'Sustainability Score', 'min': 0, 'max': 100})
            chart_mc_95.set_legend({'position': 'none'})
            chart_mc_95.set_size({'width': 650, 'height': 350})
            worksheet_mc.insert_chart(f'A{len(df_mc_mat)+25}', chart_mc_95)

            chart_mc_50 = workbook.add_chart({'type': 'scatter'})
            chart_mc_50.add_series({
                'name': 'Median (50% IQR)',
                'categories': ['MonteCarlo', 1, start_col_sum+1, l_sum, start_col_sum+1], 
                'values':     ['MonteCarlo', 1, start_col_sum+2, l_sum, start_col_sum+2],
                'marker': {'type': 'square', 'size': 6, 'fill': {'color': '#27ae60'}},
                'x_error_bars': {'type': 'custom', 'minus_values': ['MonteCarlo', 1, start_col_sum+7, l_sum, start_col_sum+7], 'plus_values':  ['MonteCarlo', 1, start_col_sum+8, l_sum, start_col_sum+8]},
                'y_error_bars': {'type': 'custom', 'minus_values': ['MonteCarlo', 1, start_col_sum+9, l_sum, start_col_sum+9], 'plus_values':  ['MonteCarlo', 1, start_col_sum+10, l_sum, start_col_sum+10]}
            })
            chart_mc_50.set_title({'name': 'Rapfish Monte Carlo Ordination (50% Inter-quartile Error Bars)'})
            chart_mc_50.set_x_axis({'name': 'Sustainability Score', 'min': 0, 'max': 100})
            chart_mc_50.set_legend({'position': 'none'})
            chart_mc_50.set_size({'width': 650, 'height': 350})
            worksheet_mc.insert_chart(f'K{len(df_mc_mat)+25}', chart_mc_50)

            # ==========================================
            # 4. SHEET DISTANCES
            # ==========================================
            df_dist = pd.DataFrame(dist_data)
            if not df_dist.empty:
                if 'titik1' in df_dist.columns: df_dist.rename(columns={'titik1': 'Titik A', 'titik2': 'Titik B', 'jarak': 'Jarak Euclidean'}, inplace=True)
                df_dist.to_excel(writer, sheet_name='Distances', index=False)

        output.seek(0)
        return send_file(output, as_attachment=True, download_name="Hasil_Rapfish_SPSS.xlsx", mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    except Exception as e:
        traceback.print_exc()
        return f"GAGAL MEMBUAT EXCEL: {str(e)}", 500

if __name__ == '__main__':
    app.run(debug=True)
import os
import sys
import subprocess
import webbrowser
import io
import traceback
from threading import Timer

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

if not getattr(sys, 'frozen', False):
    pastikan_library_lengkap()

from flask import Flask, request, jsonify, render_template, send_file
import pandas as pd
import numpy as np
from sklearn.manifold import MDS
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import pairwise_distances

# Setup Flask
if getattr(sys, 'frozen', False):
    # Untuk PyInstaller
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    template_folder = os.path.join(base_path, 'templates')
    app = Flask(__name__, template_folder=template_folder)
else:
    app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

# Fungsi Rotasi Procrustes
def rotate_and_scale(coords):
    # good = coords[0], bad = coords[-1]
    translated = coords - coords[-1]
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
        param_end_score_col_str = request.form.get('end_score_col', '').strip()
        param_start_row = int(request.form.get('start_row', 2))
        param_end_row = int(request.form.get('end_row', 18))
        mc_iter = int(request.form.get('mc_iterations', 50))

        start_text_col = param_start_text_col - 1
        start_score_col = param_start_score_col - 1
        start_row = param_start_row - 2
        end_row = param_end_row - 1 

        if start_row < 0: start_row = 0

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

        if param_end_score_col_str:
            end_score_col = min(int(param_end_score_col_str), len(df.columns))
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
            return jsonify({"status": "error", "error": "Data kosong atau tidak valid."})
        
        max_vals, min_vals = data_to_process.max(axis=0), data_to_process.min(axis=0)
        for col in data_to_process.columns:
            if max_vals[col] == min_vals[col]: max_vals[col] += 0.01

        data_with_anchors = pd.concat([
            pd.DataFrame([max_vals], columns=data_to_process.columns),
            data_to_process,
            pd.DataFrame([min_vals], columns=data_to_process.columns)
        ], ignore_index=True)
        
        scaler = MinMaxScaler()
        scaled_data = np.nan_to_num(scaler.fit_transform(data_with_anchors))
        
        dist_matrix = pairwise_distances(scaled_data, metric='euclidean')
        mds = MDS(n_components=2, dissimilarity='precomputed', random_state=42, n_init=20, max_iter=2000, eps=1e-7)
        raw_coords = mds.fit_transform(dist_matrix)
        
        # Stress-1
        fitted_dist = pairwise_distances(raw_coords, metric='euclidean')
        mask = np.triu(np.ones(dist_matrix.shape), k=1).astype(bool)
        d_ij, hat_d_ij = dist_matrix[mask], fitted_dist[mask]
        stress = round(float(np.sqrt(np.sum((hat_d_ij - d_ij)**2) / np.sum(d_ij**2))), 4)
        
        # RSQ
        rsq = round(float(np.corrcoef(d_ij, hat_d_ij)[0, 1]**2), 4)

        scaled_coords, rotated_coords = rotate_and_scale(raw_coords)
        
        labels_anchors = ["GOOD"] + labels + ["BAD"]
        rap_full_data = []
        for i in range(len(labels_anchors)):
            rap_full_data.append({
                "label": labels_anchors[i],
                "raw_x": round(float(raw_coords[i][0]), 4), "raw_y": round(float(raw_coords[i][1]), 4),
                "rot_x": round(float(rotated_coords[i][0]), 4), "rot_y": round(float(rotated_coords[i][1]), 4),
                "scl_x": round(float(scaled_coords[i][0]), 4), "scl_y": round(float(scaled_coords[i][1]), 4)
            })

        final_coords = [{"label": labels[i-1], "x": round(float(scaled_coords[i][0]), 3), "y": round(float(scaled_coords[i][1]), 3)} for i in range(1, len(scaled_coords) - 1)]
        distances = [{"titik1": labels[i-1], "titik2": labels[j-1], "jarak": round(float(dist_matrix[i][j]), 3)} for i in range(1, len(labels)+1) for j in range(i+1, len(labels)+1)]

        # Leverage
        leverage_results = []
        leverage_matrix_data = []
        leverage_scores_dict = {}
        base_scores = [pt['x'] for pt in final_coords]
        attrs = data_to_process.columns.tolist()

        for col_idx, attr in enumerate(attrs):
            attr_name = str(attr)
            temp_scaled = np.delete(scaled_data, col_idx, axis=1)
            temp_dist = pairwise_distances(temp_scaled, metric='euclidean')
            temp_scl, _ = rotate_and_scale(mds.fit_transform(temp_dist))
            scores_rem = [float(temp_scl[i][0]) for i in range(1, len(temp_scl) - 1)]
            leverage_scores_dict[attr_name] = scores_rem
            rms = np.sqrt(np.mean([(scores_rem[i] - base_scores[i])**2 for i in range(len(base_scores))]))
            leverage_results.append({"atribut": attr_name, "leverage": round(float(rms), 3)})
        
        for i, label in enumerate(labels):
            row = {"label": label}
            for attr in attrs: row[str(attr)] = round(leverage_scores_dict[str(attr)][i], 4)
            leverage_matrix_data.append(row)

        # Monte Carlo
        mc_results, mc_grouped, mc_matrix_excel = [], {l: {'x': [], 'y': []} for l in labels}, []
        for _ in range(mc_iter):
            noise = np.random.normal(0, 0.05, scaled_data.shape)
            mc_scl, _ = rotate_and_scale(mds.fit_transform(pairwise_distances(scaled_data + noise, metric='euclidean')))
            iter_row = {}
            for i in range(1, len(mc_scl)-1):
                lbl, x_val, y_val = labels[i-1], float(mc_scl[i][0]), float(mc_scl[i][1])
                mc_results.append({"label": lbl, "x": round(x_val, 3), "y": round(y_val, 3)})
                mc_grouped[lbl]['x'].append(x_val)
                mc_grouped[lbl]['y'].append(y_val)
                iter_row[lbl] = round(x_val, 4)
            mc_matrix_excel.append(iter_row)

        mc_summary, mc_distributions = [], {}
        for lbl in labels:
            x_arr, y_arr = mc_grouped[lbl]['x'], mc_grouped[lbl]['y']
            if not x_arr: continue
            mc_distributions[lbl] = [round(val, 2) for val in x_arr]
            med_x, med_y = np.median(x_arr), np.median(y_arr)
            mc_summary.append({
                "label": lbl, "med_x": round(med_x, 3), "med_y": round(med_y, 3),
                "x_minus_95": round(med_x - np.percentile(x_arr, 2.5), 3), "x_plus_95": round(np.percentile(x_arr, 97.5) - med_x, 3),
                "y_minus_95": round(med_y - np.percentile(y_arr, 2.5), 3), "y_plus_95": round(np.percentile(y_arr, 97.5) - med_y, 3),
                "x_minus_50": round(med_x - np.percentile(x_arr, 25), 3),  "x_plus_50": round(np.percentile(x_arr, 75) - med_x, 3),
                "y_minus_50": round(med_y - np.percentile(y_arr, 25), 3),  "y_plus_50": round(np.percentile(y_arr, 75) - med_y, 3)
            })

        return jsonify({
            "status": "success", "rap_analysis": final_coords, "rap_full_data": rap_full_data, "distances": distances,
            "leverage": sorted(leverage_results, key=lambda k: k['leverage'], reverse=True),
            "leverage_matrix": leverage_matrix_data, "monte_carlo": mc_results, "mc_matrix": mc_matrix_excel, 
            "mc_summary": mc_summary, "mc_distributions": mc_distributions, "stress": stress, "rsq": rsq
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"status": "error", "error": str(e)})

@app.route('/export_excel', methods=['POST'])
def export_excel():
    try:
        data = request.get_json(silent=True) or {}
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            # Sheet RapAnalysis
            pd.DataFrame(data.get('rap_full_data', [])).to_excel(writer, sheet_name='RapAnalysis', index=False)
            # Sheet Leverage
            pd.DataFrame(data.get('leverage_matrix', [])).to_excel(writer, sheet_name='Leverage', index=False)
            # Sheet MonteCarlo
            pd.DataFrame(data.get('mc_matrix', [])).to_excel(writer, sheet_name='MonteCarlo', index=False)
        output.seek(0)
        return send_file(output, as_attachment=True, download_name="Hasil_Rapfish.xlsx", mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    except Exception as e:
        traceback.print_exc()
        return f"Error: {str(e)}", 500

def open_browser():
    webbrowser.open_new("http://127.0.0.1:5000")

if __name__ == '__main__':
    try:
        if getattr(sys, 'frozen', False):
            Timer(1.5, open_browser).start()
        app.run(debug=False, port=5000)
    except Exception as e:
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk(); root.withdraw()
            messagebox.showerror("Error", str(e))
        except:
            print(f"Error: {e}")
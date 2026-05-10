import os
import sys
import subprocess
import webbrowser
import io
import traceback
from threading import Timer

# ==========================================
# 1. SISTEM AUTO-INSTALLER
# ==========================================
def pastikan_library_lengkap():
    """Memastikan semua library yang dibutuhkan terinstal."""
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

# Jalankan auto-installer jika tidak dalam mode EXE
if not getattr(sys, 'frozen', False):
    pastikan_library_lengkap()

# Import library utama setelah auto-installer
try:
    from flask import Flask, request, jsonify, render_template, send_file
    import pandas as pd
    import numpy as np
    from sklearn.manifold import MDS
    from sklearn.preprocessing import MinMaxScaler
    from sklearn.metrics import pairwise_distances
except ImportError as e:
    print(f"Kritis: Library gagal dimuat. {e}")
    sys.exit(1)

# ==========================================
# 2. KONFIGURASI FLASK
# ==========================================
if getattr(sys, 'frozen', False):
    # Penanganan folder template untuk PyInstaller
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    template_folder = os.path.join(base_path, 'templates')
    app = Flask(__name__, template_folder=template_folder)
else:
    app = Flask(__name__)

# ==========================================
# 3. FUNGSI UTILITAS STATISTIK
# ==========================================
def rotate_and_scale(coords):
    """
    Melakukan rotasi Procrustes agar titik 'BAD' berada di (0,0) 
    dan titik 'GOOD' berada di sumbu X positif (100,0).
    """
    # Titik GOOD di indeks 0, titik BAD di indeks terakhir
    good_pt = coords[0]
    bad_pt = coords[-1]
    
    # Translasi: Pindahkan BAD ke (0,0)
    translated = coords - bad_pt
    
    # Rotasi: Putar agar GOOD sejajar dengan sumbu X
    angle = np.arctan2(translated[0][1], translated[0][0])
    c, s = np.cos(-angle), np.sin(-angle)
    rot_matrix = np.array(((c, -s), (s, c)))
    rotated = translated.dot(rot_matrix.T)
    
    # Scaling: Paksa jarak GOOD-BAD menjadi 100 unit
    dist_gb = rotated[0, 0]
    scale_factor = 100.0 / dist_gb if dist_gb != 0 else 1.0
    scaled = rotated * scale_factor
    
    return scaled, rotated

# ==========================================
# 4. ROUTES APLIKASI
# ==========================================
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    """Endpoint utama untuk melakukan analisis MDS Rapfish."""
    if 'file' not in request.files:
        return jsonify({"status": "error", "error": "Tidak ada file yang diunggah"})
    
    file = request.files['file']
    filename = file.filename
    
    try:
        # Ambil parameter dari form
        start_text_col = int(request.form.get('start_text_col', 1)) - 1
        start_score_col = int(request.form.get('start_score_col', 3)) - 1
        end_score_col_str = request.form.get('end_score_col', '').strip()
        start_row = int(request.form.get('start_row', 2)) - 2
        end_row = int(request.form.get('end_row', 18)) - 1
        mc_iter = int(request.form.get('mc_iterations', 50))

        if start_row < 0: start_row = 0

        # Membaca Data
        if filename.endswith('.csv'):
            df_raw = pd.read_csv(file)
        elif filename.endswith(('.xls', '.xlsx')):
            engine_type = 'xlrd' if filename.endswith('.xls') else 'openpyxl'
            df_raw = pd.read_excel(file, engine=engine_type)
        else:
            return jsonify({"status": "error", "error": "Format file tidak didukung"})
        
        # Slicing Data
        actual_end_row = min(end_row, len(df_raw))
        df_sliced = df_raw.iloc[start_row:actual_end_row].copy()
        labels = df_sliced.iloc[:, start_text_col].astype(str).tolist()

        # Seleksi Kolom Skor
        if end_score_col_str:
            end_col = min(int(end_score_col_str), len(df_raw.columns))
            raw_scores = df_sliced.iloc[:, start_score_col:end_col].copy()
        else:
            raw_scores = df_sliced.iloc[:, start_score_col:].copy()
        
        # Konversi ke Numerik
        for col in raw_scores.columns:
            raw_scores[col] = pd.to_numeric(raw_scores[col].astype(str).str.replace(',', '.'), errors='coerce')
        
        data_clean = raw_scores.fillna(0.0).astype(float)
        # Hapus kolom yang isinya nol semua
        data_clean = data_clean.loc[:, (data_clean != 0).any(axis=0)]
        
        if data_clean.empty or len(data_clean) < 2:
            return jsonify({"status": "error", "error": "Data tidak mencukupi untuk analisis"})
        
        # Tambahkan Anchors (GOOD & BAD)
        max_vals = data_clean.max(axis=0)
        min_vals = data_clean.min(axis=0)
        # Hindari pembagian nol
        for col in data_clean.columns:
            if max_vals[col] == min_vals[col]: max_vals[col] += 0.01

        data_final = pd.concat([
            pd.DataFrame([max_vals], columns=data_clean.columns),
            data_clean,
            pd.DataFrame([min_vals], columns=data_clean.columns)
        ], ignore_index=True)
        
        # Normalisasi & MDS
        scaler = MinMaxScaler()
        scaled_data = np.nan_to_num(scaler.fit_transform(data_final))
        
        dist_matrix = pairwise_distances(scaled_data, metric='euclidean')
        mds_engine = MDS(n_components=2, dissimilarity='precomputed', random_state=42, n_init=20, max_iter=2000, eps=1e-7)
        raw_coords = mds_engine.fit_transform(dist_matrix)
        
        # Statistik: Stress & RSQ
        fitted_dist = pairwise_distances(raw_coords, metric='euclidean')
        triu_mask = np.triu(np.ones(dist_matrix.shape), k=1).astype(bool)
        d_orig, d_hat = dist_matrix[triu_mask], fitted_dist[triu_mask]
        
        stress_val = round(float(np.sqrt(np.sum((d_hat - d_orig)**2) / np.sum(d_orig**2))), 4)
        rsq_val = round(float(np.corrcoef(d_orig, d_hat)[0, 1]**2), 4)

        # Rotasi
        scl_coords, rot_coords = rotate_and_scale(raw_coords)
        
        # Siapkan Output MDS
        final_results = []
        for i in range(1, len(scl_coords) - 1):
            final_results.append({
                "label": labels[i-1],
                "x": round(float(scl_coords[i][0]), 3),
                "y": round(float(scl_coords[i][1]), 3)
            })

        # Leverage Analysis
        leverage_list = []
        lev_matrix = []
        lev_scores_temp = {}
        base_x = [pt['x'] for pt in final_results]
        attributes = data_clean.columns.tolist()

        for idx, attr in enumerate(attributes):
            attr_key = str(attr)
            temp_data = np.delete(scaled_data, idx, axis=1)
            temp_dist = pairwise_distances(temp_data, metric='euclidean')
            temp_scl, _ = rotate_and_scale(mds_engine.fit_transform(temp_dist))
            
            s_rem = [float(temp_scl[i][0]) for i in range(1, len(temp_scl) - 1)]
            lev_scores_temp[attr_key] = s_rem
            rms_err = np.sqrt(np.mean([(s_rem[j] - base_x[j])**2 for j in range(len(base_x))]))
            leverage_list.append({"atribut": attr_key, "leverage": round(float(rms_err), 3)})
        
        for i, label in enumerate(labels):
            row_data = {"label": label}
            for a in attributes: row_data[str(a)] = round(lev_scores_temp[str(a)][i], 4)
            lev_matrix.append(row_data)

        # Monte Carlo Simulation
        mc_results = []
        mc_group = {l: {'x': [], 'y': []} for l in labels}
        mc_matrix = []
        
        for _ in range(mc_iter):
            # Noise standar 0.05
            mc_noise = np.random.normal(0, 0.05, scaled_data.shape)
            mc_scl, _ = rotate_and_scale(mds_engine.fit_transform(pairwise_distances(scaled_data + mc_noise, metric='euclidean')))
            row_mc = {}
            for i in range(1, len(mc_scl)-1):
                lbl_mc = labels[i-1]
                x_mc, y_mc = float(mc_scl[i][0]), float(mc_scl[i][1])
                mc_results.append({"label": lbl_mc, "x": round(x_mc, 3), "y": round(y_mc, 3)})
                mc_group[lbl_mc]['x'].append(x_mc)
                mc_group[lbl_mc]['y'].append(y_mc)
                row_mc[lbl_mc] = round(x_mc, 4)
            mc_matrix.append(row_mc)

        # Ringkasan Monte Carlo
        mc_summary = []
        mc_dist_map = {}
        for lbl in labels:
            xs, ys = mc_group[lbl]['x'], mc_group[lbl]['y']
            if not xs: continue
            mc_dist_map[lbl] = [round(v, 2) for v in xs]
            mx, my = np.median(xs), np.median(ys)
            mc_summary.append({
                "label": lbl, "med_x": round(mx, 3), "med_y": round(my, 3),
                "x_minus_95": round(mx - np.percentile(xs, 2.5), 3), "x_plus_95": round(np.percentile(xs, 97.5) - mx, 3),
                "y_minus_95": round(my - np.percentile(ys, 2.5), 3), "y_plus_95": round(np.percentile(ys, 97.5) - my, 3),
                "x_minus_50": round(mx - np.percentile(xs, 25), 3),  "x_plus_50": round(np.percentile(xs, 75) - mx, 3),
                "y_minus_50": round(my - np.percentile(ys, 25), 3),  "y_plus_50": round(np.percentile(ys, 75) - my, 3)
            })

        return jsonify({
            "status": "success",
            "rap_analysis": final_results,
            "leverage": sorted(leverage_list, key=lambda k: k['leverage'], reverse=True),
            "leverage_matrix": lev_matrix,
            "monte_carlo": mc_results,
            "mc_matrix": mc_matrix, 
            "mc_summary": mc_summary,
            "mc_distributions": mc_dist_map,
            "stress": stress_val,
            "rsq": rsq_val
        })
        
    except Exception as err:
        traceback.print_exc()
        return jsonify({"status": "error", "error": str(err)})

@app.route('/export_excel', methods=['POST'])
def export_excel():
    """Mengekspor hasil analisis ke file Excel."""
    try:
        req_data = request.get_json(silent=True) or {}
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as excel_writer:
            # Export data MDS
            pd.DataFrame(req_data.get('rap_analysis', [])).to_excel(excel_writer, sheet_name='MDS_Results', index=False)
            # Export Leverage
            pd.DataFrame(req_data.get('leverage_matrix', [])).to_excel(excel_writer, sheet_name='Leverage', index=False)
            # Export Monte Carlo
            pd.DataFrame(req_data.get('mc_matrix', [])).to_excel(excel_writer, sheet_name='MonteCarlo', index=False)
        
        buffer.seek(0)
        return send_file(
            buffer, 
            as_attachment=True, 
            download_name="Rapfish_Output.xlsx", 
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except Exception as err:
        traceback.print_exc()
        return f"Export Error: {str(err)}", 500

# ==========================================
# 5. ENTRY POINT
# ==========================================
def auto_open_browser():
    """Fungsi pembantu untuk membuka browser otomatis."""
    webbrowser.open_new("http://127.0.0.1:5000")

if __name__ == '__main__':
    try:
        # Jalankan timer untuk membuka browser jika dalam mode standalone
        if getattr(sys, 'frozen', False):
            Timer(1.5, auto_open_browser).start()
        
        # Jalankan Flask Server
        app.run(debug=False, port=5000)
        
    except Exception as master_err:
        # Fallback Error Reporting (Gunakan Tkinter jika tersedia)
        try:
            import tkinter as tk
            from tkinter import messagebox
            gui_root = tk.Tk()
            gui_root.withdraw()
            messagebox.showerror("Rapfish Startup Failure", f"Fatal error:\n{master_err}")
        except ImportError:
            print(f"FATAL: {master_err}")
            with open("crash_log.txt", "w") as log_file:
                log_file.write(str(master_err))
                traceback.print_exc(file=log_file)
import os
import sys
import subprocess
import webbrowser
import io
import traceback
from threading import Timer

# ==========================================
# 1. PYINSTALLER RESOURCE PATH HELPER
# ==========================================
def resource_path(relative_path):
    """Mendapatkan path absolut ke resource, bekerja untuk dev dan PyInstaller."""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

# ==========================================
# 2. AUTO-INSTALLER & ENVIRONMENT SETUP
# ==========================================
# Mencegah error linter untuk variabel khusus PyInstaller
if not hasattr(sys, 'frozen'):
    sys.frozen = False

def ensure_dependencies():
    """Memastikan semua library terinstal sebelum aplikasi berjalan."""
    required_libs = {
        'flask': 'Flask',
        'pandas': 'pandas',
        'numpy': 'numpy',
        'sklearn': 'scikit-learn',
        'xlsxwriter': 'xlsxwriter',
        'openpyxl': 'openpyxl',
        'xlrd': 'xlrd'
    }
    for module_name, pip_name in required_libs.items():
        try:
            __import__(module_name)
        except ImportError:
            print(f"[*] Missing {pip_name}. Installing...")
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', pip_name])

# Jalankan pemeriksaan dependensi hanya saat dalam mode development
if not getattr(sys, 'frozen', False):
    ensure_dependencies()

# Import utama setelah dipastikan library ada
from flask import Flask, request, jsonify, render_template, send_file
import pandas as pd
import numpy as np
from sklearn.manifold import MDS
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import pairwise_distances

# ==========================================
# 3. APP INITIALIZATION WITH RESOURCE PATHS
# ==========================================
template_dir = resource_path('templates')
static_dir = resource_path('static')

app = Flask(__name__, 
            template_folder=template_dir,
            static_folder=static_dir)

# ==========================================
# 3. CORE LOGIC (MDS & PROCRUSTES)
# ==========================================
def rotate_and_scale(coords):
    """
    Menormalisasi koordinat MDS:
    1. BAD di (0,0)
    2. GOOD di (100,0)
    """
    # GOOD = idx 0, BAD = idx -1
    p_good, p_bad = coords[0], coords[-1]
    
    # Pindahkan BAD ke pusat (0,0)
    translated = coords - p_bad
    
    # Rotasi agar GOOD berada di sumbu X positif
    theta = -np.arctan2(translated[0][1], translated[0][0])
    cos, sin = np.cos(theta), np.sin(theta)
    rot_matrix = np.array([[cos, -sin], [sin, cos]])
    rotated = translated.dot(rot_matrix.T)
    
    # Scaling agar GOOD berada tepat di nilai 100
    dist = rotated[0, 0]
    scale = 100.0 / dist if dist != 0 else 1.0
    return (rotated * scale), rotated

# ==========================================
# 4. WEB ROUTES
# ==========================================
@app.route('/')
def index():
    return render_template('index.html')

def load_and_clean_data(f, s_row, e_row, s_col_txt, s_col_val, e_col_val):
    """Helper function to load and clean data from file."""
    # Load Data
    if f.filename.lower().endswith('.csv'):
        df = pd.read_csv(f)
    else:
        engine = 'xlrd' if f.filename.lower().endswith('.xls') else 'openpyxl'
        df = pd.read_excel(f, engine=engine)

    # Slicing & Cleaning
    df_sub = df.iloc[max(0, s_row):e_row].copy()
    labels = df_sub.iloc[:, s_col_txt].astype(str).tolist()
    
    if e_col_val:
        raw_vals = df_sub.iloc[:, s_col_val:int(e_col_val)].copy()
    else:
        raw_vals = df_sub.iloc[:, s_col_val:].copy()

    # Pastikan numerik
    for c in raw_vals.columns:
        raw_vals[c] = pd.to_numeric(raw_vals[c].astype(str).str.replace(',', '.'), errors='coerce')
    
    clean_data = raw_vals.fillna(0.0).astype(float)
    # Hapus kolom yang semuanya nol
    clean_data = clean_data.loc[:, (clean_data != 0).any(axis=0)]
    
    return labels, clean_data

@app.route('/preview', methods=['POST'])
def preview():
    try:
        f = request.files['file']
        s_row = int(request.form.get('start_row', 2)) - 2
        e_row = int(request.form.get('end_row', 18)) - 1
        s_col_txt = int(request.form.get('start_text_col', 1)) - 1
        s_col_val = int(request.form.get('start_score_col', 3)) - 1
        e_col_val = request.form.get('end_score_col', '').strip()

        labels, clean_data = load_and_clean_data(f, s_row, e_row, s_col_txt, s_col_val, e_col_val)
        
        # Combine labels and scores for preview
        preview_df = clean_data.copy()
        preview_df.insert(0, 'Fishery', labels)
        
        return jsonify({
            "status": "success",
            "columns": preview_df.columns.tolist(),
            "data": preview_df.head(10).values.tolist()
        })
    except Exception:
        return jsonify({"status": "error", "error": traceback.format_exc()})

@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        # 1. Parsing Parameter
        f = request.files['file']
        s_row = int(request.form.get('start_row', 2)) - 2
        e_row = int(request.form.get('end_row', 18)) - 1
        s_col_txt = int(request.form.get('start_text_col', 1)) - 1
        s_col_val = int(request.form.get('start_score_col', 3)) - 1
        e_col_val = request.form.get('end_score_col', '').strip()
        mc_iterations = int(request.form.get('mc_iterations', 50))

        # 2. Load Data using helper
        labels, clean_data = load_and_clean_data(f, s_row, e_row, s_col_txt, s_col_val, e_col_val)
        
        if len(clean_data) < 2:
            return jsonify({"status": "error", "error": "Data tidak cukup."})

        # 4. MDS Processing with Anchors
        mx_v, mn_v = clean_data.max(), clean_data.min()
        # Cegah pembagian nol pada scaling
        for col in clean_data.columns:
            if mx_v[col] == mn_v[col]: mx_v[col] += 0.01

        anchored = pd.concat([
            pd.DataFrame([mx_v], columns=clean_data.columns),
            clean_data,
            pd.DataFrame([mn_v], columns=clean_data.columns)
        ], ignore_index=True)

        scaler = MinMaxScaler()
        scaled_x = np.nan_to_num(scaler.fit_transform(anchored))
        
        d_mat = pairwise_distances(scaled_x, metric='euclidean')
        mds = MDS(n_components=2, dissimilarity='precomputed', random_state=42, n_init=10)
        coords_raw = mds.fit_transform(d_mat)
        
        # Rotasi Procrustes
        coords_scl, _ = rotate_and_scale(coords_raw)
        
        # 5. Result Extraction
        results = []
        for i in range(1, len(coords_scl)-1):
            results.append({"label": labels[i-1], "x": round(coords_scl[i,0], 3), "y": round(coords_scl[i,1], 3)})

        # RSQ & Stress
        d_fit = pairwise_distances(coords_raw, metric='euclidean')
        mask = np.triu(np.ones(d_mat.shape), k=1).astype(bool)
        s_val = round(float(np.sqrt(np.sum((d_fit[mask]-d_mat[mask])**2)/np.sum(d_mat[mask]**2))), 4)
        r_val = round(float(np.corrcoef(d_mat[mask], d_fit[mask])[0,1]**2), 4)

        # 6. Leverage
        lev_list, lev_matrix = [], []
        lev_scores = {}
        for i, col in enumerate(clean_data.columns):
            temp_x = np.delete(scaled_x, i, axis=1)
            temp_scl, _ = rotate_and_scale(mds.fit_transform(pairwise_distances(temp_x, metric='euclidean')))
            scores = [float(temp_scl[j, 0]) for j in range(1, len(temp_scl)-1)]
            lev_scores[str(col)] = scores
            rms = np.sqrt(np.mean([(scores[j] - results[j]['x'])**2 for j in range(len(scores))]))
            lev_list.append({"atribut": str(col), "leverage": round(float(rms), 3)})

        for i, lbl in enumerate(labels):
            row = {"label": lbl}
            for col in clean_data.columns: row[str(col)] = round(lev_scores[str(col)][i], 4)
            lev_matrix.append(row)

        # 7. Monte Carlo
        mc_raw, mc_matrix, mc_sum = [], [], []
        mc_groups = {l: {'x': [], 'y': []} for l in labels}
        
        for _ in range(mc_iterations):
            noise = np.random.normal(0, 0.05, scaled_x.shape)
            mc_scl, _ = rotate_and_scale(mds.fit_transform(pairwise_distances(scaled_x + noise, metric='euclidean')))
            row_iter = {}
            for i in range(1, len(mc_scl)-1):
                lbl = labels[i-1]
                x_v, y_v = float(mc_scl[i,0]), float(mc_scl[i,1])
                mc_raw.append({"label": lbl, "x": round(x_v, 3), "y": round(y_v, 3)})
                mc_groups[lbl]['x'].append(x_v)
                mc_groups[lbl]['y'].append(y_v)
                row_iter[lbl] = round(x_v, 4)
            mc_matrix.append(row_iter)

        mc_dist = {}
        for lbl in labels:
            xs, ys = mc_groups[lbl]['x'], mc_groups[lbl]['y']
            if not xs: continue
            mc_dist[lbl] = [round(v, 2) for v in xs]
            mx, my = np.median(xs), np.median(ys)
            p97_5, p2_5 = np.percentile(xs, 97.5), np.percentile(xs, 2.5)
            p75, p25 = np.percentile(xs, 75), np.percentile(xs, 25)
            py97_5, py2_5 = np.percentile(ys, 97.5), np.percentile(ys, 2.5)
            py75, py25 = np.percentile(ys, 75), np.percentile(ys, 25)
            
            mc_sum.append({
                "label": lbl, "med_x": round(mx, 3), "med_y": round(my, 3),
                "x2_5": round(p2_5, 3), "x97_5": round(p97_5, 3),
                "y2_5": round(py2_5, 3), "y97_5": round(py97_5, 3),
                "x25": round(p25, 3), "x75": round(p75, 3),
                "y25": round(py25, 3), "y75": round(py75, 3)
            })

        return jsonify({
            "status": "success", "rap_analysis": results, "stress": s_val, "rsq": r_val,
            "leverage": sorted(lev_list, key=lambda x: x['leverage'], reverse=True),
            "leverage_matrix": lev_matrix, "monte_carlo": mc_raw, "mc_matrix": mc_matrix,
            "mc_summary": mc_sum, "mc_distributions": mc_dist
        })

    except Exception:
        return jsonify({"status": "error", "error": traceback.format_exc()})

@app.route('/export_excel', methods=['POST'])
def export():
    try:
        data = request.get_json(silent=True) or {}
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine='xlsxwriter') as writer:
            pd.DataFrame(data.get('rap_analysis', [])).to_excel(writer, sheet_name='MDS', index=False)
            pd.DataFrame(data.get('leverage_matrix', [])).to_excel(writer, sheet_name='Leverage', index=False)
            pd.DataFrame(data.get('mc_matrix', [])).to_excel(writer, sheet_name='MonteCarlo', index=False)
        out.seek(0)
        return send_file(out, as_attachment=True, download_name="Rapfish_Result.xlsx")
    except Exception:
        return "Error", 500

# ==========================================
# 5. DESKTOP WINDOW LAUNCHER
# ==========================================
def open_browser(url):
    """Membuka browser setelah delay singkat."""
    try:
        webbrowser.open(url)
    except Exception as e:
        print(f"[!] Could not open browser automatically: {e}")
        print(f"[*] Please open your browser manually and go to: {url}")

def find_free_port(start_port=5000, max_attempts=10):
    """Mencari port yang tersedia jika port default sedang digunakan."""
    import socket
    for port in range(start_port, start_port + max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('127.0.0.1', port))
                return port
        except OSError:
            continue
    return None

def start_desktop_app():
    """Memulai aplikasi dalam mode desktop native menggunakan PyWebView."""
    port = find_free_port(5000, 10)
    if not port:
        port = 5000 # Fallback
    
    url = f"http://127.0.0.1:{port}"
    
    try:
        import webview
        from threading import Thread
        
        # Jalankan Flask Server di background thread
        server_thread = Thread(target=lambda: app.run(host='127.0.0.1', port=port, debug=False, use_reloader=False, threaded=True))
        server_thread.daemon = True
        server_thread.start()
        
        # Tunggu server inisialisasi sebentar
        import time
        time.sleep(1.5)
        
        # Buat Jendela Desktop Native
        webview.create_window(
            'Web-Rapfish Desktop Analysis',
            url,
            width=1280,
            height=850,
            resizable=True,
            background_color='#1a1a2e'
        )
        webview.start()
        
    except ImportError:
        # Fallback ke browser jika pywebview tidak ada
        print(f"[*] PyWebView tidak ditemukan. Membuka di browser: {url}")
        Timer(1.5, lambda: webbrowser.open(url)).start()
        app.run(host='127.0.0.1', port=port, debug=False, use_reloader=False)

# ==========================================
# 6. MAIN ENTRY POINT
# ==========================================
if __name__ == '__main__':
    start_desktop_app()
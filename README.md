# 🌊 Web-Rapfish - Modern MDS Analysis Tool

![Version](https://img.shields.io/badge/version-2.0-blue)
![Python](https://img.shields.io/badge/python-3.8+-green)
![License](https://img.shields.io/badge/license-MIT-orange)

**Web-Rapfish** adalah aplikasi web modern untuk analisis keberlanjutan perikanan menggunakan metode **Multi-Dimensional Scaling (MDS)** dengan simulasi **Monte Carlo**.

## ✨ Fitur Utama

### 🎨 Modern UI/UX
- **Glassmorphism Design** - Tampilan premium dengan efek kaca transparan
- **Dark Mode** - Mode gelap untuk kenyamanan mata
- **Responsive Layout** - Tampil sempurna di desktop, tablet, dan mobile
- **Smooth Animations** - Transisi halus dan micro-interactions

### 📊 Analisis Lengkap
- **MDS Ordination** - Visualisasi posisi keberlanjutan perikanan
- **Leverage Analysis** - Identifikasi atribut paling berpengaruh
- **Monte Carlo Simulation** - Analisis ketidakpastian dengan confidence intervals
- **Kite Diagram** - Visualisasi multi-dimensi keberlanjutan

### 🚀 Fitur Canggih
- **Data Preview** - Pratinjau data sebelum analisis
- **Chart Export** - Unduh semua grafik sebagai PNG
- **Excel Export** - Ekspor hasil lengkap ke Excel
- **Auto-Save Config** - Parameter tersimpan otomatis
- **Help Modal** - Tutorial interaktif dalam aplikasi

## 📦 Instalasi

### Metode 1: Jalankan dari Source Code

```bash
# Clone repository
git clone https://github.com/pieterlase06-arch/Web-Rapfish.git
cd Web-Rapfish

# Install dependencies
pip install -r requirements.txt

# Jalankan aplikasi
python app.py
```

Aplikasi akan otomatis membuka di browser: `http://127.0.0.1:5000`

### Metode 2: Build Windows Executable (.exe)

```bash
# Jalankan build script
build_exe.bat
```

File executable akan tersedia di: `dist\Rapfish_MDS_Analysis.exe`

**Keuntungan .exe:**
- ✅ Tidak perlu install Python
- ✅ Portable - bisa dijalankan di komputer mana saja
- ✅ Double-click langsung jalan
- ✅ Cocok untuk distribusi ke pengguna non-teknis

## 🎯 Cara Penggunaan

1. **Upload File** - Pilih file Excel (.xlsx/.xls) atau CSV
2. **Konfigurasi Parameter** - Tentukan rentang baris dan kolom data
3. **Preview Data** - Verifikasi data sudah benar
4. **Run Analysis** - Klik tombol "Run Rapfish Analysis"
5. **Lihat Hasil** - Navigasi antar tab untuk melihat berbagai visualisasi
6. **Export** - Unduh grafik (PNG) atau laporan lengkap (Excel)

## 📋 Format Data Input

File Excel/CSV harus memiliki struktur:

| Fishery Name | Attribute 1 | Attribute 2 | ... | Attribute N |
|--------------|-------------|-------------|-----|-------------|
| Fishery A    | 2           | 3           | ... | 1           |
| Fishery B    | 1           | 2           | ... | 3           |

**Catatan:** Skor atribut biasanya dalam skala 0-3 atau 1-5.

## 🛠️ Teknologi

- **Backend:** Flask (Python)
- **Frontend:** HTML5, CSS3, Vanilla JavaScript
- **Visualisasi:** Chart.js
- **Analisis:** NumPy, Pandas, Scikit-learn
- **Build Tool:** PyInstaller

## 📊 Output Analisis

### 1. MDS Ordination
- Scatter plot posisi keberlanjutan (0-100)
- Tabel skor per perikanan

### 2. Leverage Analysis
- Bar chart RMS change per atribut
- Identifikasi atribut sensitif

### 3. Monte Carlo Simulation
- Raw scatter plot (semua iterasi)
- 95% dan 50% confidence intervals
- Histogram distribusi per perikanan

### 4. Kite Diagram
- Radar chart 5 dimensi keberlanjutan
- Input manual atau auto-import dari hasil

## 🔧 Build Configuration

File `build_windows.spec` sudah dikonfigurasi untuk:
- Include semua templates dan static files
- Bundle semua dependencies Python
- Optimize dengan UPX compression
- Single-file executable

## 📝 Lisensi

MIT License - Bebas digunakan untuk keperluan akademis dan komersial.

## 👨‍💻 Pengembang

Dikembangkan dengan ❤️ untuk komunitas riset perikanan Indonesia.

**Repository:** https://github.com/pieterlase06-arch/Web-Rapfish

---

### 🆘 Troubleshooting

**Q: Aplikasi tidak bisa membuka browser otomatis?**  
A: Buka manual di `http://127.0.0.1:5000`

**Q: Error saat build .exe?**  
A: Pastikan semua dependencies terinstall: `pip install -r requirements.txt`

**Q: File Excel tidak terbaca?**  
A: Pastikan format sesuai dan tidak ada merged cells di area data

**Q: Hasil MDS tidak stabil?**  
A: Tingkatkan jumlah iterasi Monte Carlo (default: 50, recommended: 100-200)

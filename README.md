# NP Energy Intelligence - Data Warehouse Transisi Energi (UAS BI MTI)

Status: Fase 1 (preprocessing). Bagian lain (staging, DWH, ETL, dashboard) belum dibuat.

## Menjalankan preprocessing (Windows)
    python -m venv .venv
    .venv\Scripts\activate
    pip install -r requirements.txt
    python src/preprocess.py

Hasil: `data/processed/*.csv` dan `logs/preprocess.log`.
Hasil yang diharapkan: ember 11.206 baris, renewable 1.100 baris.

## Sumber data
- Ember, Yearly Electricity Data (`data/raw/release_generation_yearly_global.csv`)
- Renewable Energy Share by Country 2000-2025, Kaggle (`data/raw/renewable_energy_share_2000_2025.csv`). Pemilik dan lisensi: DIISI SETELAH DIVERIFIKASI.

## Fase 2: membuat database (PostgreSQL 15 atau lebih baru)
Jalankan berurutan (psql, atau buka tiap file di pgAdmin Query Tool):

    psql -U postgres -f sql/00_create_database.sql
    psql -U postgres -d np_energy_dw -f sql/01_schemas.sql
    psql -U postgres -d np_energy_dw -f sql/02_staging_tables.sql
    psql -U postgres -d np_energy_dw -f sql/03_dw_dimensions.sql
    psql -U postgres -d np_energy_dw -f sql/04_dw_facts.sql
    psql -U postgres -d np_energy_dw -f sql/05_seed_reference_data.sql
    psql -U postgres -d np_energy_dw -f sql/90_verify_structure.sql
    psql -U postgres -d np_energy_dw -f sql/91_constraint_tests.sql

## Fase 3A: ETL ke staging
Persiapan sekali saja:
1. Jalankan `sql/06_etl_log.sql` di pgAdmin (database `np_energy_dw`).
2. Salin `.env.example` menjadi `.env`, isi `DB_PASSWORD`. File `.env` ada di `.gitignore` dan tidak boleh diunggah.
3. `pip install -r requirements.txt` (di dalam virtual environment).

Menjalankan: `python src/run_etl.py`
Log: `logs/etl.log` (file) dan tabel `ops.etl_run`, `ops.etl_step` (database).
Validasi: `sql/92_validate_etl.sql`.
Kode keluar: 0 = sukses, 1 = ETL gagal, 2 = konfigurasi/koneksi bermasalah.

## Fase 3B-1: dimensi Data Warehouse
Menjalankan: `python src/run_etl.py` (staging lalu dimensi). Hanya staging: `python src/run_etl.py --staging-only`.

Alur `load_dw` (satu transaksi; gagal = ROLLBACK, log kegagalan tetap tersimpan):
1. Gerbang awal: staging berasal dari run ini, tidak kosong, kode ISO3 berformat 3 huruf kapital.
2. `dim_country` (MERGE): nama dan atribut wilayah dari Ember; negara yang hanya ada di Renewable memakai nama Renewable, tanpa atribut wilayah.
3. `dim_country_group` (MERGE): satu baris per kombinasi flag keanggotaan; label dibentuk dari flag.
4. Peta negara -> kelompok (tabel sementara). Negara yang tidak ada di Ember mendapat kelompok "Tidak diketahui".
5. Gerbang validasi dimensi, lalu COMMIT.

Idempotensi: MERGE hanya meng-INSERT baris baru dan meng-UPDATE baris yang nilainya berubah; run ulang tanpa perubahan data melaporkan insert=0 dan update=0, dan surrogate key tidak berubah.

Catatan kualitas data: status kualitas pada tabel fakta (Fase 3B-2) hanya menandai ada atau tidaknya NILAI KOSONG pada kolom indikator yang ditetapkan, bukan menilai bahwa seluruh baris lengkap atau tidak lengkap. Nilai kosong tidak diimputasi.

Validasi: `sql/93_validate_dw.sql` (bagian B).

## Fase 3B-2: tabel fakta Data Warehouse
Menjalankan: `python src/run_etl.py` (staging, dimensi, lalu tiga tabel fakta dalam satu transaksi).
Hanya staging: `python src/run_etl.py --staging-only`.

Urutan di dalam `load_dw` (satu transaksi; gagal = ROLLBACK seluruh DW, log kegagalan tetap tersimpan):
1. Gerbang awal dan dimensi (3B-1), peta negara -> kelompok.
2. Gerbang awal fakta: semua tahun dan sumber listrik di staging dikenal oleh dimensi.
3. `fact_energy_country_year` (1.100 baris), `fact_emissions_country_year` (1.044), `fact_generation_source` (9.118),
   masing-masing dengan MERGE lalu gerbang: jumlah baris, grain unik, foreign key tanpa yatim, data_source_key
   sesuai seed, SUM dan jumlah non-NULL sama dengan staging, status kualitas sesuai aturan.
4. Rekonsiliasi lintas fakta (peringatan): total pembangkitan vs jumlah sumber murni.
5. COMMIT.

Status kualitas: "Valid dengan indikator kosong" hanya berarti ada nilai kosong (NULL) pada kolom indikator yang
ditetapkan: fact_energy = renewables_share_energy atau renewables_share_elec; fact_emissions =
emissions_intensity_gco2e_kwh atau renewables_share_pct; fact_generation_source = generation_twh atau
share_of_generation_pct (capacity_gw tidak dihitung karena kosong secara struktural di sumber). Status ini
bukan penilaian bahwa seluruh baris tidak punya data. Nilai kosong tidak pernah diimputasi.

ETL hanya menambah dan memperbarui baris; tidak menghapus baris DW yang tidak ada lagi di staging.

Validasi: `sql/93_validate_dw.sql` bagian C.

## Tahap 4-1: data mart dan akses dashboard
Urutan menjalankan di pgAdmin (database np_energy_dw, sebagai user postgres):
1. `sql/07_mart_views.sql`  : schema `mart` dan 4 view (aman dijalankan berulang)
2. `sql/08_dashboard_role.sql` : role kelompok `np_dashboard_reader` (hak baca-saja pada schema mart)
3. Buat role login `np_dashboard` dengan password Anda sendiri, mengikuti `sql/08b_dashboard_login_template.sql`
   (password tidak boleh disimpan di file atau GitHub).
4. `sql/94_validate_dashboard.sql` : validasi view dan hak akses

View mart: `v_country_year` (negara x tahun), `v_generation_mix` (negara x tahun x sumber),
`v_source_comparison` (Ember vs Renewable), `v_etl_status` (run ETL terakhir yang memuat DW).
Dashboard hanya membaca schema mart lewat role `np_dashboard`; tidak ada akses ke schema dw, stg, dan ops.

## Tahap 4-2: kerangka dashboard dan halaman Ringkasan
Persiapan (sekali): isi `DASHBOARD_DB_USER=np_dashboard` dan `DASHBOARD_DB_PASSWORD=...` di file `.env`
(lihat `.env.example`), lalu `pip install -r requirements.txt` di dalam virtual environment.

Menjalankan (dari folder utama proyek):  `streamlit run dashboard/app.py`  ->  http://localhost:8501
Uji otomatis (tanpa browser):  `python dashboard/tests/smoke_test.py`
Validasi angka Ringkasan (sebagai user postgres di pgAdmin):  `sql/95_validate_ringkasan.sql`

Struktur: `dashboard/app.py` (navigasi dan filter), `settings.py` (membaca .env), `db.py` (koneksi dan cache),
`queries.py` (seluruh SQL dan definisi KPI), `theme.py` (warna dan format angka), `charts.py` (grafik Plotly),
`halaman/` (enam halaman; Ringkasan lengkap, lima lainnya placeholder sampai Tahap 4-3).

Dashboard hanya membaca schema mart lewat akun baca-saja np_dashboard dan hanya mendengarkan di localhost.
Selisih pada kartu KPI dan peringkat dihitung dari angka yang ditampilkan (dibulatkan).

## Tahap 4-3a: Halaman A, Perkembangan Terbarukan
Isi halaman: empat kartu KPI (pangsa tertimbang, median antarnegara, negara berpangsa >= 50%, cakupan), tren dengan
pilihan tingkat Dunia / Benua / Negara, peringkat tertinggi dan terendah dengan ambang pembangkitan, dan tabel detail
negara yang dapat diunduh (CSV). Seluruh data dari view mart.v_country_year.

Uji otomatis:  `python dashboard/tests/test_halaman_a.py`  dan  `python dashboard/tests/smoke_test.py`
Validasi SQL (user postgres):  `sql/96_validate_halaman_a.sql`

Aturan pembulatan dashboard: nilai dibulatkan 1 desimal dengan aturan setengah ke atas (di SQL) dan selisih dihitung
dari angka yang dibulatkan. Nilai kosong tidak diisi perkiraan.

## Tahap 4-3b: Halaman B, Ketergantungan pada Fosil

**Tujuan.** Menunjukkan seberapa besar pembangkitan listrik bergantung pada sumber fosil, bagaimana perubahannya,
bagaimana negara dengan pembangkitan terbesar berada, dan bagaimana pangsa terbarukan pada listrik berbeda dari
pangsa terbarukan pada energi primer.

**Sumber data.** Hanya `mart.v_country_year` (kolom pangsa dan pembangkitan listrik dari Renewable Energy Share).
`mart.v_source_comparison` tidak dipakai karena tidak ada indikator B yang dibandingkan antar-sumber.
GDP dan populasi tidak dipakai.

**KPI** (tahun terpilih; selisih terhadap 2019; tahun pembanding tetap, sama dengan halaman lain):
pangsa listrik fosil, pangsa listrik terbarukan, Nuklir dan lainnya (sisa), dan jumlah negara dalam perhitungan.

**Logika agregasi.** Fosil dan terbarukan dihitung tertimbang pembangkitan listrik pada SATU himpunan negara: pangsa
fosil dan terbarukan terisi dan pembangkitan > 0. Himpunan ini identik dengan KPI Ringkasan, sehingga angka fosil dan
terbarukan sama dengan Ringkasan. Pembulatan 1 desimal (setengah ke atas, di SQL); selisih dihitung dari angka yang tampil.

**Definisi sisa.** Nuklir dan lainnya (sisa) = 100 - fosil - terbarukan, dihitung dari angka yang tampil sehingga tiga
kartu berjumlah tepat 100,0%. Bukan pangsa nuklir saja: sisa mencakup sumber lain di luar dua kategori utama. Nilai
tertimbang tanpa pembulatan dapat berbeda sampai 0,1 poin dari angka yang tampil (mis. 8,95 tampil 8,9). Dasar: pada
setiap negara-tahun pangsa fosil + low-carbon = 100 (selisih maksimum 0,001 poin, presisi sumber 3 desimal) dan
low-carbon tidak pernah lebih kecil dari terbarukan.

**Visualisasi.** (1) Garis fosil dan terbarukan 2019-2023 (dua garis terpisah, tidak ditumpuk). (2) Dumbbell pangsa fosil
2019 ke tahun terpilih untuk 5/10/15 negara dengan pembangkitan listrik terbesar (urutan menurut pembangkitan, bukan
pangsa fosil). (3) Dumbbell dan tabel pangsa terbarukan listrik vs energi primer.

**Energi primer.** Tersedia untuk sebagian negara dan tidak diagregasi. Cakupan ditampilkan dinamis (jumlah negara,
pasangan valid, sebaran per benua tanpa dipengaruhi filter). Bobot energi primer tidak dicampur dengan bobot listrik.
Hitungan lebih rendah / sama / lebih tinggi memakai pangsa yang dibulatkan 1 desimal.

**Nilai kosong.** NULL tetap NULL: tidak diubah menjadi 0 dan tidak diimputasi. Negara tanpa nilai tidak ikut KPI dan
ditulis apa adanya pada tabel (mis. Ukraine 2023: pangsa listrik kosong).

**Menjalankan uji.**
    python dashboard/tests/test_halaman_b.py
    python dashboard/tests/smoke_test.py
    (SQL, sebagai user postgres: sql/97_validate_halaman_b.sql)
Hasil di lingkungan pengembangan: test_halaman_b 47 dari 47; test_halaman_a 39 dari 39; smoke_test 28 dari 28.

## Tahap 4-3c: Halaman C, Bauran Pembangkitan

**Tujuan.** Menunjukkan bagaimana total pembangkitan listrik tersusun menurut kategori dan sumber, dan bagaimana
perubahannya 2019 ke tahun terpilih.

**Sumber data.** Hanya `mart.v_generation_mix` (Ember). Kolom yang dipakai bernama `source_category` dan `source_name`.
Daftar kategori dan sumber diambil dari data: 3 kategori (Fossil, Nuklir, Renewable) dan 9 sumber (Coal, Gas, Other fossil,
Nuclear, Bioenergy, Hydro, Solar, Wind, Other renewables). Kamus di `charts.py` hanya untuk label Indonesia, warna, dan
urutan tampilan; nama yang tidak ada di kamus dipakai apa adanya.

**KPI.** Total pembangkitan (TWh) dan pangsa tiap kategori pada tahun terpilih, dengan selisih terhadap 2019 (TWh untuk total,
poin untuk pangsa; dihitung dari angka yang tampil). Pangsa = TWh kategori / TWh total x 100, dari jumlah pembangkitan, bukan
rata-rata antarnegara. Pembulatan 1 desimal (setengah ke atas, di SQL), sehingga jumlah tiga pangsa yang tampil bisa 99,9 sampai 100,1.

**Visualisasi.** (1) Batang 100% bertumpuk per tahun dengan drill-down Kategori, Sumber rinci, dan satu kategori (komposisi di
dalam kategori itu). (2) Perbandingan filter vs negara sorotan pada tahun terpilih (negara sorotan tidak dipengaruhi filter benua
dan kelompok). (3) Treemap kategori ke sumber, hanya TWh lebih dari 0. (4) Tabel ringkasan per sumber. (5) Tabel detail negara x
sumber (baris maksimum 50 sampai 500, baris 0 TWh dapat ditampilkan, dapat diunduh CSV).

**Nilai 0 dan kosong.** 4.085 dari 9.118 baris bernilai 0 TWh (809 dari 1.816 pada 2023); tidak ada NULL dan tidak ada nilai negatif.
Baris 0 TWh tidak dihapus dari database; hanya tidak digambar pada treemap dan disembunyikan secara bawaan pada tabel detail.
Sumber yang tidak punya baris pada suatu negara tidak dianggap 0 secara eksplisit; jumlah semua sumber yang ada sama dengan
total pembangkitan Ember (selisih maksimum 0,002 TWh), sehingga tidak ada pembangkitan yang hilang. Negara tanpa data Ember
tidak ikut dihitung. Kategori bertotal 0 TWh pada suatu filter (mis. nuklir di Oceania) memiliki pangsa dalam kategori NULL.

**Perbedaan sumber.** Pangsa terbarukan Ember (30,1% pada 2023) berbeda dari Renewable Energy Share (30,4%) yang dipakai
Ringkasan, A, dan B. Halaman C menampilkan angka pembandingnya sebagai catatan sumber; angka itu tidak dipakai menghitung bauran.

**Menjalankan uji.**
    python dashboard/tests/test_halaman_c.py
    python dashboard/tests/test_halaman_a.py
    python dashboard/tests/test_halaman_b.py
    python dashboard/tests/smoke_test.py
    (SQL, sebagai user postgres: sql/98_validate_halaman_c.sql)
Hasil di lingkungan pengembangan: test_halaman_c 56 dari 56; test_halaman_a 39 dari 39; test_halaman_b 47 dari 47;
smoke_test 27 dari 27 (turun dari 28 karena pemeriksaan placeholder halaman C tidak berlaku lagi).

# Fase 4-3d: Halaman D (Pangsa Terbarukan vs Intensitas Emisi)

Basis: kode setelah Fase 4-3c (A, B, C, Ringkasan, database, DW, ETL, koneksi TIDAK diubah).

## File di ZIP ini
| File | Status | Isi |
|---|---|---|
| `dashboard/halaman/d_pangsa_intensitas.py` | menggantikan placeholder | Halaman D lengkap |
| `dashboard/queries.py` | berubah | hanya DITAMBAH di bawah (baris lama utuh): query D (`D_*`, `d_*`) |
| `dashboard/charts.py` | berubah | hanya DITAMBAH di bawah: `scatter_regression`, `corr_bar`, `change_scatter`, `residual_bar` |
| `dashboard/tests/test_halaman_d.py` | baru | 77 pemeriksaan |
| `dashboard/tests/smoke_test.py` | berubah | satu baris: daftar placeholder kini hanya `["kualitas"]` (smoke 27 menjadi 26) |
| `sql/99_validate_halaman_d.sql` | baru | validasi D1-D5 dari tabel fakta `dw` |

## SEBELUM menimpa: cadangkan dan cek MD5 (PowerShell: `Get-FileHash <file> -Algorithm MD5`)
Versi 4-3c yang harus kamu punya sekarang:
- `dashboard\queries.py` a36cbafc4aa59e5f5ac730304a768c5d
- `dashboard\charts.py` 00e00d447936ccf343b841532f53905a
- `dashboard\tests\smoke_test.py` c3eb49e4bf0077a1e2174bbcac380de6
- `dashboard\halaman\d_pangsa_intensitas.py` 322ae9944ce1c2b7e60cc20940369c11 (placeholder)

Kalau ada yang beda, JANGAN menimpa; kabari dulu (berarti ada perubahan lokal).

## Pengujian lokal (venv aktif, dari folder proyek)
```
python dashboard/tests/test_halaman_d.py   # target 77/77
python dashboard/tests/test_halaman_a.py   # 39/39
python dashboard/tests/test_halaman_b.py   # 47/47
python dashboard/tests/test_halaman_c.py   # 56/56
python dashboard/tests/smoke_test.py       # 26/26
```
Lalu `sql/99_validate_halaman_d.sql` di pgAdmin sebagai `postgres`: harapannya 23 baris OK, 0 BEDA.

## Uji manual di browser (`streamlit run dashboard/app.py`, buka "D. Pangsa vs Intensitas", tahun 2023, semua filter)
- Kartu: Pearson -0,88 (-0,01), Spearman -0,90 (-0,02), lereng -6,6, negara 207 dari 208.
- Tab Sebaran: 207 titik, 6 warna benua, garis putus-putus, lingkaran biru Indonesia (pangsa 15,1%, intensitas 710,5).
- Tab Per benua: Africa 54 -0,97 | Asia 49 -0,82 | Europe 41 -0,67 | North America 33 -0,98 | Oceania 15 -0,97 | South America 15 -0,99.
- Tab Perubahan 2019 ke 2023: lengkap 207 dari 209, median +1,9 poin / -13,2 gCO2e/kWh, korelasi antar-perubahan -0,84; Ukraine dan Lesotho kosong.
- Tab Pencilan: 10 teratas Turkmenistan, Uzbekistan, France, Slovakia, Belgium, Hungary, Belarus, Finland, Kazakhstan, Switzerland (dari 108 negara >= 10 TWh).
- Coba filter G7 saja (peringatan n kecil, korelasi per benua kosong) dan filter benua kosong (pesan, bukan error).

## Keputusan desain (sebutkan ke dosen, bukan standar ilmiah)
- Satuan analisis = negara per tahun, tidak tertimbang pembangkitan (kartu KPI lain tertimbang; ini berbeda dan diberi label).
- Pangsa terbarukan di D = Ember (satu sumber dengan intensitas), jadi dapat berbeda dari halaman A/B/Ringkasan (Renewable).
- Korelasi per benua hanya jika n >= 10; pencilan dan korelasi antar-perubahan hanya negara >= 10 TWh.
- Garis regresi (dan dasar pencilan) dihitung dari SEMUA negara valid pada filter; daftar pencilan dibatasi >= 10 TWh.
- Selisih/perubahan dihitung dari angka yang tampil (dibulatkan di SQL, setengah ke atas). NULL tetap NULL.
- Banner "observasional, bukan bukti sebab-akibat" selalu tampil; tidak ada interpretasi penyebab di dashboard.

# Fase 4-3e: Kualitas Data dan Metodologi

Basis: kode setelah Fase 4-3d. Halaman Ringkasan, A, B, C, D, DWH, ETL, koneksi, dan role `np_dashboard` TIDAK diubah.

## Tujuan
Menambah lapisan transparansi kualitas data: seberapa lengkap data, di mana nilainya kosong dan mengapa (sebatas yang
dapat dibuktikan), apakah Ember dan Renewable berbeda, apakah rata-rata sederhana dan tertimbang berbeda, apakah antar-view
mart konsisten, dan kapan ETL terakhir. Tidak ada imputasi, tidak ada data sintetis, tidak ada angka manual.

## File di ZIP
| File | Status |
|---|---|
| `dashboard/halaman/kualitas.py` | menggantikan placeholder |
| `dashboard/queries.py` | hanya DITAMBAH di bawah: query `K_*` dan fungsi `k_*` (baris lama utuh) |
| `dashboard/charts.py` | hanya DITAMBAH di bawah: `coverage_bar`, `source_scatter` (baris lama utuh) |
| `dashboard/tests/test_halaman_kualitas.py` | baru, 78 pemeriksaan |
| `dashboard/tests/smoke_test.py` | berubah: bagian 4 (loop placeholder terakhir) diganti satu pemeriksaan "semua 6 halaman tampil tanpa error dan tanpa tanda 'dalam pengembangan'"; jumlah smoke tetap 26 |
| `sql/100_validate_quality.sql` | baru, blok Q1-Q9 (82 baris status) |

## Komponen halaman (5 tab + 2 penjelasan)
1. **Cakupan**: coverage per tahun dan indikator (listrik Renewable, pembangkitan, energi primer, Ember, intensitas, bauran) dengan
   negara master, punya baris, dan nilai tersedia dipisahkan; energi primer per benua (tanpa agregat global); sebaran status kelengkapan.
2. **Nilai kosong**: daftar negara-tahun kosong beserta alasan yang dapat dibuktikan; negara tanpa benua.
3. **Ember vs Renewable**: cakupan menurut sumber, jumlah negara berselisih besar per tahun, tabel selisih terbesar, sebaran Ember vs Renewable.
4. **Rata-rata sederhana vs tertimbang**: pangsa dan intensitas per tahun, dampak pilihan bobot.
5. **Konsistensi dan ETL**: 5 pemeriksaan antar-view mart (OK/BEDA), run ETL terakhir dari `mart.v_etl_status`.
Expander: definisi KPI dan alasan pembobotan; sumber data dan query.

## Sumber data
Hanya view mart (`v_country_year`, `v_generation_mix`, `v_source_comparison`, `v_etl_status`) lewat akun baca-saja. Halaman tidak dipengaruhi
filter benua/kelompok (hanya tahun). Rekonsiliasi DW -> Mart butuh akses schema `dw`, jadi dijalankan di `sql/100` (bukan view baru; tidak ada `v_control_totals`).

## Keputusan desain (bukan standar ilmiah)
Ambang selisih Ember vs Renewable (pembangkitan > 5%, pangsa > 2 poin), toleransi penjumlahan bauran 0,05 TWh, 15 baris tabel selisih terbesar.

## SEBELUM menimpa: cadangkan dan cek MD5 (PowerShell: `Get-FileHash <file> -Algorithm MD5`)
Versi 4-3d yang harus kamu punya sekarang:
- `dashboard\queries.py` b7a0ef0bc5079f5d20cbaf9fa445af52
- `dashboard\charts.py` 877e30a481859d48833b07a555285ee9
- `dashboard\tests\smoke_test.py` a2982ec7daa8b9e02d6e6b47a0f12a6c
- `dashboard\halaman\kualitas.py` 319b9fca787de1af11a1e991332e5128 (placeholder)

Kalau ada yang beda, JANGAN menimpa; kabari dulu.

## Menjalankan test (venv aktif, dari folder proyek)
```
python dashboard/tests/test_halaman_kualitas.py   # target 78/78
python dashboard/tests/test_halaman_a.py          # 39/39
python dashboard/tests/test_halaman_b.py          # 47/47
python dashboard/tests/test_halaman_c.py          # 56/56
python dashboard/tests/test_halaman_d.py          # 77/77
python dashboard/tests/smoke_test.py              # 26/26
```
`test_halaman_kualitas.py` juga menelusuri asal nilai kosong ke `data/raw` bila berkas itu ada di folder proyekmu (kalau tidak ada, bagian itu ditandai [SKIP], bukan lulus).

## Menjalankan SQL validation
Buka `sql/100_validate_quality.sql` di pgAdmin sebagai `postgres` dan jalankan. Harapan: semua baris status OK (82 baris), 0 BEDA.
BEDA belum tentu error; periksa penyebabnya dulu (mis. dataset diperbarui atau ETL belum dijalankan ulang).
Q9 membandingkan v_etl_status dengan log ops; angkanya dari run ETL-mu sendiri.

## Hasil validasi (SANDBOX: PostgreSQL 16, Python 3.12; BUKAN lokal PostgreSQL 18)
Kualitas 78/78, A 39/39, B 47/47, C 56/56, D 77/77, smoke 26/26, sql/100 82 OK 0 BEDA (uji negatif dengan data diubah di transaksi lalu rollback: BEDA terdeteksi).
Validasi di PostgreSQL 18 lokal: belum dilakukan; jalankan langkah di atas dan laporkan hasilnya.

# Fase 4-4: Peninjauan desain dashboard berbasis literatur (Design Rationale)

Basis: kode setelah Fase 4-3e. Data, query, DW, Mart, ETL, role `np_dashboard`, dan logika Halaman A/B/C/D/Ringkasan/Kualitas TIDAK diubah.
Perubahan hanya pada tampilan (warna, tema, satu kalimat), ditambah satu test desain.

> **Status validasi.** Semua hasil di bawah berasal dari **sandbox** (PostgreSQL 16, Python 3.12), BUKAN PostgreSQL 18 lokalmu, dan
> **tidak ada pemeriksaan visual di browser** (saya tidak punya browser). Tangkapan layar dan uji manual tetap harus kamu lakukan.

## 1. Cara kerja dan prinsip
Urutan prioritas: kebenaran data > kegunaan analitis > keterbacaan > aksesibilitas > konsistensi visual > estetika.
Setiap perubahan harus punya dasar yang dapat dibuktikan; yang tidak punya bukti kuat sengaja TIDAK diubah (bagian 7).
Dua jenis klaim dibedakan secara eksplisit di seluruh dokumen:
- **[SUMBER]** = didukung sumber yang saya verifikasi (rincian dan batasannya di bagian 2).
- **[KEPUTUSAN PROYEK]** = keputusan desain kita berdasarkan prinsip umum; BUKAN hasil penelitian. Contoh: "warna teal/hijau-kebiruan = terbarukan" adalah
  pemetaan makna khusus proyek ini. Kalimat yang aman untuk presentasi: *"Berdasarkan prinsip penggunaan warna sebagai categorical encoding
  dan konsistensi visual (Graze & Schwabish, 2024), warna #009E73 ditetapkan secara konsisten untuk kategori terbarukan pada seluruh halaman."*
  JANGAN mengatakan "penelitian membuktikan terbarukan harus berwarna hijau/teal".

## 2. Temuan literatur dan status verifikasi
Verifikasi dilakukan lewat pencarian web pada sesi ini (judul, penulis, tahun, jurnal, DOI/URL dicocokkan antar-halaman). Tidak ada DOI, judul, atau hasil yang dikarang.
"Terverifikasi penuh" = saya membaca isi artikel; "abstrak" = hanya abstrak/halaman penerbit; "sekunder" = hanya lewat kutipan di sumber lain.

| ID | Sumber | Verifikasi | Mendukung | Batasan |
|---|---|---|---|---|
| R1 | Graze, M., & Schwabish, J. (2024). Building color palettes in your data visualization style guides. *J Am Med Inform Assoc, 31*(2), 488-498. doi:10.1093/jamia/ocad084 (terbit daring 2023) | Terverifikasi penuh (teks PMC) | Palet dan gaya didokumentasikan dan konsisten; palet kategorikal harus mudah dibedakan dan "value-neutral" (kecerahan mirip); jumlah kategori umumnya 5-6 (kebiasaan, bukan angka ilmiah); sebaran terasa lebih sulit sekitar 6 kategori (dikutip dari Tseng dkk. 2023); CVD sekitar 1 dari 12 pria; peringatan soal makna warna; warna dipersepsi preattentive sehingga efektif untuk kategori bila jumlahnya tidak besar; judul grafik yang aktif | Tutorial/panduan, bukan eksperimen. Judul aktif (menyatakan temuan) tidak kita pakai (bagian 7) |
| R2 | Zhang, N., Zhang, J., Jiang, S., & Ge, W. (2024). The effects of layout order on interface complexity: An eye-tracking study for dashboard design. *Sensors, 24*(18), 5966. doi:10.3390/s24185966 | Abstrak + tinjauan isi | Urutan tata letak memengaruhi pencarian visual; menempatkan chart inti di kiri-tengah dianjurkan ("order is more") | Eksperimen laboratorium dengan antarmuka dashboard yang disederhanakan dan diabstraksi; bukti arahnya sedang, bukan hukum umum |
| R3 | Setlur, V., Correll, M., Satyanarayan, A., & Tory, M. (2024). Heuristics for supporting cooperative dashboard design. *IEEE Trans. Vis. Comput. Graph.* (Proc. IEEE VIS 2023). doi:10.1109/TVCG.2023.3327158 | Abstrak + 9 dari 39 heuristik terbaca | H3 (jelas harus mulai berinteraksi dari mana), H8 (tata letak dan alur mudah diikuti), H12 (format konsisten), H13-H14 (ungkapkan bias dan asal-usul/penyiapan data) | Heuristik dievaluasi dengan 52 mahasiswa pascasarjana lewat tugas rumah, bukan uji efek perilaku. Volume/halaman tidak saya verifikasi. **Koreksi atribusi:** penulisnya Setlur dkk. (bukan Dhanoa), dipresentasikan di VIS 2023, terbit di TVCG 2024 |
| R4 | Schloss, K. B. (2025). Perceptual and cognitive foundations of information visualization. *Annual Review of Vision Science, 11*(1), 303-330 | Abstrak (DOI tidak saya temukan, tidak ditulis) | Interpretasi lebih efektif bila desain selaras dengan cara sistem persepsi dan kognisi membangun interpretasi | Hanya abstrak yang saya baca; dipakai untuk prinsip umum |
| R5 | Patel, A. M., Baxter, W., & Porat, T. (2024). Toward guidelines for designing holistic integrated information visualizations for time-critical contexts: Systematic review. *J Med Internet Res, 26*, e58088. doi:10.2196/58088 | Terverifikasi (abstrak + metode) | Tinjauan PRISMA 46 makalah; prinsip umum Gestalt, reduksi, organisasi | Konteks *time-critical* (terutama kesehatan); penulis sendiri menyatakan belum ada pedoman khusus. Relevansi ke dashboard ini **terbatas**; hanya prinsip umum yang dipakai |
| R6 | Franconeri, S. L., Padilla, L. M., Shah, P., Zacks, J. M., & Hullman, J. (2021). The science of visual data communication: What works. *Psychol Sci Public Interest, 22*(3), 110-161. doi:10.1177/15291006211051956 | Terverifikasi (halaman penerbit + ringkasan APS) | Kanal visual berbeda presisinya; perbandingan antar-nilai lambat sehingga gunakan petunjuk pengelompokan; hindari membebani memori kerja; arahkan perhatian; lihat data dengan sebaran sebelum percaya ringkasan statistik; sumbu nol tidak selalu terbaik | Anjuran "legenda menjadi label tertanam" berasal dari ringkasan APS atas laporan pendamping Schwabish (2021), bukan dari kutipan langsung Franconeri |
| R7 | Heer, J., & Bostock, M. (2010). Crowdsourcing graphical perception: Using Mechanical Turk to assess visualization design. *Proc. ACM CHI*, 203-212. doi:10.1145/1753326.1753357 | Abstrak + halaman penerbit | Mereplikasi Cleveland-McGill dan menambah eksperimen persepsi luas persegi panjang (treemap) | Peringkat akurasi rinci treemap tidak saya verifikasi pada sesi ini; tidak diklaim |
| R8 | Cleveland, W. S., & McGill, R. (1984). Graphical perception: Theory, experimentation, and application to the development of graphical methods. *J Am Stat Assoc, 79*(387), 531-554 | **Sekunder** (kutipan di materi kuliah dan R7) | Urutan tugas persepsi dasar (posisi pada skala sama lebih akurat daripada sudut/luas) | DOI tidak saya temukan; isi tidak dibaca langsung |
| R9 | W3C. Web Content Accessibility Guidelines (WCAG) 2.2: SC 1.4.1 Use of Color, SC 1.4.3 Contrast (Minimum), SC 1.4.11 Non-text Contrast. https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast ; ringkasan rasio teks: WebAIM, https://webaim.org/articles/contrast/ | Terverifikasi (halaman W3C untuk 1.4.11; WebAIM untuk rasio teks 4,5:1 dan 7:1) | Objek grafis yang perlu untuk memahami konten >= 3:1 terhadap warna di sekitarnya (tidak diwajibkan bila nilainya juga disajikan dalam bentuk lain); teks normal >= 4,5:1 (AA), 7:1 (AAA); jangan hanya mengandalkan warna | Standar resmi (guideline), bukan penelitian. Rasio dihitung dengan rumus luminansi relatif WCAG |
| R10 | Okabe, M., & Ito, K. (2008). Color Universal Design (CUD): How to make figures and presentations that are friendly to colorblind people. https://jfly.uni-koeln.de/color/ | Terverifikasi (halaman asli) | Prinsip 3(+1) Color Universal Design; palet 8 warna yang dapat dibedakan pada tiga bentuk buta warna umum; (kodifikasi redundan seperti garis putus + warna dibaca dari ringkasan ProfHacker, sekunder) | Panduan praktisi, bukan makalah peer-reviewed; tritanopia sangat jarang (sekitar 0,001% menurut halaman itu) |
| R11 | Wong, B. (2011). Points of view: Color blindness. *Nature Methods, 8*, 441. doi:10.1038/nmeth.1618 | Terverifikasi (lewat banyak kutipan dan salinan) | Warna yang ramah buta warna juga praktik grafis yang baik; daftar warna Okabe-Ito | Kolom pendek, bukan eksperimen |
| R12 | Sarikaya, A., Correll, M., Bartram, L., Tory, M., & Fisher, D. (2019). What do we talk about when we talk about dashboards? *IEEE Trans. Vis. Comput. Graph.* (IEEE InfoVis 2018) | Abstrak (volume/halaman/DOI tidak saya temukan, tidak ditulis) | Dashboard adalah jenis visualisasi tersendiri dengan tujuan desain dan tingkat interaksi yang berbeda dari alat eksplorasi | Hanya abstrak yang dibaca |
| R13 | Yi, J. S., Kang, Y. a., Stasko, J. T., & Jacko, J. A. (2007). Toward a deeper understanding of the role of interaction in information visualization. *IEEE Trans. Vis. Comput. Graph., 13*(6), 1224-1231. doi:10.1109/TVCG.2007.70515 | Terverifikasi (metadata dan abstrak) | Interaksi dikategorikan menurut maksud pengguna (mis. filter, eksplorasi, abstraksi/elaborasi) | Daftar kategori lengkap tidak saya baca ulang pada sesi ini |
| R14 | Shneiderman, B. (1996). The eyes have it: A task by data type taxonomy for information visualizations. *Proc. IEEE Symposium on Visual Languages*, 336-343 | Terverifikasi (abstrak) | Mantra: overview dulu, lalu zoom dan filter, baru detail sesuai kebutuhan | Dokumen 1996 (teori dasar; tidak dipaksakan 2021+) |
| R15 | Shneiderman, B. (1992). Tree visualization with tree-maps: 2-d space-filling approach. *ACM Trans. Graph., 11*(1), 92-99. doi:10.1145/102377.115768 ; Johnson, B., & Shneiderman, B. (1991). Tree-maps. *IEEE Visualization '91* | Terverifikasi (teks dan metadata) | Treemap: luas persegi panjang sebanding atribut simpul; cocok untuk hierarki yang isi simpul daun dan strukturnya penting | Peringatan: luas bukan kanal yang paling presisi (R8) |
| R16 | Wagemans, J., Elder, J. H., Kubovy, M., Palmer, S. E., Peterson, M. A., Singh, M., & von der Heydt, R. (2012). A century of Gestalt psychology in visual perception: I. *Psychol Bull, 138*(6), 1172-1217. doi:10.1037/a0029333 | Terverifikasi (abstrak) | Prinsip pengelompokan: proximity, similarity, common region, dll. | Tinjauan psikologi persepsi umum, bukan khusus dashboard |
| R17 | Tseng, C., Quadri, G. J., Wang, Z., & Szafir, D. A. (2023). Measuring categorical perception in color-coded scatterplots. *Proc. ACM CHI*. doi:10.1145/3544548.3581416 | Terverifikasi (abstrak) | Jumlah kategori dan keterbedaan warna memengaruhi persepsi pada sebaran (2-10 kategori diuji) | Eksperimen daring dengan tugas menaksir rata-rata |
| R18 | Tseng, C., Wang, A. Z., Quadri, G. J., & Szafir, D. A. (2024). Revisiting categorical color perception in scatterplots. arXiv:2404.03787 | Abstrak; **preprint** (status peer-review tidak saya verifikasi) | Palet kategorikal berbasis hue paling efektif; kecerahan ikut berperan | Preprint |

Sumber sekunder yang hanya saya temukan lewat daftar pustaka R1 (tidak dibaca langsung; dicantumkan sebagai petunjuk, bukan dasar klaim): Borkin dkk. (2016, doi:10.1109/TVCG.2015.2467732, judul dibaca orang), Mackinlay dkk. (2007, doi:10.1109/TVCG.2007.70594), Schwabish dkk. (2022) *Do No Harm Guide: Centering Accessibility in Data Visualization* (Urban Institute).

**Yang TIDAK saya temukan buktinya:** penelitian empiris khusus dashboard tentang ukuran/jenis huruf, dan penelitian yang menyatakan warna tertentu (mis. hijau) harus mewakili energi terbarukan. Karena itu typography dan pemetaan warna-ke-makna dicatat sebagai keputusan proyek (bagian 3).

## 3. Audit keputusan desain saat ini (berdasarkan kode aktual)
Kolom "Perlu diubah?" mencerminkan apa yang benar-benar saya ubah di Fase 4-4.

| Elemen | Keputusan saat ini | Alasan desain | Referensi | Perlu diubah? |
|---|---|---|---|---|
| Background | Putih `#FFFFFF`; latar sekunder (sidebar/kartu) **sebelumnya** `#F3F6F4` (abu kehijauan), kini `#F4F7FA` (cool white) | Latar netral memberi kontras teks tinggi (teks utama 14,76:1 terhadap putih, 13,72:1 terhadap latar sekunder); perubahan nada ke cool white mengikuti konsep palet proyek [KEPUTUSAN PROYEK, bukan klaim penelitian] | R9 (kontras) | Ya (kecil, estetika terkontrol) |
| Card KPI | `st.metric`, 4 kartu per halaman (3-4 pada D/Kualitas); angka besar, selisih bertanda +/- dan panah | Ringkasan dulu, detail kemudian; metrik penting saja | R14, R3 (H8) | Tidak |
| Posisi KPI | Tepat di bawah judul (D: setelah banner interpretasi) | Overview first; titik mulai jelas | R14, R3 (H3, H8), R2 | Tidak |
| Posisi chart utama | Chart inti penuh lebar tepat setelah KPI; pada Ringkasan chart tren terbarukan (inti) di kiri, intensitas di kanan | Chart inti di kiri-tengah dibaca lebih efisien (bukti sedang, studi lab) | R2 | Tidak |
| Warna renewable | `#009E73` (hijau kebiruan Okabe-Ito); konsisten di Ringkasan, A, B, C | **[SUMBER]** warna konsisten sebagai categorical encoding; palet ramah buta warna. **[KEPUTUSAN PROYEK]** pemetaan "hijau kebiruan = terbarukan". Kontras terhadap putih 3,42:1 (lolos 3:1 untuk grafis) | R1, R10, R11, R9 | Tidak untuk data (warna UI diganti, lihat bawah) |
| Warna fossil | `#4D4D4D` (abu netral) | Netral = tidak menonjol; kontras 8,45:1. Pemetaan adalah keputusan proyek | R1, R9 | Tidak |
| Warna nuclear | `#CC79A7` (ungu kemerahan Okabe-Ito) | Pembeda kategori ketiga; kontras 3,06:1; jarak ke warna terbarukan pada deutan 17,9 (marginal, dicatat) | R10, R9 | Tidak |
| Warna residual | Pencilan D: `#E69F00` (di atas garis) dan `#56B4E9` (di bawah garis), nilai tertulis pada batang; B: sisa nuklir hanya angka kartu | Dua warna netral nilai (bukan baik/buruk); nilai juga ditulis sehingga kontras <3:1 diterima (WCAG membolehkan bila nilai disajikan dalam bentuk lain) | R1 (value-neutral), R9 | Tidak |
| Warna background (plot) | Putih; gridline `#E5E7EB` sangat terang | Grid hanya pendukung, tidak diperlukan untuk memahami data | R6 (kurangi beban), R9 | Tidak |
| Warna teks | `#1F2933` (slate gelap) | 14,76:1 (lolos AAA 7:1) | R9 | Tidak |
| Warna kontrol UI (primary) | **Sebelumnya** `#009E73`, kini `#0072B2` (biru laut) | Teks putih di atas `#009E73` hanya 3,42:1 (di bawah 4,5:1 AA untuk teks); `#0072B2` 5,19:1. Selain itu warna kontrol dipisah dari warna data terbarukan agar filter terpilih tidak terbaca sebagai data terbarukan [KEPUTUSAN PROYEK] | R9, R1 (semantik warna) | Ya |
| Chart type | Lihat bagian 5 | Tipe chart mengikuti tugas dan tipe data | R8, R7, R6 | Tidak |
| Filter position | Sidebar global (tahun, benua, kelompok, negara sorotan) | Filter tersedia di semua halaman tanpa mengubah letak; alur jelas | R14, R13, R3 (H3) | Tidak |
| Navigation | `st.navigation`: Ringkasan, A, B, C, D, Kualitas | Urutan overview, analisis tematik, lalu kualitas/metodologi | R14, R3 (H8) | Tidak |
| Typography | Font sans-serif bawaan Streamlit; hierarki judul/subjudul/caption/angka KPI bawaan | Konsistensi font dan hierarki (style guide mendefinisikan font dan ukuran); teks 14,76:1 | R1, R9 | Tidak |
| Spacing | Bawaan Streamlit; pengelompokan lewat kolom, subjudul, dan expander | Elemen yang berdekatan dan satu wilayah dibaca sebagai satu kelompok | R16, R6 | Tidak |
| Table design | `st.dataframe` tanpa indeks, format angka 1-2 desimal, unduh CSV, detail di bawah visual ringkas | Detail sesuai permintaan, setelah ringkasan | R14 | Tidak |
| Tooltip | Hover Plotly: negara, tahun, nilai berbulat, satuan; `help` pada kartu KPI | Detail-on-demand mengurangi beban memori kerja | R14, R6 | Tidak |
| Legend | Legenda horizontal di bawah chart; treemap berlabel langsung | Legenda ada karena kategori >2; label langsung di treemap | R6 | Tidak (lihat bagian 7) |
| Tab structure | D (4 tab), Kualitas (5 tab), A (Tertinggi/Terendah) | Pengungkapan bertahap: satu pertanyaan per tab | R14, R12 | Tidak |
| Section grouping | Judul halaman, KPI, subjudul + keterangan, expander definisi dan sumber di bawah | Overview, temuan/analisis, detail | R14, R3 (H14) | Tidak |
| Empty space | Tidak ada ruang dekoratif; kepadatan mengikuti bawaan Streamlit | Hindari kepadatan berlebih tanpa elemen dekoratif | R5, R6 | Tidak |
| Label usage | Judul deskriptif, sumbu berjudul + satuan, keterangan "cara membaca" | Aturan proyek: tanpa interpretasi/sebab-akibat di dashboard; judul aktif (R1) sengaja tidak dipakai | R1 | Tidak |
| Chart ordering | Tren/ringkasan, peringkat/perbandingan, komposisi/detail, tabel | Overview ke detail | R14 | Tidak |
| Warna benua (A, D, Kualitas) | Enam warna + abu "Tidak diketahui" | Enam kategori masih di rentang yang diuji; jarak minimum antar-warna >= 17,2 pada simulasi buta warna | R17, R1 | Tidak |
| Warna sumber (C) | 9 warna | Kombinasi **Other fossil vs Other renewables** hanya berjarak 4,5 pada deutan (membingungkan) | R10, R17 | Ya (satu warna) |
| Tepi titik sebaran | Tepi putih tipis | Warna terang (`#E69F00`, `#56B4E9`) hanya 2,25:1 dan 2,31:1 terhadap putih; tepi putih tidak memperbaikinya | R9 (1.4.11) | Ya |
| Garis acuan y = x (Kualitas) | `#9CA3AF` (2,54:1) | Garis acuan yang perlu dibaca | R9 | Ya |
| Teks pengembang | Kalimat "(Tahap 4-3)" di Ringkasan; fungsi placeholder lama di tema | Teks internal tidak boleh tampil di halaman selesai | R3 (H14) | Ya |
| Delta KPI hijau/merah | Warna delta bawaan Streamlit + tanda +/- + panah | Kodifikasi redundan: tidak hanya warna | R9 (1.4.1), R10 | Tidak |

## 4. Design Rationale Matrix
| Area | Keputusan desain | Evidence/Prinsip | Referensi | Implementasi |
|---|---|---|---|---|
| Layout | KPI di atas, chart, tabel di bawah | Overview, filter, detail sesuai kebutuhan **[SUMBER]** | R14, R3 | Semua halaman |
| Layout | Chart inti di kiri/tengah | Posisi chart inti memengaruhi pencarian visual; bukti sedang **[SUMBER, terbatas]** | R2 | Ringkasan (kiri), A-D (penuh lebar) |
| Color | Palet terbatas dan konsisten | Konsistensi palet dan jumlah kategori terbatas **[SUMBER]** | R1, R17 | Global (`theme.py`, `charts.py`) |
| Color | Warna data berasal dari palet Okabe-Ito | Dibuat agar dapat dibedakan pada buta warna umum **[SUMBER]** | R10, R11 | Global |
| Color | Hijau kebiruan untuk renewable, abu untuk fosil, ungu kemerahan untuk nuklir, biru untuk sorotan | **[KEPUTUSAN PROYEK]** berdasarkan prinsip categorical encoding yang konsisten; bukan hasil penelitian tentang makna warna | R1 | Ringkasan, A, B, C, D |
| Color | Warna kontrol UI (biru) dipisah dari warna data (hijau kebiruan) | Kontras teks putih di atas warna kontrol 5,19:1 **[SUMBER: WCAG]**; pemisahan makna **[KEPUTUSAN PROYEK]** | R9 | `.streamlit/config.toml` |
| Color | Jarak antar-warna pada simulasi buta warna >= 10 (heuristik) | **[KEPUTUSAN PROYEK]** dikalibrasi dari audit (pasangan lama 4,5 dan 8,3; terburuk yang dipertahankan 12,8) | R10 (prinsip), audit sendiri | `test_desain_44.py` |
| Typography | Hierarki bawaan Streamlit, tidak ada ukuran/jenis tambahan | Konsistensi + kontras teks tinggi; tidak ada bukti empiris khusus dashboard yang saya temukan | R1, R9 | Global |
| Chart | Garis untuk tren waktu, batang berurut untuk peringkat, dumbbell untuk dua nilai, sebaran untuk hubungan, batang 100% + treemap untuk komposisi | Posisi pada skala sama paling akurat; pilihan menurut tugas **[SUMBER]** | R8, R7, R6, R15 | A, B, C, D, Kualitas |
| Chart | Treemap untuk kontribusi sumber (satu tahun) | Hierarki dengan nilai daun; dilengkapi tabel angka karena luas kurang presisi **[SUMBER + keputusan proyek]** | R15, R8 | C |
| Chart | Sebaran + garis regresi + residual | Hubungan dua variabel kuantitatif; lihat data sebelum statistik **[SUMBER]** | R6, R8 | D |
| Interaction | Filter global tahun/benua/kelompok, drill-down per kategori, slider ambang | Filter dan detail-on-demand; tiap interaksi punya tujuan analitis (bagian 6) | R14, R13 | Sidebar, A, B, C, D |
| Table | Detail di bawah ringkasan, dapat diunduh | Pengungkapan bertahap | R14 | A, B, C, D, Kualitas |
| Whitespace/grouping | Kolom, subjudul, expander | Pengelompokan lewat proximity dan common region | R16, R6 | Global |
| Accessibility | Kontras teks AAA, kontrol AA, warna data diaudit buta warna, selisih bertanda +/- | WCAG dan prinsip CUD **[SUMBER]** | R9, R10 | Global, `test_desain_44.py` |
| Transparency | Halaman Kualitas dan Metodologi: sumber, asal data, bias, definisi KPI | Heuristik pengungkapan asal-usul dan bias data **[SUMBER]** | R3 (H13, H14) | Kualitas |

## 5. Audit tipe chart (pertanyaan, data, alasan, referensi, alternatif)
| Halaman | Chart | Pertanyaan analitik | Tipe data | Mengapa sesuai | Alternatif |
|---|---|---|---|---|---|
| Ringkasan, A, B | Garis (tren) | Bagaimana nilai berubah 2019-2023? | Waktu x kuantitatif | Posisi pada skala sama (R8); kontinuitas waktu | Batang per tahun: tidak menekankan perubahan |
| A | Batang peringkat berurut | Negara mana tertinggi/terendah? | Kategori x kuantitatif | Panjang pada baseline sama (R8); urut menurun | Tabel saja: kurang cepat dipindai (tabel ada sebagai detail) |
| Ringkasan | Batang perubahan | Negara mana naik terbesar? | Kategori x selisih | Sama seperti di atas | - |
| Ringkasan | Peta koroplet | Sebaran geografis pangsa | Spasial x kuantitatif | Pertanyaan spasial; warna = nilai (kodifikasi tidak presisi, dilengkapi tooltip) | Peringkat batang (sudah ada) |
| B | Dumbbell | Dua nilai per negara (tahun dasar vs tahun terpilih; listrik vs primer) | Kategori x 2 kuantitatif | Posisi pada skala sama, bukan batang berpasangan (R8) | Batang berkelompok: lebih sulit membandingkan selisih |
| C | Batang 100% bertumpuk per tahun | Bagaimana komposisi berubah? | Bagian-dari-keseluruhan x waktu | Hanya segmen di baseline yang presisi (R8); diatasi drill-down kategori dan tabel angka | Garis per sumber: lebih presisi untuk satu sumber tetapi tidak menunjukkan keseluruhan |
| C | Treemap | Siapa penyumbang terbesar pada satu tahun? | Hierarki kategori-sumber x kuantitatif | Hierarki dengan nilai daun (R15); luas kurang presisi (R8) sehingga ada tabel | Batang terurut |
| D | Sebaran + garis regresi | Bagaimana hubungan pangsa dan intensitas? | 2 kuantitatif (+ukuran, kategori) | Posisi di kedua sumbu paling akurat (R8); lihat data sebelum statistik (R6). Ukuran (luas) hanya pelengkap + tooltip | Heatmap kepadatan: kehilangan identitas negara |
| D | Batang korelasi per benua, batang selisih pencilan | Perbandingan r antarbenua; negara terjauh dari garis | Kategori x kuantitatif | Panjang pada baseline sama (R8) | Tabel (ada) |
| D | Sebaran perubahan | Apakah perubahan pangsa berjalan dengan perubahan intensitas? | 2 selisih kuantitatif | Sama seperti sebaran | - |
| Kualitas | Batang cakupan, tabel hitungan | Seberapa lengkap data? | Kategori x persen | Panjang pada baseline sama (R8); angka asli di label dan tabel | - |
| Kualitas | Garis sederhana vs tertimbang, sebaran Ember vs Renewable (garis y = x) | Apakah dua cara/sumber berbeda? | Waktu x kuantitatif; 2 kuantitatif | Posisi (R8); garis acuan menunjukkan kesamaan | - |
| Kualitas | Tabel status OK/BEDA | Apakah antar-view konsisten? | Teks | Status berupa teks, bukan hanya warna (R9, 1.4.1) | - |

## 6. Tujuan analitis setiap interaksi
| Interaksi | Masalah analitik yang diselesaikan | Referensi |
|---|---|---|
| Filter tahun | Membandingkan kondisi pada tahun berbeda dengan tahun dasar tetap | R14 (filter), R13 |
| Filter benua dan kelompok | Menyempit ke subset negara tanpa membuat halaman baru | R14, R13 |
| Negara sorotan | Membandingkan satu negara dengan agregat | R13 (elaborasi) |
| Slider ambang pembangkitan | Menguji sensitivitas peringkat terhadap negara kecil (ambang = keputusan desain) | R13 |
| Radio/selectbox drill-down (C, A, B) | Berpindah dari ringkasan ke detail sumber/kategori | R14 (zoom dan detail) |
| Tab (D, Kualitas) | Memisahkan beberapa pertanyaan analitik agar halaman tidak padat | R14, R5 |
| Unduh CSV | Memeriksa angka di luar dashboard (transparansi) | R3 (H14) |

## 7. Hasil audit warna (angka dari perhitungan, bukan opini)
Metode: kontras = rumus luminansi relatif WCAG; simulasi buta warna = matriks Machado dkk. (2009) severity 100% (protanopia, deuteranopia, tritanopia) pada RGB linear;
jarak warna = CIELAB dE*ab. Ambang **10 adalah heuristik proyek** (bukan standar): pasangan lama yang membingungkan berjarak 4,5 dan 8,3 sedangkan pasangan terburuk
yang dipertahankan 12,8. Audit awal memakai ruang CAM02-UCS (pustaka `colorspacious`) dengan hasil searah; test memakai CIELAB agar tidak perlu dependensi baru.
- **Teks:** `#1F2933` 14,76:1 (putih), 13,72:1 (latar sekunder): lolos AAA.
- **Objek grafis < 3:1 terhadap putih (diterima, dicatat, dijaga test T4):** `#E69F00` (Africa, Solar, 2,25), `#56B4E9` (North America, Wind, 2,31), `#B5B5B5` (Other fossil, 2,05),
  `#BBBBBB` (abu "Tidak diketahui", 1,92). Alasan diterima: warna Okabe-Ito dipilih agar dapat dibedakan pada buta warna; nilai selalu juga ada di tooltip/tabel/label; pada sebaran kini ada tepi gelap.
- **Pasangan marginal (jarak 10-20; dicatat, dijaga test T3):** Nuclear/Other fossil 12,8 (deutan); Gas/Nuclear 13,8 (deutan); Coal/Other renewables 15,4 (deutan); Gas/Other renewables 16,4 (deutan);
  sorotan/terbarukan 17,0 (tritan); Nuclear/Solar 17,2 (tritan); Africa/Asia 17,2 (tritan); nuklir/terbarukan 17,9 (deutan); Africa/South America 18,3 (deutan). Tritanopia sangat jarang (R10).
  Mitigasi: urutan tumpukan tetap, label di treemap, legenda, tooltip.
- **Tidak ada pasangan di bawah 10** setelah perubahan.

## 8. Perubahan yang dilakukan
1. `dashboard/halaman/ringkasan.py`: kalimat "(Tahap 4-3)" dihapus (teks pengembang). Output angka tidak berubah.
2. `dashboard/theme.py`: fungsi `placeholder()` Tahap 4-2 (sudah tidak dipakai) dan impor yang tidak diperlukan dihapus; komentar palet dikoreksi (palet data utama = Okabe-Ito; pemetaan makna = keputusan proyek).
3. `.streamlit/config.toml`: `primaryColor` `#009E73` ke `#0072B2` (alasan WCAG 1.4.3 dan pemisahan makna, bagian 3); `secondaryBackgroundColor` `#F3F6F4` ke `#F4F7FA`.
4. `dashboard/charts.py`: "Other renewables" `#66C2A5` ke `#882255` (jarak minimum ke 8 sumber lain naik dari 4,5 menjadi >= 15,4); tepi titik tiga grafik sebaran (D sebaran, D perubahan, Kualitas Ember vs Renewable)
   dari putih ke abu gelap `#4B5563` 0,5 px (konstanta `MARKER_EDGE`); garis acuan y = x dari `#9CA3AF` ke `#6B7280`.
5. `dashboard/tests/test_desain_44.py` (baru, 23 pemeriksaan): kontras teks/kontrol, jarak warna pada tiga jenis buta warna, daftar pasangan marginal, daftar pengecualian < 3:1, tepi titik, tidak ada teks pengembang di 6 halaman, delta KPI bertanda.

## 9. Perubahan yang SENGAJA tidak dilakukan
| Yang dipertahankan | Alasan |
|---|---|
| Palet Okabe-Ito (termasuk `#E69F00` dan `#56B4E9` yang < 3:1) | Keterbedaan pada buta warna diprioritaskan; nilai selalu tersedia di tooltip/tabel; mengganti warna mengorbankan konsistensi dan pembeda kategori |
| Warna data terbarukan `#009E73`, fosil, nuklir, intensitas, sorotan | Sudah konsisten di semua halaman; tidak ada bukti yang mewajibkan perubahan; pemetaan = keputusan proyek |
| Teks utama `#1F2933` (tidak diganti navy) | Sudah 14,76:1; mengganti hanya demi estetika bertentangan dengan urutan prioritas |
| Label langsung pada garis tren (menggantikan legenda) | Anjuran umum (R6) tetapi tanpa tampilan di browser saya tidak dapat menjamin label tidak saling menutup; ditunda sampai ada tangkapan layar |
| Kodifikasi bentuk (simbol per benua) pada sebaran | Warna sudah lolos jarak >= 10 pada buta warna; 200+ titik berukuran variabel akan makin padat; tinjau ulang bila evaluasi SUS/Nielsen menemukan kebingungan |
| Judul chart yang menyatakan temuan ("judul aktif", R1) | Aturan proyek: dashboard tidak memuat interpretasi/sebab-akibat; interpretasi hanya di laporan Bab IV |
| Struktur tab, urutan halaman, posisi filter, tipe chart | Sesuai prinsip (bagian 3-6); perubahan berisiko mengganggu makna analitis dan divalidasi |
| Hijau/merah bawaan Streamlit pada selisih KPI | Selisih juga ditulis dengan tanda +/- dan panah (kodifikasi redundan) |
| Ukuran/jenis huruf, jarak antar-elemen | Bawaan Streamlit konsisten; tidak ada bukti empiris khusus dashboard yang mendorong perubahan |

## 10. Batasan dan yang harus diperiksa manual
- **Tampilan visual belum diperiksa.** Cek di browser: ukuran/legenda sebaran, treemap, warna kontrol biru (filter, tab, tombol), dan kejelasan tepi titik gelap (jika terlalu berat, kembalikan `MARKER_EDGE` ke putih; tes T4 akan memberi tahu).
- **Warna teks keterangan (caption) Streamlit:** kontrasnya tidak dapat saya ukur dari kode (diturunkan dari tema dengan opasitas); ukur dengan alat kontras di browser.
- **Efek `primaryColor` pada tiap widget Streamlit** tidak diverifikasi secara visual; alasan perubahan bertumpu pada rasio WCAG untuk teks putih di atas warna kontrol.
- **Bukti literatur terbatas:** R2 (studi lab, antarmuka disederhanakan), R3 (evaluasi oleh mahasiswa), R5 (konteks time-critical). Tidak ada bukti yang saya temukan untuk typography khusus dashboard maupun makna warna tertentu.
- **Validasi empiris sebenarnya** untuk desain ini adalah evaluasi SUS dan Nielsen Heuristic Evaluation (V1 ke V2) yang direncanakan; hasil literatur hanya menguatkan dasar keputusan.

## 11. Hasil test (sandbox: PostgreSQL 16, Python 3.12; bukan PostgreSQL 18 lokal)
| Pemeriksaan | Hasil aktual |
|---|---|
| Desain 4-4 (`test_desain_44.py`) | 23/23 |
| Halaman A | 39/39 |
| Halaman B | 47/47 |
| Halaman C | 56/56 |
| Halaman D | 77/77 |
| Kualitas | 78/78 |
| Smoke | 26/26 |
| SQL 98 (C) / 99 (D) | 70 OK / 23 OK, 0 BEDA, 0 error |
| SQL 100 (Kualitas) | 82 OK / 0 BEDA / 0 error |

Cara menjalankan (venv aktif, dari folder proyek): `python dashboard/tests/test_desain_44.py`, lalu test A, B, C, D, Kualitas, smoke seperti fase sebelumnya; `sql/100_validate_quality.sql` sebagai `postgres`.
Test `test_desain_44.py` memakai `tomllib` (Python 3.11+; proyek memakai 3.12).

## 12. MD5 (cek sebelum menimpa dan sesudahnya; PowerShell: `Get-FileHash <file> -Algorithm MD5`)
| File | MD5 versi 4-3e (harus cocok sebelum menimpa) | MD5 baru |
|---|---|---|
| `dashboard\charts.py` | 91c6f5d4ccd676ddf27b318c7c22bff6 | 6fe1cc9234ab6e0f5c8d9ee1cc8dfac8 |
| `dashboard\theme.py` | 3144b92b98051f8bb9975ddf55b8efe7 | 760f5ab950bbf80f77f1a6b5817400ae |
| `dashboard\halaman\ringkasan.py` | 910636a48519df6280e366d5a6646aa9 | 9ce1cde2ddad1181daf778f270dd9490 |
| `.streamlit\config.toml` | 8fcd0d3af9e827ade8af7c5c0c0c62af | 2ac70b80b132b9bef3276de683fe00fe |
| `dashboard\tests\test_desain_44.py` | (baru) | 9deaf519193fa111cd9dfcea5da3989b |

Jika MD5 lama berbeda, JANGAN menimpa; kabari dulu.

## 13. Daftar referensi (APA ringkas; status verifikasi di bagian 2)
Cleveland, W. S., & McGill, R. (1984). *J Am Stat Assoc, 79*(387), 531-554. | Franconeri, S. L., Padilla, L. M., Shah, P., Zacks, J. M., & Hullman, J. (2021). *Psychol Sci Public Interest, 22*(3), 110-161. https://doi.org/10.1177/15291006211051956 |
Graze, M., & Schwabish, J. (2024). *J Am Med Inform Assoc, 31*(2), 488-498. https://doi.org/10.1093/jamia/ocad084 | Heer, J., & Bostock, M. (2010). *Proc. ACM CHI*, 203-212. https://doi.org/10.1145/1753326.1753357 |
Johnson, B., & Shneiderman, B. (1991). Tree-maps. *IEEE Visualization '91*. | Okabe, M., & Ito, K. (2008). Color Universal Design (CUD). https://jfly.uni-koeln.de/color/ |
Patel, A. M., Baxter, W., & Porat, T. (2024). *J Med Internet Res, 26*, e58088. https://doi.org/10.2196/58088 | Sarikaya, A., Correll, M., Bartram, L., Tory, M., & Fisher, D. (2019). *IEEE Trans. Vis. Comput. Graph.* (InfoVis 2018). |
Schloss, K. B. (2025). *Annu Rev Vis Sci, 11*(1), 303-330. | Setlur, V., Correll, M., Satyanarayan, A., & Tory, M. (2024). *IEEE Trans. Vis. Comput. Graph.* https://doi.org/10.1109/TVCG.2023.3327158 |
Shneiderman, B. (1992). *ACM Trans. Graph., 11*(1), 92-99. https://doi.org/10.1145/102377.115768 | Shneiderman, B. (1996). *Proc. IEEE Symp. Visual Languages*, 336-343. |
Tseng, C., Quadri, G. J., Wang, Z., & Szafir, D. A. (2023). *Proc. ACM CHI*. https://doi.org/10.1145/3544548.3581416 | Tseng, C., Wang, A. Z., Quadri, G. J., & Szafir, D. A. (2024). arXiv:2404.03787 (preprint). |
W3C. (2023). *Web Content Accessibility Guidelines (WCAG) 2.2.* https://www.w3.org/TR/WCAG22/ (halaman 1.4.11 terverifikasi) | Wagemans, J., et al. (2012). *Psychol Bull, 138*(6), 1172-1217. https://doi.org/10.1037/a0029333 |
Wong, B. (2011). *Nat Methods, 8*, 441. https://doi.org/10.1038/nmeth.1618 | Yi, J. S., Kang, Y. a., Stasko, J. T., & Jacko, J. A. (2007). *IEEE Trans. Vis. Comput. Graph., 13*(6), 1224-1231. https://doi.org/10.1109/TVCG.2007.70515 |
Zhang, N., Zhang, J., Jiang, S., & Ge, W. (2024). *Sensors, 24*(18), 5966. https://doi.org/10.3390/s24185966 | |


---

# Tahap 2 Redesign Visual: "Luminous Eco-Intelligence" Design System (Evaluasi SUS & Nielsen Heuristics)

Pembaruan ini **hanya menyentuh lapisan visual/UI** (`.streamlit/config.toml`, `dashboard/style.py`, `dashboard/components.py`, `dashboard/theme.py`, `dashboard/charts.py`, `dashboard/app.py`, dan tata letak `dashboard/halaman/*.py`). Seluruh logika ETL (`src/`), skema & view database (`sql/`), koneksi baca-saja (`dashboard/db.py`, `dashboard/settings.py`), serta query SQL dan rumus KPI (`dashboard/queries.py`) **tidak diubah**.

## Ringkasan Sistem Visual ("Luminous Eco-Intelligence")
- **Kanvas & Permukaan:** latar utama Soft Mint-Mist (`#F4F7F6`), sidebar Cool Sage (`#EAF0EE`), kartu permukaan putih (`#FFFFFF`, radius `14px`, border `#DCE5E2`, bayangan halus) untuk separasi *figure-ground* yang tegas.
- **Warna Primer & Kontras:** warna kontrol utama Emerald Deep (`#047857`, kontras teks putih `5,48:1` — lolos WCAG AA), teks utama Deep Forest Ink (`#0F2922`, kontras `14,32:1` pada kanvas dan `13,37:1` pada sidebar — lolos WCAG AAA). Seluruh CSS berjalan **100% offline** (tanpa `@import` atau CDN eksternal).
- **Komponen Reusable (`dashboard/components.py`):**
  - `hero_banner()` & `active_filter_chips()`: banner kompak bergradien domain (Eco, Slate-Bronze, Navy-Cyan, Teal-Amber, Slate-Emerald) dengan ilustrasi SVG inline dan chip status filter aktif.
  - `micro_guide()` (`💡`), `insight_box()` (`📌` dinamis dari data, tanpa klaim kausal), `empty_state()` ramah pengguna, `status_cards()`, `glossary_box()`, `etl_sidebar_card()`, dan `correlation_card_accent()`.

## Pemetaan Perbaikan terhadap Temuan Evaluasi SUS & Nielsen Heuristics
| Kode Temuan | Fokus Usability / Heuristik | Implementasi Redesign |
|---|---|---|
| **H1, M08** | *Visibility of System Status* | Chip filter aktif permanen di Hero Banner setiap halaman + kartu status sinkronisasi ETL di sidebar. |
| **M01 (Severity 3.5)** | *Error Prevention & NULL-Safety* | Pengamanan `pd.isna()`/fallback pada seluruh perhitungan delta tampilan & render halaman (teruji pada kombinasi `"Tidak diketahui"` + tahun 2020 di 6 halaman) + `components.empty_state()`. |
| **R05, M01, M02, M03** | *Help, Feedback, & Error Recovery* | Indikator loading pembaruan (`st.spinner` + styling `stStatusWidget`), mikro-panduan (`💡`), kotak insight dinamis (`📌`), serta empty state kontekstual (`filter_empty_message()`) yang membedakan filter kosong vs kombinasi tak beririsan. |
| **M04, M05, M06** | *Consistency & Semantic Coding* | Judul kartu KPI dan judul bagian visualisasi (`h2`/`h3`) seragam **ALL CAPS**, angka *tabular numerals*, tinggi 4 kartu KPI sejajar, pil delta hijau/coral, serta aksen warna korelasi negatif/positif pada Halaman D. |
| **M07** | *Visual Distinction* | Peringkat Halaman A membedakan tab **Tertinggi** (hijau emerald `#059669`) dan **Terendah** (merah coral `#DC2626`), plus badge visual status kelengkapan di tabel detail. |
| **R10** | *Aesthetic & Minimalist Sidebar* | Sidebar Cool Sage dengan pil multiselect lembut (`#D1FAE5` / `#065F46`, kontras `6,78:1`) dan kontainer gulir (`max-height: 96px`). |
| **R12** | *Match Between System & Real World* | Halaman B menyediakan tampilan default **Grouped Bar Chart** berdampingan (2019 vs tahun terpilih) di samping opsi **Garis rentang (Dumbbell)**. |
| **M09, M10 (T10)** | *Contrast & Language Consistency* | Palet cerah & kontras tinggi untuk 9 sumber pembangkitan di `SUMBER_COLOR` (`charts.py`) dengan label Bahasa Indonesia yang konsisten pada grafik, tabel detail, dan padanan *"Diagram petak (Treemap)"*. |
| **M11 (T11, E3)** | *Error Prevention — Peta Ringkasan* | `share_map()` diubah dari gradasi hijau kontinu menjadi **5 kelas warna diskrit per 20%** ramah buta warna, warna abu-abu netral `#E2E8F0` + legenda *"Abu-abu = Tidak ada data"*, garis batas negara tegas, dan tooltip detail. |
| **M12 (T12, E3)** | *Recognition Rather Than Recall — Kualitas Data* | `coverage_bar()` menampilkan label gabungan absolut + persen (mis. `210 dari 221 (95,0%)`) serta legenda warna sumber (`Renewable` vs `Ember`), dilengkapi 3 kartu ringkasan status agregat baru di atasnya. |
| **R04, R09, R11, R20** | *Progressive Disclosure & Plain-Language Glossary* | Kamus Istilah & Satuan global di sidebar (*Pangsa*, *Bauran*, *TWh*, *gCO₂e/kWh*, *Poin persentase*), Panduan Istilah Statistik di Halaman D, serta 3 kartu status + Kamus Istilah di Halaman Kualitas Data (seluruh **M01–M12** & **R01–R20** teratasi tuntas). |

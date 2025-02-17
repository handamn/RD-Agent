flowchart TD
    A[Mulai] --> B[Buka PDF & Scan Seluruh Halaman]
    B --> C{Apakah Halaman Satu Kolom?}
    C -->|Ya| D[Ekstrak Teks Langsung]
    C -->|Tidak| E{Apakah Halaman Dua Kolom?}
    E -->|Ya| F[Pisahkan Teks Kiri dan Kanan ID & EN]
    E -->|Tidak| G{Apakah Halaman Memiliki Tabel?}
    F --> H[Ekstrak Tabel Jika Ada]
    D --> H[Ekstrak Tabel Jika Ada]
    G -->|Ya| I{Apakah Tabel Merge Cell?}
    G -->|Tidak| J[Ekstrak Tabel Normal]
    I -->|Ya| K[Ekstrak Tabel Merge Cells]
    I -->|Tidak| L[Ekstrak Tabel Normal]
    K --> M[Ekstrak OCR Jika Diperlukan]
    L --> M[Ekstrak OCR Jika Diperlukan]
    J --> M[Ekstrak OCR Jika Diperlukan]
    H --> M[Ekstrak OCR Jika Diperlukan]
    M --> N[Simpan Metadata Layout & Konten]
    N --> O[Ekstraksi Konten Sesuai Metadata]
    O --> P[Post-Processing: Hapus Duplikasi & Format]
    P --> Q[Simpan Output dalam Format JSON atau Struktural Lain]
    Q --> R[Selesai]

    
    class A,B,C,D,E,F,G,H,I,J,K,L,M,N,O,P,Q,R default;


```mermaid
graph TD;
    A(🔍 Load PDF) --> B(📏 Detect Layout)
    B -->|Single Column| C[🔹 Split Sections Normally]
    B -->|Multi Column| D[🔹 Split Sections by Columns]

    C --> E{📌 Detect Content Type}
    D --> E

    E -->|Text| F[Teks Biasa]
    E -->|Table| G{📌 Detect Table Type}
    E -->|Image| H{🔍 Perform OCR}

    G -->|Normal| I[Tabel Normal]
    G -->|Continued| J[Tabel Berlanjut]
    G -->|Merged Cell| K[Tabel Merged Cell]

    H -->|Contains Table| L[OCR Tabel]
    H -->|No Table| M[OCR Teks]

    F --> Z(📌 Mark Page & Save Metadata)
    I --> Z
    J --> Z
    K --> Z
    L --> Z
    M --> Z

    Z -->|Next Page| A

```
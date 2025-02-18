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


```mermaid
graph TD;
    %% Step 1: Persiapan PDF dan Layout Deteksi
    A[1.1 🔍 Load PDF] --> B[1.2 📏 Detect Layout]

    %% Step 2: Pemisahan Halaman Berdasarkan Layout
    B -->|Single Column| C[2.1 Single Column: Split Sections]
    B -->|Multi Column| D[2.2 Multi Column: Split by Columns]

    %% Step 3: Deteksi Jenis Konten
    C --> E[3.1 📌 Detect Content Type per Section]
    D --> E
    E -->|Text| F[3.2 Teks Biasa]
    E -->|Table| G[3.3 📌 Detect Table Type]
    E -->|Image| H[3.4 OCR Teks atau Tabel]
    
    %% Step 4: Deteksi Tabel
    G -->|Normal| I[4.1 Tabel Normal]
    G -->|Continued| J[4.2 Tabel Berlanjut]
    G -->|Merged Cell| K[4.3 Tabel Merged Cell]
    
    %% Step 5: OCR Teks
    H -->|Teks| L[5.1 OCR Teks]
    H -->|Tabel| M[5.2 OCR Tabel]

    %% Step 6: Marking dan Metadata
    F --> Z[6.1 📌 Mark Page & Save Metadata]
    I --> Z
    J --> Z
    K --> Z
    L --> Z
    M --> Z

    Z -->|Next Page| A

```


```mermaid
graph TD
    A[Mulai Proses] --> B[Step 1: Deteksi Layout & Konten]
    B --> C[Step 2: Ekstraksi Konten]
    C --> D[Step 3: Penyempurnaan & Pengolahan Data]
    D --> E[Step 4: Penyimpanan dan Ekspor Hasil]
    E --> F[Selesai]

    B -->|Input| G[File PDF]
    G -->|Output| H[Metadata = Layout, Konten]
    
    C -->|Input| H[Metadata]
    C -->|Output| I[Data Diekstrak = Teks, Tabel, OCR]

    D -->|Input| I[Data Diekstrak]
    D -->|Output| J[Data Bersih = Teks, Tabel Gabungan]

    E -->|Input| J[Data Bersih]
    E -->|Output| K[File Output = CSV, Excel, dll]

```

```mermaid
flowchart TB
  node_1(["Start"])
  node_2[/"Input : File_PDF"/]
  node_3[["Step1 : Deteksi Layout #amp; Konten"]]
  node_4[/"Output/Input : MetaData"/]
  node_5[["Step2 : Ekstraksi Konten"]]
  node_6[/"Output/Input : Data Ekstrak"/]
  node_7[["Step3 : Penyempurnaan #amp; Pengolahan Data"]]
  node_8[/"Output/Input : Data Bersih"/]
  node_9[["Step4 : Penyimpanan #amp; Ekspor Hasil"]]
  node_10[/"Output : CSV/Excel/JSON/dll"/]
  node_11(["Finish"])
  node_1 --> node_2
  node_2 --> node_3
  node_3 --> node_4
  node_4 --> node_5
  node_5 --> node_6
  node_6 --> node_7
  node_7 --> node_8
  node_8 --> node_9
  node_9 --> node_10
  node_10 --> node_11
  
```


```mermaid
graph TD;
    %% Step 1: Deteksi Layout & Konten
    A[1.1 🔍 Load PDF] --> B[1.2 📏 Detect Layout]
    B -->|Single Column| C[2.1 Single Column: Split Sections]
    B -->|Multi Column| D[2.2 Multi Column: Split by Columns]

    %% Step 2: Deteksi Jenis Konten
    C --> E[3.1 📌 Detect Content Type per Section]
    D --> E
    E -->|Text| F[3.2 Teks Biasa]
    E -->|Table| G[3.3 📌 Detect Table Type]
    E -->|Image| H[3.4 OCR Teks atau Tabel]

    %% Step 3: Ekstraksi Data
    G -->|Normal| I[4.2 Ekstraksi Tabel Normal]
    G -->|Continued| J[4.3 Ekstraksi Tabel Berlanjut]
    G -->|Merged Cell| K[4.4 Ekstraksi Tabel Merged Cell]
    
    H -->|Teks| L[5.1 OCR Teks]
    H -->|Tabel| M[5.2 OCR Tabel]

    %% Step 4: Penyempurnaan & Penyimpanan Data
    F --> Z[6.1 📌 Mark Page & Save Metadata]
    I --> Z
    J --> Z
    K --> Z
    L --> Z
    M --> Z
    Z -->|Next Page| A

```

```mermaid
flowchart TB
  node_1(["Start"])
  node_2[/"Input : File PDF"/]
  node_3["Load PDF"]
  node_4["Extract Text"]
  node_5{"Can Extract?"}
  node_6["Detect Layout"]
  node_7["OCR"]
  node_8{"Singular Coloumn?"}
  node_9["Split Section"]
  node_10["Split by Coloumn"]
  node_11[/"Input/Output : 
  Metadata & OCR Layout"/]
  node_12["Detect Content Type per Section"]
  node_13{"Type?"}
  node_14["Text"]
  node_15["Detect Table Type"]
  node_16["Image Scan"]
  node_17{"Header/Cell Type?"}
  node_18["Normal Table"]
  node_19["Merge Table"]
  node_20{"Length Table?"}
  node_21["Page #lt;= 1"]
  node_22["Page #gt; 1"]
  node_23["OCR"]
  node_24{"Text/Table OCR?"}
  node_25["Content Type"]
  node_26[/"Output :
  Update Metadata with Content Type"/]
  node_27(["Finish"])

  node_1 --> node_2
  node_2 --> node_3
  node_3 --> node_4
  node_3 --> node_12
  node_4 --> node_5
  node_5 --"Can"--> node_6
  node_5 --"Cant"--> node_7
  node_7 --> node_6
  node_6 --> node_8
  node_8 --"Yes"--> node_9
  node_8 --"Multiple"--> node_10
  node_10 --> node_9
  node_9 --> node_11
  node_11 --> node_12
  node_12 --> node_13
  node_13 --"Text"--> node_14
  node_24 --"Table"--> node_15
  node_13 --"Table"--> node_15
  node_13 --"Image"--> node_16
  node_15 --> node_17
  node_17 --> node_18
  node_17 --> node_19
  node_18 --> node_20
  node_19 --> node_20
  node_20 --> node_21
  node_20 --> node_22
  node_16 --> node_23
  node_23 --> node_24
  node_24 --"Text"--> node_14
  node_14 --> node_25
  node_21 --> node_25
  node_22 --> node_25
  node_25 --> node_26
  node_26 --> node_27

  

```


```mermaid
flowchart TB
  %% Step 1: Load PDF & Layout Detection
  A1(["Start"])
  A2[/"Input: File PDF"/]
  A3["Load PDF"]
  A4["Extract Text"]
  A5{"Can Extract?"}
  A6["Detect Layout"]
  A7["OCR Layout (if needed)"]
  A8{"Single Column?"}
  A9["Split Section"]
  A10["Split by Column"]
  A11[/"Output: Metadata Layout"/]

  %% Step 2: Content Type Detection
  B1["Detect Content Type per Section"]
  B2{"Type?"}
  B3["Text"]
  B4["Detect Table Type"]
  B5["Image Scan"]
  B6{"Header/Cell Type?"}
  B7["Normal Table"]
  B8["Merge Table"]
  B9{"Length Table?"}
  B10["Page #lt;= 1"]
  B11["Page #gt; 1"]
  B12["OCR"]
  B13{"Text/Table OCR?"}
  B14["Content Type"]
  B15[/"Output: Metadata with Content Type"/]

  %% Step 3: Extraction Process
  C1["Extract Data Based on Metadata"]
  C2["Extract Text"]
  C3["Extract Table"]
  C4["Extract OCR Text"]
  C5["Extract OCR Table"]
  C6["Data Cleaning"]
  C7[/"Output: JSON/CSV/Database"/]

  %% Flow
  A1 --> A2
  A2 --> A3
  A3 --> A4
  A4 --> A5
  A5 --"Yes"--> A6
  A5 --"No"--> A7
  A7 --> A6
  A6 --> A8
  A8 --"Yes"--> A9
  A8 --"No"--> A10
  A10 --> A9
  A9 --> A11
  A11 --> B1
  B1 --> B2
  B2 --"Text"--> B3
  B2 --"Table"--> B4
  B2 --"Image"--> B5
  B4 --> B6
  B6 --> B7
  B6 --> B8
  B7 --> B9
  B8 --> B9
  B9 --> B10
  B9 --> B11
  B5 --> B12
  B12 --> B13
  B13 --"Text"--> B3
  B13 --"Table"--> B4
  B3 --> B14
  B10 --> B14
  B11 --> B14
  B14 --> B15
  B15 --> C1
  C1 --> C2
  C1 --> C3
  C1 --> C4
  C1 --> C5
  C2 --> C6
  C3 --> C6
  C4 --> C6
  C5 --> C6
  C6 --> C7

```


```mermaid
flowchart TB
  %% Step 1: Load PDF & Layout + Content Detection
  A1(["Start"])
  A2[/"Input: File PDF"/]
  A3["Load PDF"]
  A4["Extract Text"]
  A5["Detect Layout & Content"]
  A6{"Column Layout?"}
  A7["Single Column"]
  A8["Multi Column"]
  A9["Split Sections"]
  A10[/"Output: Metadata Layout & Content Type"/]

  %% Step 2: OCR & Table Classification (Jika Diperlukan)
  B1{"Has Image Content?"}
  B2["OCR Processing"]
  B3{"OCR Result: Table or Text?"}
  B4["OCR Text"]
  B5["OCR Table"]
  B6["Detect Table Type"]
  B7{"Table Type?"}
  B8["Normal Table"]
  B9["Merged Table"]
  B10["Continued Table"]
  B11[/"Output: Updated Metadata with OCR & Table Type"/]

  %% Step 3: Extraction
  C1["Extract Data Based on Metadata"]
  C2["Extract Text"]
  C3["Extract Table"]
  C4["Extract OCR Text"]
  C5["Extract OCR Table"]
  C6["Data Cleaning"]
  C7[/"Output: JSON/CSV/Database"/]

  %% Flow
  A1 --> A2
  A2 --> A3
  A3 --> A4
  A4 --> A5
  A5 --> A6
  A6 --"Yes"--> A7
  A6 --"No"--> A8
  A8 --> A9
  A7 --> A9
  A9 --> A10
  A10 --> B1
  B1 --"Yes"--> B2
  B1 --"No"--> C1
  B2 --> B3
  B3 --"Text"--> B4
  B3 --"Table"--> B5
  B4 --> B11
  B5 --> B6
  B6 --> B7
  B7 --> B8
  B7 --> B9
  B7 --> B10
  B8 --> B11
  B9 --> B11
  B10 --> B11
  B11 --> C1
  C1 --> C2
  C1 --> C3
  C1 --> C4
  C1 --> C5
  C2 --> C6
  C3 --> C6
  C4 --> C6
  C5 --> C6
  C6 --> C7

```


# Step1
```mermaid
flowchart TB
  %% Step 1: Load PDF & Layout + Content Detection
  A1(["Start"])
  A2[/"Input: File PDF"/]
  A3["Load PDF"]
  A4["Extract Text"]
  A5["Detect Layout & Content"]
  A6{"Column Layout?"}
  A7["Single Column"]
  A8["Multi Column"]
  A9["Split Sections"]
  A10[/"Output: Metadata Layout & Content Type"/]

  %% Step 2: Deteksi Tabel atau OCR (Jika Diperlukan)
  B1{"Has Image Content?"}
  B2["OCR Processing"]
  B3{"OCR Result: Table or Text?"}
  B4["OCR Text"]
  B5["OCR Table"]
  
  %% Step 3: Deteksi Tabel (Untuk Semua Konten, Termasuk OCR & Teks Langsung)
  C1{"Has Table?"}
  C2["Detect Table Type"]
  C3{"Table Type?"}
  C4["Normal Table"]
  C5["Merged Table"]
  C6["Continued Table"]
  C7[/"Output: Updated Metadata with Table Type"/]

  %% Step 4: Extraction
  D1["Extract Data Based on Metadata"]
  D2["Extract Text"]
  D3["Extract Table"]
  D4["Extract OCR Text"]
  D5["Extract OCR Table"]
  D6["Data Cleaning"]
  D7[/"Output: JSON/CSV/Database"/]

  %% Flow
  A1 --> A2
  A2 --> A3
  A3 --> A4
  A4 --> A5
  A5 --> A6
  A6 --"Yes"--> A7
  A6 --"No"--> A8
  A8 --> A9
  A7 --> A9
  A9 --> A10
  A10 --> B1
  B1 --"Yes"--> B2
  B1 --"No"--> C1
  B2 --> B3
  B3 --"Text"--> B4
  B3 --"Table"--> B5
  B4 --> C1
  B5 --> C1

  %% Deteksi Tabel Jika Ada
  C1 --"Yes"--> C2
  C1 --"No"--> D1
  C2 --> C3
  C3 --"Normal"--> C4
  C3 --"Merged"--> C5
  C3 --"Continued"--> C6
  C4 --> C7
  C5 --> C7
  C6 --> C7
  C7 --> D1

  %% Ekstraksi Data
  D1 --> D2
  D1 --> D3
  D1 --> D4
  D1 --> D5
  D2 --> D6
  D3 --> D6
  D4 --> D6
  D5 --> D6
  D6 --> D7

```


# Step2
```mermaid
flowchart TB
  %% Step 1: Start Ekstraksi
  A1(["Start Extraction"])
  A2[/"Input: Metadata Content Type"/]

  %% Step 2: Pilih Tipe Konten
  B1{"Content Type?"}
  B2["Extract Text"]
  B3["Extract Table"]
  B4["Extract OCR Text"]
  B5["Extract OCR Table"]
  
  %% Step 3: Tabel Langsung
  C1{"Table Type?"}
  C2["Extract Normal Table"]
  C3["Extract Merged Table"]
  C4["Extract Continued Table"]

  %% Step 4: Tabel OCR
  D1{"OCR Table Type?"}
  D2["Extract OCR Normal Table"]
  D3["Extract OCR Merged Table"]
  D4["Extract OCR Continued Table"]

  %% Step 5: Data Cleaning & Output
  E1["Data Cleaning & Formatting"]
  E2[/"Output: JSON, CSV, Database"/]

  %% Flow
  A1 --> A2
  A2 --> B1
  B1 --"Text"--> B2
  B1 --"Table"--> B3
  B1 --"OCR Text"--> B4
  B1 --"OCR Table"--> B5

  %% Pilih Tipe Tabel
  B3 --> C1
  C1 --"Normal"--> C2
  C1 --"Merged"--> C3
  C1 --"Continued"--> C4
  C2 --> E1
  C3 --> E1
  C4 --> E1

  %% Pilih Tipe OCR Table
  B5 --> D1
  D1 --"Normal"--> D2
  D1 --"Merged"--> D3
  D1 --"Continued"--> D4
  D2 --> E1
  D3 --> E1
  D4 --> E1

  %% Cleaning dan Output
  B2 --> E1
  B4 --> E1
  E1 --> E2

```



```mermaid
flowchart TB
  %% Step 1: Load PDF & Layout + Content Detection
  A1(["Start"])
  A2[/"Input: File PDF"/]
  A3["Load PDF"]
  A4["Extract Text"]
  A5["Detect Layout & Content"]
  A6{"Column Layout?"}
  A7["Single Column"]
  A8["Multi Column"]
  A9["Split Sections"]
  A10[/"Output: Metadata Layout & Content Type"/]

  %% Step 2: Deteksi Tabel atau OCR (Jika Diperlukan)
  B1{"Has Image Content?"}
  B2["OCR Processing"]
  B3{"OCR Result: Table or Text?"}
  B4["OCR Text"]
  B5["OCR Table"]
  
  %% Step 3: Deteksi Tabel (Untuk Semua Konten, Termasuk OCR & Teks Langsung)
  C1{"Has Table?"}
  C2["Detect Table Type"]
  C3{"Table Type?"}
  C4["Normal Table"]
  C5["Merged Table"]
  C6["Continued Table"]
  C7[/"Output: Updated Metadata with Table Type"/]

  %% Step 4: Extraction
  D1["Extract Data Based on Metadata"]


  %% Flow
  A1 --> A2
  A2 --> A3
  A3 --> A4
  A4 --> A5
  A5 --> A6
  A6 --"Yes"--> A7
  A6 --"No"--> A8
  A8 --> A9
  A7 --> A9
  A9 --> A10
  A10 --> B1
  B1 --"Yes"--> B2
  B1 --"No"--> C1
  B2 --> B3
  B3 --"Text"--> B4
  B3 --"Table"--> B5
  B4 --> C1
  B5 --> C1

  %% Deteksi Tabel Jika Ada
  C1 --"Yes"--> C2
  C1 --"No"--> D1
  C2 --> C3
  C3 --"Normal"--> C4
  C3 --"Merged"--> C5
  C3 --"Continued"--> C6
  C4 --> C7
  C5 --> C7
  C6 --> C7
  C7 --> D1

  %% Ekstraksi Data
  D1 --> D2


```


```mermaid
flowchart TB

  %% Step 1: Load & Layout Detection
  A1(["Start Processing"])
  A2[/"Input: File PDF"/]
  A3["Load PDF & Extract Raw Text"]
  A4{"Has Extractable Text?"}
  A5["Detect Layout (Single/Multi Column)"]
  A6["Perform OCR"]
  A7{"Single or Multi Column?"}
  A8["Split Sections"]
  A9["Split by Column"]
  A10[/"Output: Metadata Layout"/]

  %% Step 2: Content Detection
  B1["Detect Content Type per Section"]
  B2{"Content Type?"}
  B3["Mark as Text"]
  B4["Detect Table Type"]
  B5["Detect Image for OCR"]
  B6{"Table Type?"}
  B7["Mark as Normal Table"]
  B8["Mark as Merged Table"]
  B9["Mark as Continued Table"]

  %% Step 3: OCR Processing
  C1["Perform OCR on Image Sections"]
  C2{"OCR Result Type?"}
  C3["Mark as OCR Text"]
  C4["Mark as OCR Table"]
  C5{"OCR Table Type?"}
  C6["Mark as OCR Normal Table"]
  C7["Mark as OCR Merged Table"]
  C8["Mark as OCR Continued Table"]
  C9[/"Output: (Final Layout) + (Content Type) Metadata"/]

  %% Step 4: Extraction Processing
  D1(["Start Extraction"])
  D2[/"Input: Metadata Content Type"/]
  D3{"Extracting Content Type?"}
  D4["Extract Text"]
  D5["Extract Table"]
  D6["Extract OCR Text"]
  D7["Extract OCR Table"]
  
  %% Table Extraction
  E1{"Table Type?"}
  E2["Extract Normal Table"]
  E3["Extract Merged Table"]
  E4["Extract Continued Table"]

  %% OCR Table Extraction
  F1{"OCR Table Type?"}
  F2["Extract OCR Normal Table"]
  F3["Extract OCR Merged Table"]
  F4["Extract OCR Continued Table"]

  %% Step 5: Data Cleaning & Output
  G1["Data Cleaning & Formatting"]
  G2[/"Output: JSON, CSV, Database"/]
  G3(["Finish"])

  %% Step 1: Load & Layout Detection
  A1 --> A2
  A2 --> A3
  A3 --> A4
  A4 --"Yes"--> A5
  A4 --"No"--> A6
  A6 --> A5
  A5 --> A7
  A7 --"Single"--> A8
  A7 --"Multi"--> A9
  A9 --> A8
  A8 --> A10

  %% Step 2: Content Detection
  A10 --> B1
  B1 --> B2
  B2 --"Text"--> B3
  B2 --"Table"--> B4
  B2 --"Image"--> B5

  %% Step 3: Table & OCR Processing
  B4 --> B6
  B6 --"Normal"--> B7
  B6 --"Merged"--> B8
  B6 --"Continued"--> B9
  B5 --> C1
  C1 --> C2
  C2 --"Text"--> C3
  C2 --"Table"--> C4
  C4 --> C5
  C5 --"Normal"--> C6
  C5 --"Merged"--> C7
  C5 --"Continued"--> C8
  B3 --> C9
  B7 --> C9
  B8 --> C9
  B9 --> C9
  C3 --> C9
  C6 --> C9
  C7 --> C9
  C8 --> C9

  %% Step 4: Extraction Processing
  C9 --> D1
  D1 --> D2
  D2 --> D3
  D3 --"Text"--> D4
  D3 --"Table"--> D5
  D3 --"OCR Text"--> D6
  D3 --"OCR Table"--> D7

  %% Table Extraction
  D5 --> E1
  E1 --"Normal"--> E2
  E1 --"Merged"--> E3
  E1 --"Continued"--> E4
  E2 --> G1
  E3 --> G1
  E4 --> G1

  %% OCR Table Extraction
  D7 --> F1
  F1 --"Normal"--> F2
  F1 --"Merged"--> F3
  F1 --"Continued"--> F4
  F2 --> G1
  F3 --> G1
  F4 --> G1

  %% Step 5: Cleaning & Output
  D4 --> G1
  D6 --> G1
  G1 --> G2
  G2 --> G3
```

import PyPDF2
import pandas as pd
import re

def ekstrak_teks_dan_tabel(nama_file_pdf):
    """
    Mengekstrak teks dan tabel dari file PDF laporan keuangan.

    Args:
        nama_file_pdf (str): Nama file PDF yang akan diproses.

    Returns:
        tuple: Tuple berisi teks (str) dan list DataFrame pandas.
    """

    teks = ""
    tabel = []

    try:
        with open(nama_file_pdf, 'rb') as file:
            pembaca_pdf = PyPDF2.PdfReader(file)
            jumlah_halaman = len(pembaca_pdf.pages)

            for nomor_halaman in range(jumlah_halaman):
                halaman = pembaca_pdf.pages[nomor_halaman]
                teks += halaman.extract_text()

                # Ekstraksi tabel (perlu penyesuaian lebih lanjut)
                tabel_halaman = ekstrak_tabel_dari_teks(halaman.extract_text())
                if tabel_halaman:
                    tabel.extend(tabel_halaman)

    except FileNotFoundError:
        print(f"File {nama_file_pdf} tidak ditemukan.")
    except Exception as e:
        print(f"Terjadi kesalahan: {e}")

    return teks, tabel

def ekstrak_tabel_dari_teks(teks_halaman):
    """
    Mengekstrak tabel dari teks halaman PDF (perlu penyesuaian lebih lanjut).

    Args:
        teks_halaman (str): Teks dari satu halaman PDF.

    Returns:
        list: List DataFrame pandas yang ditemukan di halaman tersebut.
    """

    # Identifikasi baris tabel
    baris_tabel = re.findall(r"([\d.,]+\s{2,}.+)", teks_halaman)
    if not baris_tabel:
        return []

    # Identifikasi header tabel
    header_tabel = []
    baris_header = re.findall(r"([A-Za-z\s]+\s{2,}[A-Za-z\s]+)", teks_halaman)
    if baris_header:
        header_tabel = [judul.strip() for judul in baris_header[0].split('  ')]

    # Proses setiap baris tabel
    data_tabel = []
    for baris in baris_tabel:
        # Pisahkan nilai-nilai dalam baris menggunakan spasi ganda
        nilai = [nilai.strip() for nilai in baris.split('  ')]
        data_tabel.append(nilai)

    # Buat DataFrame pandas
    df = pd.DataFrame(data_tabel)

    # Tambahkan header jika ditemukan
    if header_tabel:
        df.columns = header_tabel

    return [df]

# Contoh penggunaan
nama_file = "studi_kasus/8_Tabel_N_Halaman_Merge_V1.pdf"
teks, tabel = ekstrak_teks_dan_tabel(nama_file)

print("Teks:")
print(teks)

print("\nTabel:")
for df in tabel:
    print(df)
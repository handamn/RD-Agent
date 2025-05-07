from Classify import Classify
from Extract import IntegratedPdfExtractor

if __name__ == "__main__":
    # Inisialisasi class
    analyzer = Classify(output_dir="database/classified_result")
    extractor = IntegratedPdfExtractor(temp_dir="temporary_dir", dpi=300)
    
    # List file PDF [name]
    pdf_files = [
        # ['ABF Indonesia Bond Index Fund'],
        # ['Avrist Ada Kas Mutiara'],
        # ['Avrist Ada Saham Blue Safir Kelas A'],
        # ['Avrist IDX30'],
        # ['Avrist Prime Bond Fund'],
        # ['Bahana Dana Likuid Kelas G'],
        # ['Bahana Likuid Plus'],
        # ['Bahana Likuid Syariah Kelas G'],
        # ['Bahana MES Syariah Fund Kelas G'],
        # ['Bahana Pendapatan Tetap Makara Prima kelas G'],
        # ['Bahana Primavera 99 Kelas G'],
        # ['Batavia Dana Kas Maxima'],
        # ['Batavia Dana Likuid'],
        # ['Batavia Dana Obligasi Ultima'],
        # ['Batavia Dana Saham'],
        # ['Batavia Dana Saham Syariah'],
        # ['Batavia Index PEFINDO I-Grade'],
        # ['Batavia Obligasi Platinum Plus'],
        # ['Batavia Technology Sharia Equity USD'],
        # ['BNI-AM Dana Lancar Syariah'],
        # ['BNI-AM Dana Likuid Kelas A'],
        # ['BNI-AM Dana Pendapatan Tetap Makara Investasi'],
        # ['BNI-AM Dana Pendapatan Tetap Syariah Ardhani'],
        # ['BNI-AM Dana Saham Inspiring Equity Fund'],
        # ['BNI-AM IDX PEFINDO Prime Bank Kelas R1'],
        # ['BNI-AM Indeks IDX30'],
        # ['BNI-AM ITB Harmoni'],
        # ['BNI-AM PEFINDO I-Grade Kelas R1'],
        # ['BNI-AM Short Duration Bonds Index Kelas R1'],
        # ['BNI-AM SRI KEHATI Kelas R1'],
        # ['BNP Paribas Cakra Syariah USD Kelas RK1'],
        # ['BNP Paribas Ekuitas'],
        # ['BNP Paribas Greater China Equity Syariah USD'],
        # ['BNP Paribas Infrastruktur Plus'],
        # ['BNP Paribas Pesona'],
        # ['BNP Paribas Pesona Syariah'],
        # ['BNP Paribas Prima II Kelas RK1'],
        # ['BNP Paribas Prima USD Kelas RK1'],
        # ['BNP Paribas Rupiah Plus'],
        # ['BNP Paribas Solaris'],
        # ['BNP Paribas SRI KEHATI'],
        # ['BNP Paribas Sukuk Negara Kelas RK1'],
        # ['BRI Indeks Syariah'],
        # ['BRI Mawar Konsumer 10 Kelas A'],
        # ['BRI Melati Pendapatan Utama'],
        # ['BRI MSCI Indonesia ESG Screened Kelas A'],
        # ['BRI Seruni Pasar Uang II Kelas A'],
        # ['BRI Seruni Pasar Uang III'],
        # ['BRI Seruni Pasar Uang Syariah'],
        # ['Danamas Pasti'],
        # ['Danamas Rupiah Plus'],
        # ['Danamas Stabil'],
        # ['Eastspring IDR Fixed Income Fund Kelas A'],
        # ['Eastspring IDX ESG Leaders Plus Kelas A'],
        # ['Eastspring Investments Cash Reserve Kelas A'],
        # ['Eastspring Investments Value Discovery Kelas A'],
        # ['Eastspring Investments Yield Discovery Kelas A'],
        # ['Eastspring Syariah Fixed Income Amanah Kelas A'],
        # ['Eastspring Syariah Greater China Equity USD Kelas A'],
        # ['Eastspring Syariah Money Market Khazanah Kelas A'],
        # ['Grow Dana Optima Kas Utama'],
        # ['Grow Obligasi Optima Dinamis Kelas O'],
        # ['Grow Saham Indonesia Plus Kelas O'],
        # ['Grow SRI KEHATI Kelas O'],
        # ['Jarvis Balanced Fund'],
        # ['Jarvis Money Market Fund'],
        # ['Majoris Pasar Uang Indonesia'],
        # ['Majoris Pasar Uang Syariah Indonesia'],
        # ['Majoris Saham Alokasi Dinamik Indonesia'],
        # ['Majoris Sukuk Negara Indonesia'],
        # ['Mandiri Indeks FTSE Indonesia ESG Kelas A'],
        # ['Mandiri Investa Atraktif-Syariah'],
        # ['Mandiri Investa Dana Syariah Kelas A'],
        # ['Mandiri Investa Dana Utama Kelas D'],
        # ['Mandiri Investa Pasar Uang Kelas A'],
        # ['Mandiri Investa Syariah Berimbang'],
        # ['Mandiri Pasar Uang Syariah Ekstra'],
        # ['Manulife Dana Kas II Kelas A'],
        # ['Manulife Dana Kas Syariah'],
        # ['Manulife Dana Saham Kelas A'],
        # ['Manulife Obligasi Negara Indonesia II Kelas A'],
        # ['Manulife Obligasi Unggulan Kelas A'],
        # ['Manulife Saham Andalan'],
        # ['Manulife Syariah Sektoral Amanah Kelas A'],
        # ['Manulife USD Fixed Income Kelas A'],
        # ['Principal Cash Fund'],
        # ['Principal Index IDX30 Kelas O'],
        # ['Principal Islamic Equity Growth Syariah'],
        # ['Schroder 90 Plus Equity Fund'],
        # ['Schroder Dana Andalan II'],
        # ['Schroder Dana Istimewa'],
        # ['Schroder Dana Likuid'],
        # ['Schroder Dana Likuid Syariah'],
        ['Schroder Dana Mantap Plus II'],
        ['Schroder Dana Prestasi'],
        ['Schroder Dana Prestasi Plus'],
        ['Schroder Dynamic Balanced Fund'],
        ['Schroder Global Sharia Equity Fund USD'],
        ['Schroder Syariah Balanced Fund'],
        ['Schroder USD Bond Fund Kelas A'], #################
        # ['Simas Saham Unggulan'],
        # ['Simas Satu'],
        # ['Simas Syariah Unggulan'],
        # ['Sucorinvest Bond Fund'],
        # ['Sucorinvest Citra Dana Berimbang'],
        # ['Sucorinvest Equity Fund'],
        # ['Sucorinvest Flexi Fund'],
        # ['Sucorinvest Money Market Fund'],
        # ['Sucorinvest Premium Fund'],
        # ['Sucorinvest Sharia Balanced Fund'],
        # ['Sucorinvest Sharia Equity Fund'],
        # ['Sucorinvest Sharia Money Market Fund'],
        # ['Sucorinvest Sharia Sukuk Fund'],
        # ['Sucorinvest Stable Fund'],
        # ['TRAM Consumption Plus Kelas A'],
        # ['TRAM Strategic Plus Kelas A'],
        # ['TRIM Dana Tetap 2 Kelas A'],
        # ['TRIM Kapital'],
        # ['TRIM Kapital Plus'],
        # ['TRIM Kas 2 Kelas A'],
        # ['TRIM Syariah Saham'],
        # ['Trimegah Dana Tetap Syariah Kelas A'],
        # ['Trimegah FTSE Indonesia Low Volatility Factor Index'],
        
        # ['Trimegah Kas Syariah'],
        
    ]

    print("\nMemulai proses bergantian antara Classify dan Extractor...\n")
    for pdf_name in pdf_files:
        pdf_name = pdf_name[0]
        pdf_path = f"database/prospectus/{pdf_name}.pdf"
        print(f"\n--- Memproses: {pdf_name} ---")

        # Jalankan Classify hanya untuk file ini
        try:
            analyze_result = analyzer.analyze([[pdf_name, pdf_path]])
            print(f"✓ Analisis selesai: {pdf_name}")
        except Exception as e:
            print(f"✗ Gagal analisis {pdf_name}: {e}")
            continue

        # Jalankan Extractor hanya untuk file ini
        try:
            extract_result = extractor.process_multiple_pdfs(
                [[pdf_name, pdf_path]],
                analysis_dir="database/classified_result",
                output_dir="database/extracted_result"
            )
            print(f"✓ Ekstraksi selesai: {pdf_name}")
        except Exception as e:
            print(f"✗ Gagal ekstraksi {pdf_name}: {e}")
from Classify import Classify
from Extract import IntegratedPdfExtractor
from Chunk import PDFChunkProcessor
from Chunk import Config as config_chunk

if __name__ == "__main__":

    # List file PDF [name]
    pdf_files = [
        # ['ABF Indonesia Bond Index Fund'],
    ]

    # Inisialisasi class
    analyzer = Classify(
        output_dir="database/classified_result"
        )
    
    extractor = IntegratedPdfExtractor(
        temp_dir="temporary_dir",
        dpi=300
        )
    
    processor = PDFChunkProcessor(
        input_names=pdf_files,
        continue_from_last=True,         # Lewati file yang sudah diproses
        max_tokens=config_chunk.DEFAULT_MAX_TOKENS,
        overlap_tokens=config_chunk.DEFAULT_OVERLAP_TOKENS,
        use_structured_output=True,      # Gunakan output terstruktur (JSON) dari Gemini
        verbose=True                     # Tampilkan log
    )
    
    

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
    
    processor.process()

    
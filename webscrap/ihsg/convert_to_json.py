import pandas as pd
import numpy as np
import json

kode = "IHSG"
# Baca file CSV
csv_file = f"database/{kode}.csv"  # Ganti dengan file Anda
df = pd.read_csv(csv_file)

# Bersihkan dan konversi data
for col in ["Open", "High", "Low", "Close", "Adj Close"]:
    df[col] = df[col].astype(str).str.replace(",", "").astype(float)

df["Volume"] = pd.to_numeric(
    df["Volume"].astype(str).str.replace(",", ""), errors="coerce"
).apply(lambda x: None if pd.isna(x) else int(x))

# Ubah format data menjadi list of dictionaries
historical_data = df.rename(columns={
    "Date": "date",
    "Open": "open",
    "High": "high",
    "Low": "low",
    "Close": "close",
    "Adj Close": "adj_close",
    "Volume": "volume"
}).replace({np.nan: None}).to_dict(orient="records")


# Buat struktur JSON
output_json = {
    "benchmark_name": kode,
    "historical_data": historical_data
}

# Simpan ke file JSON
json_file = f"database/{kode}.json"
with open(json_file, "w") as f:
    json.dump(output_json, f, indent=2)  # Tidak perlu `default=str`

print(f"File JSON telah disimpan sebagai {json_file}")

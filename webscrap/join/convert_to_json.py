import pandas as pd
import numpy as np
import json

kode = "ABF Indonesia Bond Index Fund"
# Baca file CSV
csv_file = f"database/{kode}.csv"  # Ganti dengan file Anda
df = pd.read_csv(csv_file)

# Bersihkan dan konversi data
for col in ["NAV", "AUM"]:
    df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", ""), errors="coerce")

df["AUM"] = df["AUM"].apply(lambda x: None if pd.isna(x) else x)

df = df.rename(columns={
    "tanggal": "date",
    "NAV": "nav",
    "AUM": "aum",
    "currency": "currency"
})

# Konversi ke format JSON
output_json = {
    "benchmark_name": "Investment Fund",
    "historical_data": df.replace({np.nan: None}).to_dict(orient="records")
}

# Simpan ke file JSON
json_file = f"database/{kode}.json"
with open(json_file, "w") as f:
    json.dump(output_json, f, indent=2)  # Tidak perlu `default=str`

print(f"File JSON telah disimpan sebagai {json_file}")

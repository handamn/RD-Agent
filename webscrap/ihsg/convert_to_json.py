import pandas as pd
import json
import numpy as np


kode = "IHSG"
# Baca file CSV
csv_file = f"database/{kode}.csv"  # Ganti dengan nama file yang sesuai
df = pd.read_csv(csv_file)

# Gantilah nilai "nan" pada kolom Volume dengan 0 dan hilangkan koma

df["Volume"] = pd.to_numeric(
    df["Volume"].astype(str).str.replace(",", "").replace("nan", np.nan), 
    errors="coerce"
).astype("Int64")

# Ubah format data menjadi list of dictionaries
historical_data = df.rename(columns={
    "Date": "date",
    "Open": "open",
    "High": "high",
    "Low": "low",
    "Close": "close",
    "Adj Close": "adj_close",
    "Volume": "volume"
}).to_dict(orient="records")

# Buat struktur JSON
output_json = {
    "benchmark_name": "IHSG",
    "historical_data": historical_data
}

# Simpan ke file JSON
json_file = f"database/{kode}.json"
with open(json_file, "w") as f:
    json.dump(output_json, f, indent=2)

print(f"File JSON telah disimpan sebagai {json_file}")

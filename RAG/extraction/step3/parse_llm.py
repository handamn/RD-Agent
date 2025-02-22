from google import genai
from google.genai import types

import requests

image_path = "https://goo.gle/instrument-img"
image = requests.get(image_path)

client = genai.Client(api_key="aaa")
response = client.models.generate_content(
    model="gemini-2.0-flash",
    contents=["What is this image?",
              types.Part.from_bytes(data=image.content, mime_type="image/jpeg")])

print(response.text)


import os
from dotenv import load_dotenv


LANGCHAIN_TRACING_V2 = os.getenv('GOOGLE_API_KEY')

load_dotenv()
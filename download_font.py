import urllib.request
import os

font_url = "https://github.com/google/fonts/raw/main/ofl/vt323/VT323-Regular.ttf"
dest = "assets/VT323-Regular.ttf"

if not os.path.exists("assets"):
    os.makedirs("assets")

try:
    print("Downloading pixel font...")
    urllib.request.urlretrieve(font_url, dest)
    print("Font downloaded successfully.")
except Exception as e:
    print(f"Error downloading font: {e}")

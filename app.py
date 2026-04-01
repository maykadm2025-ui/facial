from pathlib import Path

from flask import Flask, send_from_directory

app = Flask(__name__)
BASE_DIR = Path(__file__).resolve().parent

@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")

if __name__ == "__main__":
    app.run(debug=True)

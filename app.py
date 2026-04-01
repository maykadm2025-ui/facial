from flask import Flask, send_file

app = Flask(__name__)

# Configurações do Supabase (Para uso futuro no servidor)
SUPABASE_URL = "https://bpdcdqaangtkoiqppdwf.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJwZGNkcWFhbmd0a29pcXBwZHdmIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzUwNjc0NjksImV4cCI6MjA5MDY0MzQ2OX0.x8X7o2Zpc_7ZfInSVtMuJRzePyV5Ljkkmn2XaMNNEII"

@app.route('/')
def index():
    # Envia o index.html diretamente do diretório atual (raiz)
    return send_file('index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
from flask import Flask, render_template, request, jsonify
from supabase import create_client, Client

# O parâmetro template_folder='.' diz ao Flask para procurar o HTML na raiz (pasta atual)
app = Flask(__name__, template_folder='.')

# Configurações do Supabase
SUPABASE_URL = 'https://bpdcdqaangtkoiqppdwf.supabase.co'
SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJwZGNkcWFhbmd0a29pcXBwZHdmIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzUwNjc0NjksImV4cCI6MjA5MDY0MzQ2OX0.x8X7o2Zpc_7ZfInSVtMuJRzePyV5Ljkkmn2XaMNNEII'

# Inicializando o cliente do Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

@app.route('/')
def index():
    # Agora ele vai encontrar o index.html solto na mesma pasta do app.py
    return render_template('index.html')

@app.route('/api/cadastro', methods=['POST'])
def cadastro():
    dados = request.json
    
    try:
        # Inserindo os dados capturados na tabela 'cadastros' do Supabase
        resposta = supabase.table('cadastros').insert({
            'nome': dados.get('nome'),
            'turma': dados.get('turma'),
            'entrada': dados.get('entrada'),
            'status': dados.get('status'),
            'foto_base64': dados.get('foto'),
            'turno': dados.get('turno'),
        }).execute()
        
        return jsonify({'sucesso': True, 'dados': resposta.data}), 200
        
    except Exception as e:
        return jsonify({'sucesso': False, 'erro': str(e)}), 400

@app.route('/api/relatorio', methods=['GET'])
def relatorio():
    try:
        # Busca registros onde o status é diferente de 'Cadastrado'
        resposta = supabase.table('cadastros').select('*').neq('status', 'Cadastrado').execute()
        dados = resposta.data
        
        # Remove o 'descriptor' do dicionário no backend para garantir a regra e economizar tráfego de rede
        for aluno in dados:
            aluno.pop('descriptor', None)
            
        return jsonify({'sucesso': True, 'dados': dados}), 200
        
    except Exception as e:
        return jsonify({'sucesso': False, 'erro': str(e)}), 400

if __name__ == '__main__':
    app.run(debug=True, port=5000)
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request as UrlRequest, urlopen

from flask import Flask, jsonify, request, send_from_directory

app = Flask(__name__)
BASE_DIR = Path(__file__).resolve().parent

SUPABASE_URL = "https://bpdcdqaangtkoiqppdwf.supabase.co"
SUPABASE_KEY = "sb_publishable_8wPo5UwpL_e1rSwmodNWiA_c9P-klIx"
SUPABASE_BUCKET = "face"
SUPABASE_CADASTROS_PATH = "cadastros/alunos.json"


class SupabaseStorageError(RuntimeError):
    def __init__(self, message, status_code=502):
        super().__init__(message)
        self.status_code = status_code


def _supabase_headers(content_type=None):
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Accept": "application/json",
    }

    if content_type:
        headers["Content-Type"] = content_type

    return headers


def _supabase_object_url(path):
    encoded_path = quote(path, safe="/")
    return f"{SUPABASE_URL}/storage/v1/object/{SUPABASE_BUCKET}/{encoded_path}"


def _supabase_request(method, path, body=None, content_type=None):
    requisicao = UrlRequest(
        _supabase_object_url(path),
        data=body,
        headers=_supabase_headers(content_type),
        method=method,
    )

    try:
        with urlopen(requisicao, timeout=20) as resposta:
            return resposta.status, resposta.read()
    except HTTPError as erro:
        return erro.code, erro.read()
    except URLError as erro:
        raise ConnectionError(f"Falha ao conectar ao Supabase: {erro.reason}") from erro


def _extrair_erro_supabase(corpo):
    if not corpo:
        return "Erro desconhecido ao acessar o Supabase."

    try:
        dados = json.loads(corpo.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return corpo.decode("utf-8", errors="replace") or "Erro desconhecido ao acessar o Supabase."

    if isinstance(dados, dict):
        return (
            dados.get("message")
            or dados.get("error")
            or dados.get("msg")
            or "Erro desconhecido ao acessar o Supabase."
        )

    return "Erro desconhecido ao acessar o Supabase."


def _arquivo_nao_encontrado(status, corpo):
    if status == 404:
        return True

    if status != 400:
        return False

    return "not found" in _extrair_erro_supabase(corpo).lower()


def _salvar_cadastros_no_supabase(cadastros):
    corpo = json.dumps(cadastros, ensure_ascii=False).encode("utf-8")
    content_type = "application/json; charset=utf-8"

    status, resposta = _supabase_request("PUT", SUPABASE_CADASTROS_PATH, corpo, content_type)
    if status in (200, 201):
        return

    if status in (400, 404):
        status, resposta = _supabase_request("POST", SUPABASE_CADASTROS_PATH, corpo, content_type)
        if status in (200, 201):
            return

    codigo = status if 400 <= status < 500 else 502
    raise SupabaseStorageError(_extrair_erro_supabase(resposta), codigo)


@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")


@app.after_request
def adicionar_cors(resposta):
    if request.path.startswith("/api/"):
        resposta.headers["Access-Control-Allow-Origin"] = "*"
        resposta.headers["Access-Control-Allow-Headers"] = "Content-Type"
        resposta.headers["Access-Control-Allow-Methods"] = "GET, PUT, OPTIONS"

    return resposta


@app.route("/api/cadastros", methods=["OPTIONS"])
def opcoes_cadastros():
    return ("", 204)


@app.get("/api/cadastros")
def obter_cadastros():
    try:
        status, corpo = _supabase_request("GET", SUPABASE_CADASTROS_PATH)
    except ConnectionError as erro:
        return jsonify({"error": str(erro)}), 502

    if _arquivo_nao_encontrado(status, corpo):
        return jsonify([])

    if status != 200:
        codigo = status if 400 <= status < 500 else 502
        return jsonify({"error": _extrair_erro_supabase(corpo)}), codigo

    try:
        dados = json.loads(corpo.decode("utf-8")) if corpo else []
    except (UnicodeDecodeError, json.JSONDecodeError):
        return jsonify({"error": "O arquivo de cadastros do Supabase está inválido."}), 502

    return jsonify(dados if isinstance(dados, list) else [])


@app.put("/api/cadastros")
def salvar_cadastros():
    dados = request.get_json(silent=True)
    if not isinstance(dados, list):
        return jsonify({"error": "O corpo da requisição deve ser uma lista de alunos."}), 400

    try:
        _salvar_cadastros_no_supabase(dados)
    except ConnectionError as erro:
        return jsonify({"error": str(erro)}), 502
    except SupabaseStorageError as erro:
        return jsonify({"error": str(erro)}), erro.status_code

    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(debug=True)

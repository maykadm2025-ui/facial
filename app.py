import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request as UrlRequest, urlopen
from uuid import uuid4

from flask import Flask, Response, jsonify, request, send_from_directory

app = Flask(__name__)
BASE_DIR = Path(__file__).resolve().parent

SUPABASE_URL = "https://bpdcdqaangtkoiqppdwf.supabase.co"
SUPABASE_KEY = "sb_publishable_8wPo5UwpL_e1rSwmodNWiA_c9P-klIx"
SUPABASE_BUCKET = "face"
SUPABASE_CADASTROS_PATH = "cadastros/alunos.json"
SUPABASE_IMAGENS_DIR = "cadastros/imagens"


class SupabaseStorageError(RuntimeError):
    def __init__(self, message, status_code=502):
        super().__init__(message)
        self.status_code = status_code


def _supabase_headers(content_type=None, accept=None):
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Accept": accept or "application/json",
    }

    if content_type:
        headers["Content-Type"] = content_type

    return headers


def _storage_endpoint(endpoint):
    return f"{SUPABASE_URL}/storage/v1/{endpoint.lstrip('/')}"


def _objeto_endpoint(path):
    return f"object/{SUPABASE_BUCKET}/{quote(path, safe='/')}"


def _supabase_request(method, endpoint, body=None, content_type=None, accept=None):
    requisicao = UrlRequest(
        _storage_endpoint(endpoint),
        data=body,
        headers=_supabase_headers(content_type, accept),
        method=method,
    )

    try:
        with urlopen(requisicao, timeout=30) as resposta:
            return resposta.status, dict(resposta.headers.items()), resposta.read()
    except HTTPError as erro:
        return erro.code, dict(erro.headers.items()), erro.read()
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


def _carregar_cadastros_do_supabase():
    status, _, corpo = _supabase_request("GET", _objeto_endpoint(SUPABASE_CADASTROS_PATH))

    if _arquivo_nao_encontrado(status, corpo):
        return []

    if status != 200:
        codigo = status if 400 <= status < 500 else 502
        raise SupabaseStorageError(_extrair_erro_supabase(corpo), codigo)

    try:
        dados = json.loads(corpo.decode("utf-8")) if corpo else []
    except (UnicodeDecodeError, json.JSONDecodeError) as erro:
        raise SupabaseStorageError("O arquivo de cadastros do Supabase está inválido.", 502) from erro

    return dados if isinstance(dados, list) else []


def _salvar_json_no_supabase(path, dados):
    corpo = json.dumps(dados, ensure_ascii=False).encode("utf-8")
    content_type = "application/json; charset=utf-8"

    status, _, resposta = _supabase_request("PUT", _objeto_endpoint(path), corpo, content_type)
    if status in (200, 201):
        return

    if status in (400, 404):
        status, _, resposta = _supabase_request("POST", _objeto_endpoint(path), corpo, content_type)
        if status in (200, 201):
            return

    codigo = status if 400 <= status < 500 else 502
    raise SupabaseStorageError(_extrair_erro_supabase(resposta), codigo)


def _upload_imagem_no_supabase(path, conteudo, content_type):
    status, _, resposta = _supabase_request("POST", _objeto_endpoint(path), conteudo, content_type)
    if status in (200, 201):
        return

    codigo = status if 400 <= status < 500 else 502
    raise SupabaseStorageError(_extrair_erro_supabase(resposta), codigo)


def _deletar_objeto_do_supabase(path):
    status, _, corpo = _supabase_request("DELETE", _objeto_endpoint(path))
    if status in (200, 204) or _arquivo_nao_encontrado(status, corpo):
        return

    codigo = status if 400 <= status < 500 else 502
    raise SupabaseStorageError(_extrair_erro_supabase(corpo), codigo)


def _deletar_multiplos_objetos_do_supabase(paths):
    caminhos = [path for path in paths if path]
    if not caminhos:
        return

    corpo = json.dumps({"prefixes": caminhos}).encode("utf-8")
    status, _, resposta = _supabase_request(
        "DELETE",
        f"object/{SUPABASE_BUCKET}",
        corpo,
        "application/json; charset=utf-8",
    )

    if status in (200, 204):
        return

    codigo = status if 400 <= status < 500 else 502
    raise SupabaseStorageError(_extrair_erro_supabase(resposta), codigo)


def _extensao_por_content_type(content_type):
    mapa = {
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
    }
    return mapa.get(content_type, "jpg")


def _cadastro_publico(cadastro):
    return {
        "id": cadastro.get("id"),
        "nome": cadastro.get("nome", ""),
        "turno": cadastro.get("turno", "Manha"),
        "tem_foto": bool(cadastro.get("foto_path")),
        "criado_em": cadastro.get("criado_em"),
    }


def _buscar_cadastro_por_id(cadastro_id):
    cadastros = _carregar_cadastros_do_supabase()
    for cadastro in cadastros:
        if str(cadastro.get("id")) == cadastro_id:
            return cadastro

    return None


@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")


@app.after_request
def adicionar_cors(resposta):
    if request.path.startswith("/api/"):
        resposta.headers["Access-Control-Allow-Origin"] = "*"
        resposta.headers["Access-Control-Allow-Headers"] = "Content-Type"
        resposta.headers["Access-Control-Allow-Methods"] = "GET, POST, DELETE, OPTIONS"

    return resposta


@app.route("/api/cadastros", methods=["OPTIONS"])
@app.route("/api/cadastros/<cadastro_id>/foto", methods=["OPTIONS"])
def opcoes_api(cadastro_id=None):
    return ("", 204)


@app.get("/api/cadastros")
def obter_cadastros():
    try:
        cadastros = _carregar_cadastros_do_supabase()
    except ConnectionError as erro:
        return jsonify({"error": str(erro)}), 502
    except SupabaseStorageError as erro:
        return jsonify({"error": str(erro)}), erro.status_code

    return jsonify([_cadastro_publico(cadastro) for cadastro in cadastros])


@app.post("/api/cadastros")
def criar_cadastro():
    nome = (request.form.get("nome") or "").strip()
    turno = request.form.get("turno") or "Manha"
    foto = request.files.get("foto")

    if not nome:
        return jsonify({"error": "O nome do aluno é obrigatório."}), 400

    if turno not in {"Manha", "Noite"}:
        return jsonify({"error": "O turno informado é inválido."}), 400

    if foto is None or not foto.filename:
        return jsonify({"error": "A foto do aluno é obrigatória."}), 400

    content_type = (foto.mimetype or "image/jpeg").lower()
    if not content_type.startswith("image/"):
        return jsonify({"error": "O arquivo enviado precisa ser uma imagem."}), 400

    conteudo_foto = foto.read()
    if not conteudo_foto:
        return jsonify({"error": "A imagem enviada está vazia."}), 400

    try:
        cadastros = _carregar_cadastros_do_supabase()
    except ConnectionError as erro:
        return jsonify({"error": str(erro)}), 502
    except SupabaseStorageError as erro:
        return jsonify({"error": str(erro)}), erro.status_code

    if any(str(cadastro.get("nome", "")).strip().lower() == nome.lower() for cadastro in cadastros):
        return jsonify({"error": "Esse aluno já está cadastrado."}), 409

    cadastro_id = uuid4().hex
    extensao = _extensao_por_content_type(content_type)
    foto_path = f"{SUPABASE_IMAGENS_DIR}/{cadastro_id}.{extensao}"
    novo_cadastro = {
        "id": cadastro_id,
        "nome": nome,
        "turno": turno,
        "foto_path": foto_path,
        "foto_content_type": content_type,
        "criado_em": datetime.now(timezone.utc).isoformat(),
    }

    try:
        _upload_imagem_no_supabase(foto_path, conteudo_foto, content_type)
        _salvar_json_no_supabase(SUPABASE_CADASTROS_PATH, [*cadastros, novo_cadastro])
    except ConnectionError as erro:
        try:
            _deletar_objeto_do_supabase(foto_path)
        except Exception:
            pass
        return jsonify({"error": str(erro)}), 502
    except SupabaseStorageError as erro:
        try:
            _deletar_objeto_do_supabase(foto_path)
        except Exception:
            pass
        return jsonify({"error": str(erro)}), erro.status_code

    return jsonify(_cadastro_publico(novo_cadastro)), 201


@app.delete("/api/cadastros")
def apagar_cadastros():
    try:
        cadastros = _carregar_cadastros_do_supabase()
        imagens = [cadastro.get("foto_path") for cadastro in cadastros if cadastro.get("foto_path")]

        _deletar_multiplos_objetos_do_supabase(imagens)
        _deletar_objeto_do_supabase(SUPABASE_CADASTROS_PATH)
    except ConnectionError as erro:
        return jsonify({"error": str(erro)}), 502
    except SupabaseStorageError as erro:
        return jsonify({"error": str(erro)}), erro.status_code

    return jsonify({"ok": True})


@app.get("/api/cadastros/<cadastro_id>/foto")
def obter_foto_cadastro(cadastro_id):
    try:
        cadastro = _buscar_cadastro_por_id(cadastro_id)
    except ConnectionError as erro:
        return jsonify({"error": str(erro)}), 502
    except SupabaseStorageError as erro:
        return jsonify({"error": str(erro)}), erro.status_code

    if not cadastro or not cadastro.get("foto_path"):
        return jsonify({"error": "Foto não encontrada."}), 404

    try:
        status, headers, corpo = _supabase_request(
            "GET",
            _objeto_endpoint(cadastro["foto_path"]),
            accept="image/*,application/octet-stream",
        )
    except ConnectionError as erro:
        return jsonify({"error": str(erro)}), 502

    if _arquivo_nao_encontrado(status, corpo):
        return jsonify({"error": "Foto não encontrada."}), 404

    if status != 200:
        codigo = status if 400 <= status < 500 else 502
        return jsonify({"error": _extrair_erro_supabase(corpo)}), codigo

    content_type = headers.get("Content-Type") or cadastro.get("foto_content_type") or "image/jpeg"
    return Response(corpo, mimetype=content_type)


if __name__ == "__main__":
    app.run(debug=True)

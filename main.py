import re
from datetime import datetime, timedelta
import requests
from flask import Flask, jsonify, request
app = Flask(__name__)
BASE = "https://comunicaapi.pje.jus.br/api/v1"
def clean_process(value):
    return re.sub(r"[^0-9]", "", str(value or ""))
def normalize_date(value):
    if not value:
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%dT%H:%M:%S.%fZ"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return text[:10] if len(text) >= 10 else text
def extract_items(payload):
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    for key in ("items", "content", "comunicacoes", "results", "data", "comunicacao"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            if any(name in value for name in ("numeroProcesso", "numero_processo", "processo")):
                return [value]
            for nested_key in ("items", "content", "comunicacoes", "results", "data", "comunicacao"):
                nested = value.get(nested_key)
                if isinstance(nested, list):
                    return nested
                if isinstance(nested, dict) and any(name in nested for name in ("numeroProcesso", "numero_processo", "processo")):
                    return [nested]
    return []
def item_process(item):
    if not isinstance(item, dict):
        return ""
    return clean_process(
        item.get("numeroProcesso")
        or item.get("numero_processo")
        or item.get("processo")
        or item.get("numeroProcessoFormatado")
    )
@app.get("/")
def health():
    return jsonify({"ok": True, "service": "consulta-djen-ponte"})
@app.post("/")
def consultar():
    data = request.get_json(silent=True) or {}
    processo = clean_process(data.get("processo"))
    if not processo:
        return jsonify({"encontrada": False, "erro": "processo_obrigatorio"}), 400
    hoje = datetime.now().date()
    inicio = (hoje - timedelta(days=10)).strftime("%Y-%m-%d")
    fim = hoje.strftime("%Y-%m-%d")
    params = {
        "numeroProcesso": processo,
        "dataDisponibilizacaoInicio": inicio,
        "dataDisponibilizacaoFim": fim,
        "itensPorPagina": 50,
        "pagina": 1,
    }
    response = requests.get(f"{BASE}/comunicacao", params=params, timeout=30)
    if response.status_code >= 400:
        return jsonify({
            "encontrada": False,
            "processo": processo,
            "data_inicio": inicio,
            "data_fim": fim,
            "erro": f"api_http_{response.status_code}",
            "detalhe": response.text[:500],
        }), 502
    payload = response.json()
    items = extract_items(payload)
    item = next((entry for entry in items if item_process(entry) == processo), None)
    if item is None and len(items) == 1:
        item = items[0]
    if item is None:
        return jsonify({
            "encontrada": False,
            "processo": processo,
            "data_inicio": inicio,
            "data_fim": fim,
            "count": payload.get("count", len(items)) if isinstance(payload, dict) else len(items),
        })
    result = dict(item)
    result["encontrada"] = True
    result["processo"] = processo
    result["data_inicio"] = inicio
    result["data_fim"] = fim
    result["teor_integral"] = (
        item.get("teor") or item.get("texto") or item.get("conteudo")
        or item.get("descricao") or item.get("mensagem")
    )
    certidao = item.get("certidaoUrl") or item.get("certidao_url") or item.get("url")
    if certidao:
        result["certidao_url"] = certidao
    return jsonify(result)

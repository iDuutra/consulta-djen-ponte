import re
from datetime import datetime

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


@app.get("/")
def health():
    return jsonify({"ok": True, "service": "consulta-djen-ponte"})


@app.post("/")
def consultar():
    data = request.get_json(silent=True) or {}
    processo = clean_process(data.get("processo"))
    inicio = normalize_date(data.get("data_inicio") or data.get("data"))
    fim = normalize_date(data.get("data_fim") or inicio)
    if not processo:
        return jsonify({"encontrada": False, "erro": "processo_obrigatorio"}), 400
    params = {
        "numeroProcesso": processo,
        "dataDisponibilizacaoInicio": inicio,
        "dataDisponibilizacaoFim": fim,
        "itensPorPagina": 50,
        "pagina": 1,
    }
    try:
        r = requests.get(BASE + "/comunicacao", params=params, headers={"Accept": "application/json"}, timeout=25)
        r.raise_for_status()
        payload = r.json()
    except requests.exceptions.RequestException as exc:
        return jsonify({"encontrada": False, "processo": processo, "erro": "djen_indisponivel", "detalhe": str(exc)}), 502
    except ValueError as exc:
        return jsonify({"encontrada": False, "processo": processo, "erro": "resposta_djen_invalida", "detalhe": str(exc)}), 502

    items = payload.get("items", payload if isinstance(payload, list) else [])
    item = next((x for x in items if clean_process(x.get("numeroProcesso")) == processo), None)
    if not item:
        return jsonify({"encontrada": False, "processo": processo, "count": payload.get("count", 0) if isinstance(payload, dict) else 0})

    result = dict(item)
    result["encontrada"] = True
    result["processo"] = processo
    result["teor_integral"] = item.get("texto") or item.get("teor") or item.get("conteudo")
    hash_value = item.get("hash") or item.get("id")
    if hash_value:
        cert_url = BASE + "/comunicacao/" + str(hash_value) + "/certidao"
        try:
            cert = requests.get(cert_url, headers={"Accept": "application/json"}, timeout=25)
            if cert.ok:
                result["certidao_url"] = cert_url
                if not result.get("teor_integral"):
                    result["teor_integral"] = cert.text
        except requests.exceptions.RequestException:
            pass
    return jsonify(result)

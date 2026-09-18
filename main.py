import re
import requests
from flask import jsonify, Request

BASE = "https://comunicaapi.pje.jus.br/api/v1"

def clean_process(value):
    return re.sub(r"[^0-9]", "", str(value or ""))

def main(request: Request):
    data = request.get_json(silent=True) or {}
    processo = clean_process(data.get("processo"))
    inicio = data.get("data_inicio") or data.get("data")
    fim = data.get("data_fim") or inicio
    if not processo:
        return jsonify({"encontrada": False, "erro": "processo_obrigatorio"}), 400
    params = {"numeroProcesso": processo, "dataDisponibilizacaoInicio": inicio, "dataDisponibilizacaoFim": fim, "itensPorPagina": 50, "pagina": 1}
    r = requests.get(BASE + "/comunicacao", params=params, headers={"Accept":"application/json"}, timeout=25)
    r.raise_for_status()
    payload = r.json()
    items = payload.get("items", payload if isinstance(payload, list) else [])
    item = next((x for x in items if clean_process(x.get("numeroProcesso")) == processo), None)
    if not item:
        return jsonify({"encontrada": False, "processo": processo, "count": payload.get("count", 0)})
    result = dict(item)
    result["encontrada"] = True
    result["processo"] = processo
    result["teor_integral"] = item.get("texto") or item.get("teor") or item.get("conteudo")
    hash_value = item.get("hash") or item.get("id")
    if hash_value:
        cert = requests.get(BASE + "/comunicacao/" + str(hash_value) + "/certidao", headers={"Accept":"application/json"}, timeout=25)
        if cert.ok:
            result["certidao_url"] = BASE + "/comunicacao/" + str(hash_value) + "/certidao"
            if not result.get("teor_integral"):
                result["teor_integral"] = cert.text
    return jsonify(result)


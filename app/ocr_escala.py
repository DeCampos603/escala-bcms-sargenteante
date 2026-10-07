# -*- coding: utf-8 -*-
"""Módulo de Inteligência Artificial e Visão Computacional - EscalaPro BCMS.

Reconhecimento automatizado de fotos de escalas de serviço impressas
e anotações a caneta (trocas) via Gemini Vision Multimodal.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from PIL import Image

from app.db import get_db_connection

# Carrega variáveis de ambiente (.env na raiz do REPO)
ROOT_REPO = Path(__file__).resolve().parent.parent.parent
ENV_PATH = ROOT_REPO / ".env"
if ENV_PATH.exists():
    load_dotenv(str(ENV_PATH))
else:
    load_dotenv()


def normalizar_nome_guerra(texto: str) -> str:
    """Remove postos/graduações e caracteres espúrios para matching."""
    if not texto:
        return ""
    limpo = re.sub(r"^(3[º°]?\s*Sgt|2[º°]?\s*Sgt|1[º°]?\s*Sgt|Subten|Asp|2[º°]?\s*Ten|1[º°]?\s*Ten|Cap)\s*", "", texto, flags=re.IGNORECASE)
    limpo = limpo.replace("\n", " ").replace("\r", " ").strip()
    return limpo.upper()


def analisar_foto_escala(imagem_file_or_bytes: Any) -> dict[str, Any]:
    """Analisa a foto da escala de serviço militar usando Gemini Vision.

    Extrai semana, dias, militares impressos e anotações a caneta.
    """
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY não configurada no arquivo .env. Configure a chave para habilitar a visão de IA."
        )

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        raise ImportError("Biblioteca google-genai não instalada. Execute: pip install google-genai")

    import io

    # Carrega imagem via PIL suportando str, Path, bytes ou file-like
    if isinstance(imagem_file_or_bytes, (str, Path)):
        img = Image.open(imagem_file_or_bytes)
    elif isinstance(imagem_file_or_bytes, bytes):
        img = Image.open(io.BytesIO(imagem_file_or_bytes))
    elif hasattr(imagem_file_or_bytes, "read"):
        conteudo = imagem_file_or_bytes.read()
        if isinstance(conteudo, bytes):
            img = Image.open(io.BytesIO(conteudo))
        else:
            img = Image.open(imagem_file_or_bytes)
    else:
        img = Image.open(imagem_file_or_bytes)

    client = genai.Client(api_key=api_key)

    prompt = """Você é um especialista em análise de escalas de serviço militar do Exército Brasileiro (BCMS).
Analise com extrema atenção a fotografia desta escala de serviço impressa.

INSTRUÇÕES OBRIGATÓRIAS:
1. Identifique o número da semana no topo (ex: '37 - PREVISÃO DA ESCALA DE SERVIÇO DE 10 a 16 DE SETEMBRO DE 2026' -> semana 37).
2. Identifique o ano e período de datas.
3. Para cada um dos 7 dias da escala (de Quinta a Quarta-feira):
   - Extraia a linha do posto 'SGT DE DIA' (3º Sargentos).
   - Identifique a data (YYYY-MM-DD), o dia da semana (QUI, SEX, SAB, DOM, SEG, TER, QUA).
   - Identifique se o dia é 'PRETA' (expediente normal) ou 'VERMELHA' (sábado, domingo ou coluna sombreada/feriado).
   - Identifique o militar que está impresso originalmente no papel (ex: '3º Sgt DIEGO LIMA' -> 'DIEGO LIMA').
   - ATENÇÃO REDOBRADA PARA TROCAS A CANETA: se houver nome riscado à mão e outro nome manuscrito a caneta na célula, indique o nome original impresso em 'militar_impresso' e o militar manuscrito a caneta em 'militar_caneta'.
   - Se não houver rasura a caneta, 'militar_caneta' deve ser null.

Retorne EXCLUSIVAMENTE um JSON válido com o seguinte formato:
{
  "semana_ano": 37,
  "periodo": "10 a 16 de setembro de 2026",
  "data_inicio": "2026-09-10",
  "data_fim": "2026-09-16",
  "dias": [
    {
      "data": "2026-09-10",
      "dia_semana": "QUI",
      "tipo_escala": "PRETA",
      "posto_codigo": "SGT_DE_DIA",
      "militar_impresso": "DIEGO LIMA",
      "militar_caneta": "ANDRESSA",
      "troca_detectada": true,
      "motivo": "Troca a caneta detectada na escala física"
    }
  ]
}"""

    # Modelos recomendados em ordem de preferência
    modelos = ["gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-3.1-flash-lite"]
    last_error = None

    for model_name in modelos:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=[img, prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1,
                ),
            )
            raw_text = response.text.strip()
            # Limpeza caso venha envolvido em markdown ```json ... ```
            if raw_text.startswith("```"):
                raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
                raw_text = re.sub(r"\s*```$", "", raw_text)

            resultado = json.loads(raw_text)

            # Se veio uma lista, pega o primeiro elemento
            if isinstance(resultado, list) and len(resultado) > 0:
                resultado = resultado[0]

            # Pós-processamento e normalização dos nomes com a base SQLite
            return _vincular_com_banco_dados(resultado)
        except Exception as e:
            last_error = e
            continue

    raise RuntimeError(f"Falha ao processar imagem da escala via IA: {last_error}")


def _vincular_com_banco_dados(dados_extraidos: dict[str, Any]) -> dict[str, Any]:
    """Cruza os nomes detectados pelo OCR com os militares cadastrados no SQLite."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, posto_graduacao, nome_guerra FROM militares WHERE ativo = 1")
        militares_banco = [dict(r) for r in cursor.fetchall()]

    mapa_nomes = {m["nome_guerra"].upper(): m for m in militares_banco}

    dias_processados = []
    for d in dados_extraidos.get("dias", []):
        nome_imp_norm = normalizar_nome_guerra(d.get("militar_impresso", ""))
        nome_can_norm = normalizar_nome_guerra(d.get("militar_caneta", ""))

        militar_imp = mapa_nomes.get(nome_imp_norm)
        militar_can = mapa_nomes.get(nome_can_norm) if nome_can_norm else None

        dias_processados.append({
            "data": d.get("data"),
            "dia_semana": d.get("dia_semana"),
            "tipo_escala": d.get("tipo_escala", "PRETA"),
            "posto_codigo": d.get("posto_codigo", "SGT_DE_DIA"),
            "militar_impresso_raw": d.get("militar_impresso"),
            "militar_impresso_id": militar_imp["id"] if militar_imp else None,
            "militar_impresso_nome": militar_imp["nome_guerra"] if militar_imp else nome_imp_norm,
            "militar_impresso_encontrado": militar_imp is not None,
            "militar_caneta_raw": d.get("militar_caneta"),
            "militar_caneta_id": militar_can["id"] if militar_can else None,
            "militar_caneta_nome": militar_can["nome_guerra"] if militar_can else (nome_can_norm or None),
            "militar_caneta_encontrado": militar_can is not None if nome_can_norm else True,
            "troca_detectada": bool(d.get("troca_detectada") or nome_can_norm),
            "motivo": d.get("motivo"),
        })

    dados_extraidos["dias"] = dias_processados
    return dados_extraidos

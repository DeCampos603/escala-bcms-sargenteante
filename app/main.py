# -*- coding: utf-8 -*-
"""Servidor FastAPI e API REST do EscalaPro BCMS.

Execução local com entrega do Frontend Moderno em HTML5/CSS Vanilla.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, Query, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# Adiciona o diretório raiz ao sys.path para imports absolutos
PROJETO_DIR = Path(__file__).resolve().parent.parent
if str(PROJETO_DIR) not in sys.path:
    sys.path.insert(0, str(PROJETO_DIR))

from app.db import init_db
from app.ocr_escala import analisar_foto_escala
from app.regras import calcular_folgas_militares, gerar_previsao_semana
from app.relatorios import gerar_excel_escala_semanal, gerar_png_escala_semanal
from app.servicos import (
    adicionar_afastamento,
    adicionar_militar,
    alterar_tipo_escala_dia,
    excluir_militar,
    importar_escala_foto,
    listar_afastamentos,
    listar_extrato_permutas,
    listar_semanas_disponiveis,
    obter_escala_semana,
    obter_estatisticas_dashboard,
    registrar_troca_caneta,
    remover_troca_caneta,
    reordenar_antiguidade_militares,
    salvar_previsao_semana,
)

# Inicializa banco de dados e carga inicial se necessário
init_db()

app = FastAPI(
    title="EscalaPro BCMS",
    description="Sistema Local de Previsão e Controle de Escalas de Serviço Militar - BCMS",
    version="1.0.0",
)

# Middleware de Segurança e CORS Local
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Schemas Pydantic ---
class TrocaRequest(BaseModel):
    escala_dia_id: int = Field(..., description="ID do dia na escala")
    militar_substituto_id: int = Field(..., description="ID do militar que assume a caneta")
    motivo: str = Field(..., description="Motivo ou número da autorização de troca")
    autorizado_por: str = Field("Fiscal de Dia", description="Autoridade que autorizou")


class PrevisaoRequest(BaseModel):
    semana_ano: int = Field(..., description="Número da semana no ano (ex: 42)")
    data_inicio_quinta: str = Field(..., description="Data de início da semana militar (Quinta-feira, YYYY-MM-DD)")
    posto_codigo: str = Field("SGT_DE_DIA", description="Código do posto de serviço")
    qtd_semanas: int = Field(1, description="Quantidade de semanas para prever (1 ou 2)")
    custom_tipos_dias: dict[str, str] | None = Field(None, description="Overrides manuais de tipo de escala {'YYYY-MM-DD': 'PRETA'|'VERMELHA'}")


class AlterarTipoDiaRequest(BaseModel):
    tipo_escala: str = Field(..., description="Novo tipo: PRETA ou VERMELHA")


class SalvarPrevisaoRequest(BaseModel):
    previsao: list[dict[str, Any]] = Field(..., description="Lista de dias previstos gerada pelo motor")


class NovoMilitarRequest(BaseModel):
    posto_graduacao: str = Field("3º Sgt", description="Posto ou Graduação")
    nome_guerra: str = Field(..., description="Nome de Guerra")
    antiguidade_ordem: int = Field(999, description="Ordem de antiguidade")
    escala_habilitada: str = Field("SGT_DE_DIA", description="Escala")
    subunidade: str = Field("BCMS", description="Companhia / Subunidade")


class ReordenarAntiguidadeRequest(BaseModel):
    ordem_ids: list[int] = Field(..., description="Lista ordenada de IDs dos militares do 1º ao último")


class NovoAfastamentoRequest(BaseModel):
    militar_id: int = Field(..., description="ID do militar")
    data_inicio: str = Field(..., description="Data início YYYY-MM-DD")
    data_fim: str = Field(..., description="Data fim YYYY-MM-DD")
    motivo: str = Field(..., description="FÉRIAS, DISPENSA, LTS, MISSÃO")
    observacao: str | None = None


class ConfirmarFotoRequest(BaseModel):
    semana_ano: int = Field(..., description="Número da semana da escala")
    dias: list[dict[str, Any]] = Field(..., description="Lista dos 7 dias com titular impresso e trocas a caneta")


# --- Endpoints da API REST ---

@app.get("/api/dashboard")
def get_dashboard(data_ref: str = "2026-10-05"):
    """Retorna métricas consolidadas do dashboard executivo."""
    return obter_estatisticas_dashboard(data_ref_str=data_ref)


@app.get("/api/semanas")
def get_semanas():
    """Retorna as semanas de serviço já cadastradas no sistema."""
    return listar_semanas_disponiveis()


@app.get("/api/escala/{semana_ano}")
def get_escala_semana(semana_ano: int, posto_codigo: str = "SGT_DE_DIA"):
    """Retorna o espelho semanal detalhado com todos os 7 dias e trocas."""
    dados = obter_escala_semana(semana_ano=semana_ano, posto_codigo=posto_codigo)
    if not dados.get("dias"):
        raise HTTPException(status_code=404, detail=f"Semana {semana_ano} não encontrada.")
    return dados


@app.post("/api/previsao/calcular")
def calcular_previsao(payload: PrevisaoRequest):
    """Calcula a previsão automática com até 2 semanas respeitando tempo de folga, interstício e escolhas do sargenteante."""
    previsao = gerar_previsao_semana(
        semana_ano=payload.semana_ano,
        data_inicio_quinta_str=payload.data_inicio_quinta,
        posto_codigo=payload.posto_codigo,
        qtd_semanas=payload.qtd_semanas,
        custom_tipos_dias=payload.custom_tipos_dias,
    )
    return {"semana_ano": payload.semana_ano, "qtd_semanas": payload.qtd_semanas, "previsao": previsao}


@app.post("/api/previsao/salvar")
def salvar_previsao(payload: SalvarPrevisaoRequest):
    """Grava permanentemente a previsão gerada no banco de dados."""
    salvos = salvar_previsao_semana(payload.previsao)
    return {"sucesso": True, "dias_salvos": salvos}


@app.post("/api/trocas")
def registrar_troca(payload: TrocaRequest):
    """Registra uma permuta a caneta sem alterar a folga oficial do substituto."""
    try:
        resultado = registrar_troca_caneta(
            escala_dia_id=payload.escala_dia_id,
            militar_substituto_id=payload.militar_substituto_id,
            motivo=payload.motivo,
            autorizado_por=payload.autorizado_por,
        )
        return resultado
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/trocas/{escala_dia_id}")
def desfazer_troca(escala_dia_id: int):
    """Cancela uma troca a caneta e retorna ao militar oficial da escala."""
    sucesso = remover_troca_caneta(escala_dia_id)
    return {"sucesso": sucesso}


@app.get("/api/permutas")
def get_permutas():
    """Retorna o extrato de todas as permutas/trocas realizadas no período."""
    return listar_extrato_permutas()


@app.get("/api/militares")
def get_militares(data_ref: str = "2026-10-05", posto_codigo: str = "SGT_DE_DIA"):
    """Lista todos os militares com os dias de folga calculados até a data de referência."""
    return calcular_folgas_militares(data_referencia_str=data_ref, posto_codigo=posto_codigo)


@app.post("/api/militares")
def post_militar(payload: NovoMilitarRequest):
    """Cadastra um novo militar no efetivo."""
    m_id = adicionar_militar(
        posto_graduacao=payload.posto_graduacao,
        nome_guerra=payload.nome_guerra,
        antiguidade_ordem=payload.antiguidade_ordem,
        escala_habilitada=payload.escala_habilitada,
        subunidade=payload.subunidade,
    )
    return {"sucesso": True, "id": m_id}


@app.post("/api/militares/reordenar-antiguidade")
def post_reordenar_antiguidade(payload: ReordenarAntiguidadeRequest):
    """Reordena a precedência hierárquica (antiguidade) dos militares via drag-and-drop."""
    try:
        return reordenar_antiguidade_militares(payload.ordem_ids)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/afastamentos")
def get_afastamentos():
    """Lista todos os afastamentos vigentes e programados."""
    return listar_afastamentos()


@app.post("/api/afastamentos")
def post_afastamento(payload: NovoAfastamentoRequest):
    """Registra afastamento (férias, dispensa médica, missão)."""
    a_id = adicionar_afastamento(
        militar_id=payload.militar_id,
        data_inicio=payload.data_inicio,
        data_fim=payload.data_fim,
        motivo=payload.motivo,
        observacao=payload.observacao,
    )
    return {"sucesso": True, "id": a_id}


@app.get("/api/exportar/excel/{semana_ano}")
def exportar_excel(semana_ano: int, posto_codigo: str = "SGT_DE_DIA"):
    """Exporta o espelho semanal e extrato de permutas em arquivo Excel (.xlsx)."""
    excel_stream = gerar_excel_escala_semanal(semana_ano=semana_ano, posto_codigo=posto_codigo)
    filename = f"Escala_BCMS_Semana_{semana_ano}.xlsx"
    return StreamingResponse(
        excel_stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.get("/api/exportar/png/{semana_ano}")
def exportar_png(semana_ano: int, posto_codigo: str = "SGT_DE_DIA"):
    """Exporta a previsão da escala em imagem PNG de alta resolução visual (1600x900)."""
    try:
        png_stream = gerar_png_escala_semanal(semana_ano=semana_ano, posto_codigo=posto_codigo)
        filename = f"Previsao_Escala_BCMS_Semana_{semana_ano}.png"
        return StreamingResponse(
            png_stream,
            media_type="image/png",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar imagem PNG: {str(e)}")


@app.post("/api/reconhecer-foto-escala")
async def reconhecer_foto(arquivo: UploadFile = File(...)):
    """Processa a foto da folha física de escala via IA Multimodal (Gemini Vision).

    Identifica semana, período, militares impressos titulares e anotações/riscados a caneta.
    """
    try:
        conteudo = await arquivo.read()
        if not conteudo:
            raise HTTPException(status_code=400, detail="Arquivo vazio.")
        resultado = analisar_foto_escala(conteudo)
        return resultado
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/confirmar-importacao-foto")
def confirmar_foto(payload: ConfirmarFotoRequest):
    """Grava permanentemente a escala reconhecida da foto no banco de dados.

    Atualiza as folgas de todo o efetivo (baseando o histórico no militar impresso)
    e registra as trocas a caneta na auditoria oficial de permutas.
    """
    try:
        resultado = importar_escala_foto(semana_ano=payload.semana_ano, dias=payload.dias)
        return resultado
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@app.patch("/api/escala/dia/{escala_dia_id}/tipo")
def patch_tipo_escala_dia(escala_dia_id: int, payload: AlterarTipoDiaRequest):
    """Altera se o dia na escala será PRETA ou VERMELHA."""
    try:
        return alterar_tipo_escala_dia(escala_dia_id, payload.tipo_escala)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/militares/{militar_id}")
def delete_militar(militar_id: int):
    """Exclui ou desativa um militar do efetivo da sargenteação."""
    try:
        return excluir_militar(militar_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# --- Servir Frontend Estático ---
STATIC_DIR = PROJETO_DIR / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/")
def read_index():
    """Entrega a aplicação Web principal do BCMS na raiz."""
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"mensagem": "EscalaPro BCMS API ativa."}

@app.get("/sargenteante")
def read_sargenteante():
    """Entrega o portal operacional paralelo para apresentação e uso pelo Sargenteante."""
    sarg_path = STATIC_DIR / "sargenteante.html"
    if sarg_path.exists():
        return FileResponse(str(sarg_path))
    return FileResponse(str(STATIC_DIR / "index.html"))

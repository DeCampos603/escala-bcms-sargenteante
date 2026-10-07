# -*- coding: utf-8 -*-
"""Testes Automatizados de Regras de Negócio e API - EscalaPro BCMS.

Execução:
    py -3 -m pytest tests -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

PROJETO_DIR = Path(__file__).resolve().parent.parent
if str(PROJETO_DIR) not in sys.path:
    sys.path.insert(0, str(PROJETO_DIR))

from app.db import get_db_connection, init_db
from app.main import app
from app.regras import (
    calcular_folgas_militares,
    gerar_previsao_semana,
    obter_tipo_dia,
    verificar_intersticio_valido,
)
from app.servicos import (
    listar_extrato_permutas,
    listar_semanas_disponiveis,
    obter_escala_semana,
    registrar_troca_caneta,
    remover_troca_caneta,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_banco():
    """Garante que o banco de dados e os dados de teste estejam inicializados."""
    init_db()
    with get_db_connection() as conn:
        conn.execute("DELETE FROM escalas_dias WHERE semana_ano > 42")
        conn.execute("DELETE FROM permutas_trocas WHERE escala_dia_id NOT IN (SELECT id FROM escalas_dias)")
        conn.commit()



def test_obter_tipo_dia():
    """Valida a separação entre Escala Preta (úteis) e Vermelha (sáb, dom, feriados)."""
    # Dia normal (Quinta-feira 10/09/2026)
    tipo, dia_sem, feriado = obter_tipo_dia("2026-09-10")
    assert tipo == "PRETA"
    assert dia_sem == "QUI"
    assert feriado is None

    # Sábado (12/09/2026)
    tipo, dia_sem, feriado = obter_tipo_dia("2026-09-12")
    assert tipo == "VERMELHA"
    assert dia_sem == "SAB"

    # Domingo (13/09/2026)
    tipo, dia_sem, feriado = obter_tipo_dia("2026-09-13")
    assert tipo == "VERMELHA"
    assert dia_sem == "DOM"

    # Segunda-feira com Feriado Nacional (12/10/2026 - N. Sra. Aparecida)
    tipo, dia_sem, feriado = obter_tipo_dia("2026-10-12")
    assert tipo == "VERMELHA"
    assert dia_sem == "SEG"
    assert "Aparecida" in str(feriado)


def test_carga_inicial_e_semanas():
    """Verifica se as semanas históricas 37 a 42 foram carregadas com precisão."""
    semanas = listar_semanas_disponiveis()
    assert len(semanas) >= 6
    semanas_nums = [s["semana_ano"] for s in semanas]
    assert 37 in semanas_nums
    assert 41 in semanas_nums
    assert 42 in semanas_nums


def test_escala_semana_37_com_troca():
    """Verifica se a semana 37 contém os militares impressos e a troca a caneta de Diego Lima/Andressa."""
    dados = obter_escala_semana(37)
    assert len(dados["dias"]) == 7

    dia_qui = dados["dias"][0]
    assert dia_qui["data"] == "2026-09-10"
    assert dia_qui["impresso_nome"] == "DIEGO LIMA"
    assert dia_qui["caneta_nome"] == "ANDRESSA"
    assert dia_qui["tipo_escala"] == "PRETA"


def test_escala_semana_41_com_trocas_oficiais():
    """Verifica se a semana 41 reflete exatamente a foto física oficial:
    - 10/10 (SAB): BARAUNA impresso, ANDRESSA caneta
    - 11/10 (DOM): SOUSA MOURA impresso, DE CAMPOS caneta
    - 14/10 (QUA): SOUSA MOURA impresso, sem troca
    """
    dados = obter_escala_semana(41)
    assert len(dados["dias"]) == 7

    dia_sab = next(d for d in dados["dias"] if d["data"] == "2026-10-10")
    assert dia_sab["impresso_nome"] == "BARAUNA"
    assert dia_sab["caneta_nome"] == "ANDRESSA"

    dia_dom = next(d for d in dados["dias"] if d["data"] == "2026-10-11")
    assert dia_dom["impresso_nome"] == "SOUSA MOURA"
    assert dia_dom["caneta_nome"] == "DE CAMPOS"

    dia_qua = next(d for d in dados["dias"] if d["data"] == "2026-10-14")
    assert dia_qua["impresso_nome"] == "SOUSA MOURA"
    assert dia_qua["caneta_nome"] is None


def test_escala_semana_42_e_novos_militares():
    """Verifica se a semana 42 contém a nova escala oficial da foto física:
    - 15/10 (QUI): SCHWEGER (PRETA)
    - 16/10 (SEX): BARAUNA (PRETA)
    - 17/10 (SAB): VIANA (VERMELHA)
    - 18/10 (DOM): SCHWEGER (VERMELHA)
    - 19/10 (SEG): VITOR SOARES (PRETA)
    - 20/10 (TER): DIEGO LIMA (PRETA)
    - 21/10 (QUA): PONCIANO (PRETA)
    E verifica se SCHWEGER e PONCIANO estão presentes no efetivo de militares.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT nome_guerra FROM militares WHERE nome_guerra IN ('SCHWEGER', 'PONCIANO')")
        nomes = [r[0] for r in cursor.fetchall()]
        assert "SCHWEGER" in nomes
        assert "PONCIANO" in nomes

    dados = obter_escala_semana(42)
    assert len(dados["dias"]) == 7

    escalados_esperados = [
        ("2026-10-15", "QUI", "PRETA", "SCHWEGER"),
        ("2026-10-16", "SEX", "PRETA", "BARAUNA"),
        ("2026-10-17", "SAB", "VERMELHA", "VIANA"),
        ("2026-10-18", "DOM", "VERMELHA", "SCHWEGER"),
        ("2026-10-19", "SEG", "PRETA", "VITOR SOARES"),
        ("2026-10-20", "TER", "PRETA", "DIEGO LIMA"),
        ("2026-10-21", "QUA", "PRETA", "PONCIANO"),
    ]

    for data_esp, dia_sem_esp, tipo_esp, nome_esp in escalados_esperados:
        dia = next(d for d in dados["dias"] if d["data"] == data_esp)
        assert dia["dia_semana"] == dia_sem_esp
        assert dia["tipo_escala"] == tipo_esp
        assert dia["impresso_nome"] == nome_esp


def test_regra_troca_caneta_preserva_folga():
    """DIRETRIZ DE OURO DO USUÁRIO:

    A troca a caneta não reseta a folga do substituto na escala oficial,
    apenas do militar que estava impresso.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Diego Lima e Andressa
        cursor.execute("SELECT id FROM militares WHERE nome_guerra = 'DIEGO LIMA'")
        id_diego = cursor.fetchone()[0]
        cursor.execute("SELECT id FROM militares WHERE nome_guerra = 'ANDRESSA'")
        id_andressa = cursor.fetchone()[0]

    # Em 11/09/2026 (dia seguinte a 10/09):
    folgas_11set = calcular_folgas_militares("2026-09-11")
    folga_diego = next(f for f in folgas_11set if f["id"] == id_diego)
    folga_andressa = next(f for f in folgas_11set if f["id"] == id_andressa)

    # Diego Lima estava impresso em 10/09, então sua folga em 11/09 é de 1 dia
    assert folga_diego["folga_preta"] == 1
    # Andressa tirou na caneta em 10/09, mas sua folga oficial NÃO foi resetada para 1 dia
    # (ela não tinha serviço impresso antes de 10/09 no dataset, folga = 999)
    assert folga_andressa["folga_preta"] == 999
    # Andressa possui 1 crédito de permuta
    assert folga_andressa["creditos_permuta"] >= 1


def test_intersticio_48h():
    """Garante que nenhum militar pode ser escalado em dias consecutivos."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM militares WHERE nome_guerra = 'BARRETO'")
        id_barreto = cursor.fetchone()[0]

    # Barreto está escalado em 11/09/2026 (SEX). Em 12/09/2026 (SAB) ele está em interstício
    valido_dia_seguinte = verificar_intersticio_valido(id_barreto, "2026-09-12")
    assert valido_dia_seguinte is False


def test_gerador_previsao_semana_43():
    """Testa o motor preditivo para a próxima semana a ser prevista: Semana 43 (22/10/2026 a 28/10/2026)."""
    previsao = gerar_previsao_semana(
        semana_ano=43,
        data_inicio_quinta_str="2026-10-22",
        posto_codigo="SGT_DE_DIA",
    )
    assert len(previsao) == 7

    # Primeiro dia da semana 43 (22/10 - Quinta-feira útil = PRETA)
    dia_22 = previsao[0]
    assert dia_22["data"] == "2026-10-22"
    assert dia_22["tipo_escala"] == "PRETA"
    # REIS tem a maior folga na preta
    assert dia_22["nome_guerra"] == "REIS"

    # Fim de semana (24/10 Sábado e 25/10 Domingo = VERMELHA)
    dia_24 = previsao[2]
    dia_25 = previsao[3]
    assert dia_24["tipo_escala"] == "VERMELHA"
    assert dia_25["tipo_escala"] == "VERMELHA"

    # 28/10 (Quarta-feira) é Dia do Servidor Público (VERMELHA)
    dia_28 = previsao[6]
    assert dia_28["data"] == "2026-10-28"
    assert dia_28["tipo_escala"] == "VERMELHA"


def test_api_endpoints():
    """Valida as respostas dos endpoints HTTP da API FastAPI."""
    res_dash = client.get("/api/dashboard")
    assert res_dash.status_code == 200
    dados_dash = res_dash.json()
    assert "total_efetivo" in dados_dash
    assert dados_dash["total_efetivo"] >= 25

    res_sem = client.get("/api/semanas")
    assert res_sem.status_code == 200

    res_escala = client.get("/api/escala/37")
    assert res_escala.status_code == 200
    assert len(res_escala.json()["dias"]) == 7


def test_exportar_png_endpoint():
    """Valida o endpoint de exportação visual da previsão da escala em PNG."""
    res = client.get("/api/exportar/png/41")
    assert res.status_code == 200
    assert res.headers["content-type"] == "image/png"
    assert len(res.content) > 1000  # Imagem binária não vazia


def test_confirmar_importacao_foto_e_recalculo_folgas():
    """Valida a importação de escala reconhecida por foto e o recálculo estrito das folgas."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM militares WHERE nome_guerra = 'ANDRESSA'")
        id_andressa = cursor.fetchone()[0]
        cursor.execute("SELECT id FROM militares WHERE nome_guerra = 'BARRETO'")
        id_barreto = cursor.fetchone()[0]

    # Simula importação de foto da Semana 50 onde Barreto foi impresso na Quinta e Andressa assumiu na caneta
    payload = {
        "semana_ano": 50,
        "dias": [
            {
                "data": "2026-12-10",
                "dia_semana": "QUI",
                "tipo_escala": "PRETA",
                "posto_codigo": "SGT_DE_DIA",
                "militar_impresso_id": id_barreto,
                "militar_caneta_id": id_andressa,
                "motivo": "Troca a caneta foto oficial",
            },
            {
                "data": "2026-12-11",
                "dia_semana": "SEX",
                "tipo_escala": "PRETA",
                "posto_codigo": "SGT_DE_DIA",
                "militar_impresso_id": id_andressa,
                "militar_caneta_id": None,
                "motivo": None,
            },
        ],
    }

    res = client.post("/api/confirmar-importacao-foto", json=payload)
    assert res.status_code == 200
    dados = res.json()
    assert dados["sucesso"] is True
    assert dados["dias_importados"] == 2
    assert dados["trocas_registradas"] == 1

    # Em 11/12/2026: Barreto teve serviço impresso em 10/12, logo sua folga é 1 dia
    folgas_11dez = calcular_folgas_militares("2026-12-11")
    folga_barreto = next(f for f in folgas_11dez if f["id"] == id_barreto)
    assert folga_barreto["folga_preta"] == 1

    # Em 12/12/2026: Andressa teve serviço impresso em 11/12, logo sua folga é 1 dia
    folgas_12dez = calcular_folgas_militares("2026-12-12")
    folga_andressa = next(f for f in folgas_12dez if f["id"] == id_andressa)
    assert folga_andressa["folga_preta"] == 1


def test_previsao_duas_semanas_e_override_preta_vermelha():
    """Valida a previsão de 2 semanas (14 dias) e a sobreposição manual de Preta/Vermelha."""
    res = client.post("/api/previsao/calcular", json={
        "semana_ano": 42,
        "data_inicio_quinta": "2026-10-15",
        "posto_codigo": "SGT_DE_DIA",
        "qtd_semanas": 2,
        "custom_tipos_dias": {
            "2026-10-16": "VERMELHA"  # Força uma sexta-feira útil a ser tratada como VERMELHA
        }
    })
    assert res.status_code == 200
    dados = res.json()
    assert dados["qtd_semanas"] == 2
    previsao = dados["previsao"]
    assert len(previsao) == 14  # 14 dias para 2 semanas

    # Primeiro dia: semana 42
    assert previsao[0]["semana_ano"] == 42
    # Oitavo dia: semana 43
    assert previsao[7]["semana_ano"] == 43

    # Sexta-feira 16/10 teve override para VERMELHA
    dia_16 = next(d for d in previsao if d["data"] == "2026-10-16")
    assert dia_16["tipo_escala"] == "VERMELHA"


def test_alterar_tipo_dia_endpoint():
    """Valida a alteração dinâmica do tipo de escala de um dia específico."""
    dados_sem = client.get("/api/escala/37").json()
    primeiro_dia_id = dados_sem["dias"][0]["id"]

    res_patch = client.patch(f"/api/escala/dia/{primeiro_dia_id}/tipo", json={"tipo_escala": "VERMELHA"})
    assert res_patch.status_code == 200
    assert res_patch.json()["tipo_escala"] == "VERMELHA"

    # Retorna para PRETA
    res_revert = client.patch(f"/api/escala/dia/{primeiro_dia_id}/tipo", json={"tipo_escala": "PRETA"})
    assert res_revert.status_code == 200
    assert res_revert.json()["tipo_escala"] == "PRETA"


def test_cadastrar_e_excluir_militar():
    """Valida o cadastro e a exclusão/desativação de militares no efetivo."""
    # Cadastra novo militar
    res_novo = client.post("/api/militares", json={
        "posto_graduacao": "3º Sgt",
        "nome_guerra": "SARGENTO_TESTE",
        "antiguidade_ordem": 99,
        "escala_habilitada": "SGT_DE_DIA",
        "subunidade": "BCMS"
    })
    assert res_novo.status_code == 200
    novo_id = res_novo.json()["id"]

    # Exclui o militar recém-criado
    res_del = client.delete(f"/api/militares/{novo_id}")
    assert res_del.status_code == 200
    assert res_del.json()["sucesso"] is True


def test_reordenar_antiguidade_militares():
    """Valida a reordenação de antiguidade via lista arrastável."""
    # Obter lista atual de militares
    militares = client.get("/api/militares").json()
    assert len(militares) >= 2

    # Inverte a ordem dos dois primeiros
    id_1 = militares[0]["id"]
    id_2 = militares[1]["id"]
    ids_reordenados = [id_2, id_1] + [m["id"] for m in militares[2:]]

    res = client.post("/api/militares/reordenar-antiguidade", json={"ordem_ids": ids_reordenados})
    assert res.status_code == 200
    assert res.json()["sucesso"] is True

    # Verifica se a nova ordem foi refletida no banco
    novos_militares = client.get("/api/militares").json()
    # militares[0] agora deve ser id_2
    assert novos_militares[0]["id"] == id_2
    assert novos_militares[0]["antiguidade"] == 1
    assert novos_militares[1]["id"] == id_1
    assert novos_militares[1]["antiguidade"] == 2

    # Restaura a ordem original
    ids_originais = [m["id"] for m in militares]
    client.post("/api/militares/reordenar-antiguidade", json={"ordem_ids": ids_originais})




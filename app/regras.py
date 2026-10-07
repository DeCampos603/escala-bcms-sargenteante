# -*- coding: utf-8 -*-
"""Motor de Regras de Negócio e Algoritmo Preditivo de Escala - EscalaPro BCMS.

Implementa a doutrina militar das Forças Armadas:
1. Escalas Preta (dias úteis) e Vermelha (sáb/dom/feriado) como filas paralelas independentes.
2. Contagem estrita de folga baseada exclusivamente no militar impresso oficial (trocas a caneta não alteram a folga).
3. Interstício obrigatório de descanso mínimo (48 horas entre quaisquer serviços).
4. Reconhecimento automático de feriados nacionais e militares.
5. Pulo ordenado de militares em gozo de férias ou afastamentos de saúde.
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta
from typing import Any

from app.db import get_db_connection

DIAS_SEMANA_MAP = {
    0: "SEG",
    1: "TER",
    2: "QUA",
    3: "QUI",
    4: "SEX",
    5: "SAB",
    6: "DOM",
}


def parse_date(data_str: str) -> date:
    """Converte string YYYY-MM-DD para objeto date."""
    return datetime.strptime(data_str, "%Y-%m-%d").date()


def format_date(dt: date) -> str:
    """Converte objeto date para YYYY-MM-DD."""
    return dt.strftime("%Y-%m-%d")


def obter_tipo_dia(data_str: str, conn: sqlite3.Connection | None = None) -> tuple[str, str, str | None]:
    """Retorna (tipo_escala, dia_semana_abrev, descricao_feriado_ou_none).

    - tipo_escala: 'PRETA' ou 'VERMELHA'
    - dia_semana: 'SEG', 'TER', 'QUA', 'QUI', 'SEX', 'SAB', 'DOM'
    """
    dt = parse_date(data_str)
    dia_sem = DIAS_SEMANA_MAP[dt.weekday()]

    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT descricao FROM feriados WHERE data = ?", (data_str,))
        row = cursor.fetchone()
        feriado_desc = row["descricao"] if row else None

        if dia_sem in ("SAB", "DOM") or feriado_desc:
            return "VERMELHA", dia_sem, feriado_desc
        return "PRETA", dia_sem, None
    finally:
        if should_close:
            conn.close()


def verificar_afastamento(militar_id: int, data_str: str, conn: sqlite3.Connection | None = None) -> dict | None:
    """Verifica se o militar está em afastamento (férias, dispensa, LTS) na data."""
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT motivo, observacao, data_inicio, data_fim
               FROM afastamentos
               WHERE militar_id = ?
                 AND ? BETWEEN data_inicio AND data_fim
               LIMIT 1""",
            (militar_id, data_str),
        )
        row = cursor.fetchone()
        if row:
            return {
                "motivo": row["motivo"],
                "observacao": row["observacao"],
                "periodo": f"{row['data_inicio']} a {row['data_fim']}",
            }
        return None
    finally:
        if should_close:
            conn.close()


def calcular_folgas_militares(
    data_referencia_str: str,
    posto_codigo: str = "SGT_DE_DIA",
    conn: sqlite3.Connection | None = None,
) -> list[dict[str, Any]]:
    """Calcula o tempo de folga exato de todos os militares aptos até a data de referência.

    IMPORTANTE (Regra de Ouro do Usuário):
    - Considera apenas serviços em que o militar foi o MILITAR IMPRESSO OFICIAL.
    - Trocas a caneta NÃO resetam nem alteram a folga do substituto.
    """
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        dt_ref = parse_date(data_referencia_str)
        cursor = conn.cursor()

        # Obter todos os militares ativos habilitados para o posto
        cursor.execute(
            """SELECT id, posto_graduacao, nome_guerra, antiguidade_ordem
               FROM militares
               WHERE ativo = 1 AND escala_habilitada = ?
               ORDER BY antiguidade_ordem ASC""",
            (posto_codigo,),
        )
        militares = [dict(row) for row in cursor.fetchall()]

        resultado = []
        for m in militares:
            m_id = m["id"]

            # Último serviço impresso na ESCALA PRETA
            cursor.execute(
                """SELECT data FROM escalas_dias
                   WHERE militar_impresso_id = ?
                     AND tipo_escala = 'PRETA'
                     AND data < ?
                   ORDER BY data DESC LIMIT 1""",
                (m_id, data_referencia_str),
            )
            row_p = cursor.fetchone()
            ult_data_p = row_p["data"] if row_p else None
            folga_preta = (dt_ref - parse_date(ult_data_p)).days if ult_data_p else 999

            # Último serviço impresso na ESCALA VERMELHA
            cursor.execute(
                """SELECT data FROM escalas_dias
                   WHERE militar_impresso_id = ?
                     AND tipo_escala = 'VERMELHA'
                     AND data < ?
                   ORDER BY data DESC LIMIT 1""",
                (m_id, data_referencia_str),
            )
            row_v = cursor.fetchone()
            ult_data_v = row_v["data"] if row_v else None
            folga_verm = (dt_ref - parse_date(ult_data_v)).days if ult_data_v else 999

            # Último serviço impresso GERAL (qualquer cor)
            cursor.execute(
                """SELECT data, tipo_escala FROM escalas_dias
                   WHERE militar_impresso_id = ?
                     AND data < ?
                   ORDER BY data DESC LIMIT 1""",
                (m_id, data_referencia_str),
            )
            row_g = cursor.fetchone()
            ult_data_g = row_g["data"] if row_g else None
            folga_geral = (dt_ref - parse_date(ult_data_g)).days if ult_data_g else 999

            # Total de serviços executados como substituto a caneta (crédito de permuta)
            cursor.execute(
                """SELECT COUNT(*) as qtd FROM permutas_trocas
                   WHERE militar_substituto_id = ? AND compensado = 0""",
                (m_id,),
            )
            creditos_permuta = cursor.fetchone()["qtd"]

            # Total de serviços cedidos a outrem (débito de permuta)
            cursor.execute(
                """SELECT COUNT(*) as qtd FROM permutas_trocas
                   WHERE militar_cedente_id = ? AND compensado = 0""",
                (m_id,),
            )
            debitos_permuta = cursor.fetchone()["qtd"]

            # Checar se possui afastamento ativo na data de referência
            afastamento = verificar_afastamento(m_id, data_referencia_str, conn=conn)

            resultado.append({
                "id": m_id,
                "posto_graduacao": m["posto_graduacao"],
                "nome_guerra": m["nome_guerra"],
                "antiguidade": m["antiguidade_ordem"],
                "folga_preta": folga_preta,
                "ult_servico_preta": ult_data_p,
                "folga_vermelha": folga_verm,
                "ult_servico_vermelha": ult_data_v,
                "folga_geral": folga_geral,
                "ult_servico_geral": ult_data_g,
                "creditos_permuta": creditos_permuta,
                "debitos_permuta": debitos_permuta,
                "saldo_permuta": creditos_permuta - debitos_permuta,
                "afastamento_ativo": afastamento,
            })

        return resultado
    finally:
        if should_close:
            conn.close()


def verificar_intersticio_valido(
    militar_id: int,
    data_alvo_str: str,
    escalas_em_memoria: list[dict[str, Any]] | None = None,
    conn: sqlite3.Connection | None = None,
) -> bool:
    """Verifica se o militar cumpre a trava de 48 horas de descanso entre serviços.

    Nenhum militar pode estar de serviço no dia anterior ou no dia posterior.
    """
    dt_alvo = parse_date(data_alvo_str)
    dias_proibidos = [
        format_date(dt_alvo - timedelta(days=1)),
        format_date(dt_alvo + timedelta(days=1)),
        data_alvo_str,
    ]

    # Verificar nas escalas já atribuídas nesta rodada preditiva em memória
    if escalas_em_memoria:
        for esc in escalas_em_memoria:
            if esc["militar_id"] == militar_id and esc["data"] in dias_proibidos:
                return False

    # Verificar no banco de dados persistido
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT data FROM escalas_dias
               WHERE (militar_impresso_id = ? OR militar_caneta_id = ?)
                 AND data IN (?, ?, ?)""",
            (militar_id, militar_id, dias_proibidos[0], dias_proibidos[1], dias_proibidos[2]),
        )
        return cursor.fetchone() is None
    finally:
        if should_close:
            conn.close()


def gerar_previsao_semana(
    semana_ano: int,
    data_inicio_quinta_str: str,
    posto_codigo: str = "SGT_DE_DIA",
    qtd_semanas: int = 1,
    custom_tipos_dias: dict[str, str] | None = None,
    conn: sqlite3.Connection | None = None,
) -> list[dict[str, Any]]:
    """Gera a previsão matemática de escalas para o BCMS (Até 2 semanas de previsão).

    Respeita:
    1. Fila da Escala Preta para dias úteis (maior folga preta).
    2. Fila da Escala Vermelha para sábados, domingos e feriados (maior folga vermelha).
    3. Opção de customização manual de cada dia (Preta ou Vermelha) definida pelo Sargenteante.
    4. Trava de interstício de 48h entre serviços consecutivos.
    5. Exclusão de militares em férias, dispensas médicas ou missões.
    """
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        dt_inicio = parse_date(data_inicio_quinta_str)
        total_dias = 7 * max(1, min(qtd_semanas, 4))
        datas_periodo = [dt_inicio + timedelta(days=i) for i in range(total_dias)]

        previsao: list[dict[str, Any]] = []
        historico_virtual_simulado: list[dict[str, Any]] = []

        for idx, dt in enumerate(datas_periodo):
            dt_str = format_date(dt)
            sem_ano = semana_ano + (idx // 7)

            tipo_escala_padrao, dia_sem, feriado_desc = obter_tipo_dia(dt_str, conn=conn)

            # Permite sobreposição/seleção manual pelo Sargenteante
            if custom_tipos_dias and dt_str in custom_tipos_dias:
                tipo_escala = custom_tipos_dias[dt_str].strip().upper()
            else:
                tipo_escala = tipo_escala_padrao

            # Obter folgas acumuladas atualizadas até a data do serviço
            ranking = calcular_folgas_militares(dt_str, posto_codigo=posto_codigo, conn=conn)

            # Atualizar ranking com as alocações virtuais feitas nos dias anteriores
            for r in ranking:
                for sim in historico_virtual_simulado:
                    if sim["militar_id"] == r["id"]:
                        sim_dt = parse_date(sim["data"])
                        # Se foi escalado na preta anteriormente
                        if sim["tipo"] == "PRETA" and (dt - sim_dt).days < r["folga_preta"]:
                            r["folga_preta"] = (dt - sim_dt).days
                        # Se foi escalado na vermelha anteriormente
                        if sim["tipo"] == "VERMELHA" and (dt - sim_dt).days < r["folga_vermelha"]:
                            r["folga_vermelha"] = (dt - sim_dt).days
                        # Folga geral
                        if (dt - sim_dt).days < r["folga_geral"]:
                            r["folga_geral"] = (dt - sim_dt).days

            # Filtrar candidatos elegíveis:
            # 1. Sem afastamento médico/férias
            # 2. Interstício de 48h respeitado
            candidatos_validos = []
            for r in ranking:
                if r["afastamento_ativo"]:
                    continue
                if not verificar_intersticio_valido(r["id"], dt_str, historico_virtual_simulado, conn=conn):
                    continue
                candidatos_validos.append(r)

            if not candidatos_validos:
                # Fallback de segurança se todo o efetivo estiver em trava
                candidatos_validos = [r for r in ranking if not r["afastamento_ativo"]]

            # Ordenar candidatos pela folga da fila correspondente (maior folga primeiro)
            if tipo_escala == "PRETA":
                candidatos_validos.sort(key=lambda x: (-x["folga_preta"], x["antiguidade"]))
            else:
                candidatos_validos.sort(key=lambda x: (-x["folga_vermelha"], x["antiguidade"]))

            escolhido = candidatos_validos[0]

            alocacao = {
                "data": dt_str,
                "dia_semana": dia_sem,
                "tipo_escala": tipo_escala,
                "feriado": feriado_desc,
                "semana_ano": sem_ano,
                "posto_codigo": posto_codigo,
                "militar_id": escolhido["id"],
                "posto_graduacao": escolhido["posto_graduacao"],
                "nome_guerra": escolhido["nome_guerra"],
                "folga_preta_acumulada": escolhido["folga_preta"],
                "folga_vermelha_acumulada": escolhido["folga_vermelha"],
                "status": "PREVISTO",
            }
            previsao.append(alocacao)

            # Adiciona ao histórico simulado para travar os próximos dias
            historico_virtual_simulado.append({
                "militar_id": escolhido["id"],
                "data": dt_str,
                "tipo": tipo_escala,
            })

        return previsao
    finally:
        if should_close:
            conn.close()


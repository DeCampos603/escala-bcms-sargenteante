# -*- coding: utf-8 -*-
"""Camada de Serviços e Repositório do EscalaPro BCMS.

Orquestra operações de negócio entre o banco SQLite, o algoritmo de regras e a API.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from app.db import get_db_connection
from app.regras import calcular_folgas_militares, format_date, obter_tipo_dia, parse_date


def listar_semanas_disponiveis(conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
    """Retorna lista consolidada de semanas já cadastradas com intervalo de datas."""
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT semana_ano,
                   MIN(data) as data_inicio,
                   MAX(data) as data_fim,
                   COUNT(*) as total_dias,
                   status
            FROM escalas_dias
            GROUP BY semana_ano
            ORDER BY semana_ano ASC
        """)
        return [dict(row) for row in cursor.fetchall()]
    finally:
        if should_close:
            conn.close()


def obter_escala_semana(
    semana_ano: int,
    posto_codigo: str = "SGT_DE_DIA",
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """Recupera todos os dias de uma semana de serviço para visualização no espelho clássico."""
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                e.id,
                e.data,
                e.semana_ano,
                e.dia_semana,
                e.tipo_escala,
                e.posto_codigo,
                e.status,
                e.observacoes,
                -- Militar Impresso Oficial
                m_imp.id as impresso_id,
                m_imp.posto_graduacao as impresso_graduacao,
                m_imp.nome_guerra as impresso_nome,
                -- Militar Substituto a Caneta
                m_can.id as caneta_id,
                m_can.posto_graduacao as caneta_graduacao,
                m_can.nome_guerra as caneta_nome,
                -- Dados da Permuta
                p.id as permuta_id,
                p.motivo as permuta_motivo,
                p.autorizado_por as permuta_autorizado_por,
                f.descricao as feriado_descricao
            FROM escalas_dias e
            JOIN militares m_imp ON e.militar_impresso_id = m_imp.id
            LEFT JOIN militares m_can ON e.militar_caneta_id = m_can.id
            LEFT JOIN permutas_trocas p ON p.escala_dia_id = e.id
            LEFT JOIN feriados f ON f.data = e.data
            WHERE e.semana_ano = ? AND e.posto_codigo = ?
            ORDER BY e.data ASC
        """, (semana_ano, posto_codigo))

        dias = [dict(row) for row in cursor.fetchall()]

        data_inicio = dias[0]["data"] if dias else ""
        data_fim = dias[-1]["data"] if dias else ""

        return {
            "semana_ano": semana_ano,
            "posto_codigo": posto_codigo,
            "data_inicio": data_inicio,
            "data_fim": data_fim,
            "titulo": f"PREVISÃO DA ESCALA DE SERVIÇO ({semana_ano}ª SEMANA)",
            "dias": dias,
        }
    finally:
        if should_close:
            conn.close()


def salvar_previsao_semana(
    previsao: list[dict[str, Any]],
    conn: sqlite3.Connection | None = None,
) -> int:
    """Salva a lista de previsão gerada no banco de dados como status PREVISTO/PUBLICADO."""
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        cursor = conn.cursor()
        salvos = 0
        for item in previsao:
            cursor.execute("""
                INSERT OR REPLACE INTO escalas_dias
                (data, semana_ano, dia_semana, tipo_escala, posto_codigo, militar_impresso_id, status, observacoes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                item["data"],
                item["semana_ano"],
                item["dia_semana"],
                item["tipo_escala"],
                item["posto_codigo"],
                item["militar_id"],
                item.get("status", "PREVISTO"),
                item.get("feriado"),
            ))
            salvos += 1
        conn.commit()
        return salvos
    finally:
        if should_close:
            conn.close()


def registrar_troca_caneta(
    escala_dia_id: int,
    militar_substituto_id: int,
    motivo: str,
    autorizado_por: str = "Fiscal de Dia",
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """Registra uma troca a caneta.

    DIRETRIZ FUNDAMENTAL:
    O militar substituto assume a execução no dia, gerando crédito de permuta,
    mas a folga e o rodízio na escala impressa oficial NÃO são alterados.
    """
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM escalas_dias WHERE id = ?", (escala_dia_id,))
        escala = cursor.fetchone()
        if not escala:
            raise ValueError(f"Escala ID {escala_dia_id} não encontrada.")

        militar_cedente_id = escala["militar_impresso_id"]

        if militar_cedente_id == militar_substituto_id:
            raise ValueError("O militar substituto não pode ser o mesmo titular impresso.")

        # Atualiza a escala do dia marcando o substituto
        cursor.execute("""
            UPDATE escalas_dias
            SET militar_caneta_id = ?, updated_at = datetime('now', 'localtime')
            WHERE id = ?
        """, (militar_substituto_id, escala_dia_id))

        # Registra ou atualiza a permuta na tabela de auditoria
        cursor.execute("DELETE FROM permutas_trocas WHERE escala_dia_id = ?", (escala_dia_id,))
        cursor.execute("""
            INSERT INTO permutas_trocas
            (escala_dia_id, data_servico, militar_cedente_id, militar_substituto_id, motivo, autorizado_por)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (escala_dia_id, escala["data"], militar_cedente_id, militar_substituto_id, motivo, autorizado_por))

        conn.commit()
        return {"sucesso": True, "mensagem": "Troca a caneta registrada com sucesso."}
    finally:
        if should_close:
            conn.close()


def remover_troca_caneta(escala_dia_id: int, conn: sqlite3.Connection | None = None) -> bool:
    """Cancela uma troca a caneta, voltando o serviço ao militar titular impresso."""
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE escalas_dias
            SET militar_caneta_id = NULL, updated_at = datetime('now', 'localtime')
            WHERE id = ?
        """, (escala_dia_id,))
        cursor.execute("DELETE FROM permutas_trocas WHERE escala_dia_id = ?", (escala_dia_id,))
        conn.commit()
        return True
    finally:
        if should_close:
            conn.close()


def listar_extrato_permutas(conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
    """Retorna o extrato de todas as permutas/trocas realizadas no período."""
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                p.id,
                p.data_servico,
                p.motivo,
                p.autorizado_por,
                p.compensado,
                p.created_at,
                ced.id as cedente_id,
                ced.posto_graduacao as cedente_graduacao,
                ced.nome_guerra as cedente_nome,
                sub.id as substituto_id,
                sub.posto_graduacao as substituto_graduacao,
                sub.nome_guerra as substituto_nome,
                e.tipo_escala,
                e.dia_semana,
                e.semana_ano
            FROM permutas_trocas p
            JOIN militares ced ON p.militar_cedente_id = ced.id
            JOIN militares sub ON p.militar_substituto_id = sub.id
            JOIN escalas_dias e ON p.escala_dia_id = e.id
            ORDER BY p.data_servico DESC
        """)
        return [dict(row) for row in cursor.fetchall()]
    finally:
        if should_close:
            conn.close()


def adicionar_militar(
    posto_graduacao: str,
    nome_guerra: str,
    antiguidade_ordem: int = 999,
    escala_habilitada: str = "SGT_DE_DIA",
    subunidade: str = "BCMS",
    conn: sqlite3.Connection | None = None,
) -> int:
    """Adiciona um novo militar ao efetivo."""
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO militares (posto_graduacao, nome_guerra, antiguidade_ordem, escala_habilitada, subunidade)
            VALUES (?, ?, ?, ?, ?)
        """, (posto_graduacao, nome_guerra.upper().strip(), antiguidade_ordem, escala_habilitada, subunidade))
        conn.commit()
        return cursor.lastrowid
    finally:
        if should_close:
            conn.close()


def adicionar_afastamento(
    militar_id: int,
    data_inicio: str,
    data_fim: str,
    motivo: str,
    observacao: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> int:
    """Lança um afastamento (férias, atestado, missão) que bloqueia a escala no período."""
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO afastamentos (militar_id, data_inicio, data_fim, motivo, observacao)
            VALUES (?, ?, ?, ?, ?)
        """, (militar_id, data_inicio, data_fim, motivo, observacao))
        conn.commit()
        return cursor.lastrowid
    finally:
        if should_close:
            conn.close()


def listar_afastamentos(conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
    """Lista todos os afastamentos cadastrados com dados do militar."""
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                a.id,
                a.data_inicio,
                a.data_fim,
                a.motivo,
                a.observacao,
                m.id as militar_id,
                m.posto_graduacao,
                m.nome_guerra
            FROM afastamentos a
            JOIN militares m ON a.militar_id = m.id
            ORDER BY a.data_inicio DESC
        """)
        return [dict(row) for row in cursor.fetchall()]
    finally:
        if should_close:
            conn.close()


def obter_estatisticas_dashboard(
    data_ref_str: str = "2026-10-05",
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """Retorna métricas consolidadas para os cards do dashboard executivo."""
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM militares WHERE ativo = 1")
        total_efetivo = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM escalas_dias")
        total_escalas = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM permutas_trocas")
        total_permutas = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM afastamentos WHERE ? BETWEEN data_inicio AND data_fim", (data_ref_str,))
        afastados_hoje = cursor.fetchone()[0]

        # Ranking de maiores folgas
        folgas = calcular_folgas_militares(data_ref_str, conn=conn)

        top_preta = sorted(folgas, key=lambda x: -x["folga_preta"])[:5]
        top_vermelha = sorted(folgas, key=lambda x: -x["folga_vermelha"])[:5]

        return {
            "total_efetivo": total_efetivo,
            "total_escalas_registradas": total_escalas,
            "total_permutas_registradas": total_permutas,
            "afastados_hoje": afastados_hoje,
            "top_folgas_preta": top_preta,
            "top_folgas_vermelha": top_vermelha,
        }
    finally:
        if should_close:
            conn.close()


def importar_escala_foto(
    semana_ano: int,
    dias: list[dict[str, Any]],
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """Salva no banco de dados os dias reconhecidos da foto da escala oficial.

    Atualiza as folgas de todo o efetivo (baseando o histórico no militar_impresso)
    e registra anotações a caneta na auditoria de permutas.
    """
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        cursor = conn.cursor()
        salvos = 0
        trocas_salvas = 0

        for d in dias:
            data_str = d["data"]
            dia_sem = d.get("dia_semana", "")
            tipo_esc = d.get("tipo_escala", "PRETA")
            posto_cod = d.get("posto_codigo", "SGT_DE_DIA")
            militar_imp_id = d.get("militar_impresso_id")
            militar_can_id = d.get("militar_caneta_id")
            motivo = d.get("motivo") or "Anotação a caneta na escala física oficial"

            if not militar_imp_id:
                nome_imp = d.get("militar_impresso_nome")
                if nome_imp:
                    cursor.execute(
                        "SELECT id FROM militares WHERE UPPER(nome_guerra) = ? AND ativo = 1",
                        (nome_imp.upper(),),
                    )
                    row = cursor.fetchone()
                    if row:
                        militar_imp_id = row["id"]

            if not militar_imp_id:
                continue

            if militar_can_id is None and d.get("militar_caneta_nome"):
                cursor.execute(
                    "SELECT id FROM militares WHERE UPPER(nome_guerra) = ? AND ativo = 1",
                    (d["militar_caneta_nome"].upper(),),
                )
                row = cursor.fetchone()
                if row:
                    militar_can_id = row["id"]

            cursor.execute(
                "SELECT id FROM escalas_dias WHERE data = ? AND posto_codigo = ?",
                (data_str, posto_cod),
            )
            existente = cursor.fetchone()

            if existente:
                escala_dia_id = existente["id"]
                cursor.execute("""
                    UPDATE escalas_dias
                    SET semana_ano = ?,
                        dia_semana = ?,
                        tipo_escala = ?,
                        militar_impresso_id = ?,
                        militar_caneta_id = ?,
                        status = 'PUBLICADO',
                        updated_at = datetime('now', 'localtime')
                    WHERE id = ?
                """, (semana_ano, dia_sem, tipo_esc, militar_imp_id, militar_can_id, escala_dia_id))
            else:
                cursor.execute("""
                    INSERT INTO escalas_dias
                    (data, semana_ano, dia_semana, tipo_escala, posto_codigo, militar_impresso_id, militar_caneta_id, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'PUBLICADO')
                """, (data_str, semana_ano, dia_sem, tipo_esc, posto_cod, militar_imp_id, militar_can_id))
                escala_dia_id = cursor.lastrowid

            salvos += 1

            cursor.execute("DELETE FROM permutas_trocas WHERE escala_dia_id = ?", (escala_dia_id,))
            if militar_can_id and militar_can_id != militar_imp_id:
                cursor.execute("""
                    INSERT INTO permutas_trocas
                    (escala_dia_id, data_servico, militar_cedente_id, militar_substituto_id, motivo, autorizado_por)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (escala_dia_id, data_str, militar_imp_id, militar_can_id, motivo, "Foto Escala Oficial"))
                trocas_salvas += 1

        conn.commit()
        return {
            "sucesso": True,
            "semana_ano": semana_ano,
            "dias_importados": salvos,
            "trocas_registradas": trocas_salvas,
            "mensagem": f"Escala da {semana_ano}ª Semana importada com sucesso! Folgas recalculadas automaticamente.",
        }
    finally:
        if should_close:
            conn.close()


def alterar_tipo_escala_dia(
    escala_dia_id: int,
    novo_tipo: str,
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """Altera o tipo da escala de um dia específico (PRETA ou VERMELHA)."""
    novo_tipo = novo_tipo.strip().upper()
    if novo_tipo not in ("PRETA", "VERMELHA"):
        raise ValueError("O tipo de escala deve ser 'PRETA' ou 'VERMELHA'.")

    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, data FROM escalas_dias WHERE id = ?", (escala_dia_id,))
        dia = cursor.fetchone()
        if not dia:
            raise ValueError(f"Dia de escala ID {escala_dia_id} não encontrado.")

        cursor.execute("""
            UPDATE escalas_dias
            SET tipo_escala = ?, updated_at = datetime('now', 'localtime')
            WHERE id = ?
        """, (novo_tipo, escala_dia_id))
        conn.commit()
        return {"sucesso": True, "tipo_escala": novo_tipo, "mensagem": f"Escala alterada para {novo_tipo} com sucesso."}
    finally:
        if should_close:
            conn.close()


def excluir_militar(
    militar_id: int,
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """Exclui ou desativa um militar do efetivo ativo."""
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, nome_guerra FROM militares WHERE id = ?", (militar_id,))
        m = cursor.fetchone()
        if not m:
            raise ValueError(f"Militar ID {militar_id} não encontrado.")

        # Verifica se possui histórico de serviços na tabela de escalas
        cursor.execute(
            "SELECT COUNT(*) FROM escalas_dias WHERE militar_impresso_id = ? OR militar_caneta_id = ?",
            (militar_id, militar_id),
        )
        total_historico = cursor.fetchone()[0]

        if total_historico == 0:
            cursor.execute("DELETE FROM afastamentos WHERE militar_id = ?", (militar_id,))
            cursor.execute("DELETE FROM militares WHERE id = ?", (militar_id,))
            msg = f"Militar {m['nome_guerra']} excluído permanentemente do efetivo."
        else:
            # Desativa para preservar a integridade das escalas anteriores
            cursor.execute("UPDATE militares SET ativo = 0 WHERE id = ?", (militar_id,))
            msg = f"Militar {m['nome_guerra']} removido do efetivo ativo (histórico preservado)."

        conn.commit()
        return {"sucesso": True, "mensagem": msg}
    finally:
        if should_close:
            conn.close()


def reordenar_antiguidade_militares(
    ordem_ids: list[int],
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """Atualiza a ordem de antiguidade (antiguidade_ordem) dos militares.

    Recebe a lista de IDs de militares na nova ordem desejada (do 1º ao último).
    Atualiza no SQLite e sincroniza em dados/carga_inicial.json.
    """
    if not ordem_ids:
        raise ValueError("A lista de IDs não pode ser vazia.")

    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        cursor = conn.cursor()
        for idx, m_id in enumerate(ordem_ids, start=1):
            cursor.execute(
                "UPDATE militares SET antiguidade_ordem = ? WHERE id = ?",
                (idx, m_id),
            )
        conn.commit()

        # Sincroniza também no carga_inicial.json se existir
        from app.db import SEED_PATH
        if SEED_PATH.exists():
            try:
                import json
                with open(SEED_PATH, "r", encoding="utf-8") as f:
                    seed = json.load(f)

                cursor.execute("SELECT id, nome_guerra, antiguidade_ordem FROM militares")
                mapa_ordem = {r["nome_guerra"].upper(): r["antiguidade_ordem"] for r in cursor.fetchall()}

                for m in seed.get("militares", []):
                    ng = m.get("nome_guerra", "").upper()
                    if ng in mapa_ordem:
                        m["antiguidade_ordem"] = mapa_ordem[ng]

                seed["militares"].sort(key=lambda x: x.get("antiguidade_ordem", 999))

                with open(SEED_PATH, "w", encoding="utf-8") as f:
                    json.dump(seed, f, indent=2, ensure_ascii=False)
            except Exception:
                pass

        return {
            "sucesso": True,
            "total_atualizados": len(ordem_ids),
            "mensagem": f"Ordem de antiguidade atualizada com sucesso para {len(ordem_ids)} militares.",
        }
    finally:
        if should_close:
            conn.close()




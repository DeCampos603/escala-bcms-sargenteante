# -*- coding: utf-8 -*-
"""Camada de Banco de Dados SQLite (escalas.db) para o EscalaPro BCMS.

Estrutura local atômica e resiliente, sem dependências externas de SGBD.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
DB_PATH = ROOT_DIR / "dados" / "escalas.db"
SEED_PATH = ROOT_DIR / "dados" / "carga_inicial.json"
FERIADOS_PATH = ROOT_DIR / "dados" / "feriados_2026.json"


def get_db_connection() -> sqlite3.Connection:
    """Retorna conexão ativa com o SQLite configurada para RowDict e Foreign Keys."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db() -> None:
    """Cria tabelas se não existirem e executa a carga inicial automática se o banco estiver vazio."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # 1. Tabela de Postos de Serviço
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS postos_servico (
                codigo TEXT PRIMARY KEY,
                nome TEXT NOT NULL,
                posto_graduacao_requerido TEXT NOT NULL,
                ordem_exibicao INTEGER DEFAULT 0
            );
        """)

        # 2. Tabela de Militares
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS militares (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                posto_graduacao TEXT NOT NULL DEFAULT '3º Sgt',
                nome_guerra TEXT UNIQUE NOT NULL,
                nome_completo TEXT,
                identidade_militar TEXT,
                subunidade TEXT DEFAULT 'BCMS',
                escala_habilitada TEXT NOT NULL DEFAULT 'SGT_DE_DIA',
                antiguidade_ordem INTEGER DEFAULT 999,
                ativo INTEGER DEFAULT 1,
                created_at TEXT DEFAULT (datetime('now', 'localtime'))
            );
        """)

        # 3. Tabela de Feriados
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS feriados (
                data TEXT PRIMARY KEY,
                descricao TEXT NOT NULL,
                tipo TEXT NOT NULL DEFAULT 'NACIONAL'
            );
        """)

        # 4. Tabela de Afastamentos / Dispensas
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS afastamentos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                militar_id INTEGER NOT NULL,
                data_inicio TEXT NOT NULL,
                data_fim TEXT NOT NULL,
                motivo TEXT NOT NULL,
                observacao TEXT,
                created_at TEXT DEFAULT (datetime('now', 'localtime')),
                FOREIGN KEY (militar_id) REFERENCES militares (id) ON DELETE CASCADE
            );
        """)

        # 5. Tabela de Escalas Diárias (Escalado Oficial e Caneta)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS escalas_dias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data TEXT NOT NULL,
                semana_ano INTEGER NOT NULL,
                dia_semana TEXT NOT NULL,
                tipo_escala TEXT NOT NULL, -- 'PRETA' ou 'VERMELHA'
                posto_codigo TEXT NOT NULL,
                militar_impresso_id INTEGER NOT NULL,
                militar_caneta_id INTEGER,
                status TEXT NOT NULL DEFAULT 'PUBLICADO', -- 'PREVISTO', 'PUBLICADO', 'EXECUTADO'
                observacoes TEXT,
                created_at TEXT DEFAULT (datetime('now', 'localtime')),
                updated_at TEXT DEFAULT (datetime('now', 'localtime')),
                UNIQUE(data, posto_codigo),
                FOREIGN KEY (posto_codigo) REFERENCES postos_servico (codigo),
                FOREIGN KEY (militar_impresso_id) REFERENCES militares (id),
                FOREIGN KEY (militar_caneta_id) REFERENCES militares (id)
            );
        """)

        # 6. Tabela de Permutas / Trocas a Caneta (Conta-Corrente)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS permutas_trocas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                escala_dia_id INTEGER NOT NULL,
                data_servico TEXT NOT NULL,
                militar_cedente_id INTEGER NOT NULL,     -- quem estava impresso
                militar_substituto_id INTEGER NOT NULL,  -- quem assumiu a caneta
                motivo TEXT,
                autorizado_por TEXT,
                compensado INTEGER DEFAULT 0,
                data_compensacao TEXT,
                created_at TEXT DEFAULT (datetime('now', 'localtime')),
                FOREIGN KEY (escala_dia_id) REFERENCES escalas_dias (id) ON DELETE CASCADE,
                FOREIGN KEY (militar_cedente_id) REFERENCES militares (id),
                FOREIGN KEY (militar_substituto_id) REFERENCES militares (id)
            );
        """)

        conn.commit()

        # Seed inicial caso tabelas estejam vazias
        _seed_initial_data(conn)


def _seed_initial_data(conn: sqlite3.Connection) -> None:
    """Insere dados das semanas 37 a 41 e feriados se banco estiver vazio."""
    cursor = conn.cursor()

    # Seed Feriados
    cursor.execute("SELECT COUNT(*) FROM feriados")
    if cursor.fetchone()[0] == 0 and FERIADOS_PATH.exists():
        with open(FERIADOS_PATH, "r", encoding="utf-8") as f:
            feriados_data = json.load(f)
            for fer in feriados_data:
                cursor.execute(
                    "INSERT OR IGNORE INTO feriados (data, descricao, tipo) VALUES (?, ?, ?)",
                    (fer["data"], fer["descricao"], fer["tipo"]),
                )
        conn.commit()

    # Seed Postos e Militares
    cursor.execute("SELECT COUNT(*) FROM militares")
    if cursor.fetchone()[0] == 0 and SEED_PATH.exists():
        with open(SEED_PATH, "r", encoding="utf-8") as f:
            seed = json.load(f)

        # Inserir postos
        for p in seed.get("postos", []):
            cursor.execute(
                "INSERT OR IGNORE INTO postos_servico (codigo, nome, posto_graduacao_requerido, ordem_exibicao) VALUES (?, ?, ?, ?)",
                (p["codigo"], p["nome"], p["posto_graduacao_requerido"], p["ordem_exibicao"]),
            )

        # Inserir militares
        militares_map: dict[str, int] = {}
        for m in seed.get("militares", []):
            cursor.execute(
                """INSERT INTO militares (posto_graduacao, nome_guerra, antiguidade_ordem, escala_habilitada)
                   VALUES (?, ?, ?, ?)""",
                (m["posto_graduacao"], m["nome_guerra"], m["antiguidade_ordem"], m["escala_habilitada"]),
            )
            militares_map[m["nome_guerra"]] = cursor.lastrowid

        # Inserir histórico das semanas 37 a 41
        for h in seed.get("historico_escalas", []):
            imp_id = militares_map.get(h["militar_impresso"])
            can_id = militares_map.get(h["militar_caneta"]) if h.get("militar_caneta") else None

            cursor.execute(
                """INSERT OR REPLACE INTO escalas_dias
                   (data, semana_ano, dia_semana, tipo_escala, posto_codigo, militar_impresso_id, militar_caneta_id, status, observacoes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    h["data"],
                    h["semana_ano"],
                    h["dia_semana"],
                    h["tipo_escala"],
                    h["posto_codigo"],
                    imp_id,
                    can_id,
                    h["status"],
                    h.get("observacoes"),
                ),
            )
            escala_id = cursor.lastrowid

            # Se houve troca a caneta, registra na conta-corrente de permutas
            if can_id and imp_id:
                cursor.execute(
                    """INSERT INTO permutas_trocas
                       (escala_dia_id, data_servico, militar_cedente_id, militar_substituto_id, motivo)
                       VALUES (?, ?, ?, ?, ?)""",
                    (escala_id, h["data"], imp_id, can_id, h.get("motivo_troca", "Permuta de escala")),
                )

        conn.commit()

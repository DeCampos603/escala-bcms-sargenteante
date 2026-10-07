# -*- coding: utf-8 -*-
"""Módulo de Exportação e Relatórios - EscalaPro BCMS.

Gera planilhas Excel (.xlsx) profissionais e relatórios HTML/PDF
com o layout idêntico à folha de serviço do BCMS (Prancheta / Mural).
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from app.servicos import listar_extrato_permutas, obter_escala_semana


def gerar_excel_escala_semanal(semana_ano: int, posto_codigo: str = "SGT_DE_DIA") -> io.BytesIO:
    """Gera pasta de trabalho Excel (.xlsx) contendo o espelho da semana e o extrato de permutas."""
    dados_semana = obter_escala_semana(semana_ano, posto_codigo=posto_codigo)
    permutas = listar_extrato_permutas()

    wb = openpyxl.Workbook()

    # -------------------------------------------------------------
    # ABA 1: Espelho da Escala (Layout A4 Paisagem BCMS)
    # -------------------------------------------------------------
    ws1 = wb.active
    ws1.title = f"Semana {semana_ano}"
    ws1.views.sheetView[0].showGridLines = True

    # Cores e Estilos Militares
    navy_fill = PatternFill(start_color="0F172A", end_color="0F172A", fill_type="solid")
    red_header_fill = PatternFill(start_color="991B1B", end_color="991B1B", fill_type="solid")
    red_col_fill = PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid")
    gray_fill = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")

    font_title = Font(name="Calibri", size=14, bold=True, color="FFFFFF")
    font_sub = Font(name="Calibri", size=10, bold=True, color="64748B")
    font_header = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    font_bold = Font(name="Calibri", size=11, bold=True, color="0F172A")
    font_regular = Font(name="Calibri", size=11, color="1E293B")
    font_caneta = Font(name="Calibri", size=10, bold=True, color="1E3A8A") # Azul caneta
    font_riscado = Font(name="Calibri", size=9, strike=True, color="94A3B8")

    thin_border = Border(
        left=Side(style="thin", color="CBD5E1"),
        right=Side(style="thin", color="CBD5E1"),
        top=Side(style="thin", color="CBD5E1"),
        bottom=Side(style="thin", color="CBD5E1"),
    )
    double_bottom_border = Border(
        left=Side(style="thin", color="CBD5E1"),
        right=Side(style="thin", color="CBD5E1"),
        top=Side(style="thin", color="CBD5E1"),
        bottom=Side(style="double", color="0F172A"),
    )

    # Cabeçalho Geral
    ws1.merge_cells("A1:H1")
    title_cell = ws1["A1"]
    title_cell.value = "BATALHÃO CENTRAL DE MANUTENÇÃO E SUPRIMENTO (UASG 160329)"
    title_cell.font = font_title
    title_cell.fill = navy_fill
    title_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws1.row_dimensions[1].height = 28

    ws1.merge_cells("A2:H2")
    sub_cell = ws1["A2"]
    data_inicio = dados_semana.get("data_inicio", "")
    data_fim = dados_semana.get("data_fim", "")
    sub_cell.value = f"{semana_ano} - PREVISÃO DA ESCALA DE SERVIÇO (DE {data_inicio} A {data_fim})"
    sub_cell.font = Font(name="Calibri", size=11, bold=True, color="0F172A")
    sub_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws1.row_dimensions[2].height = 22

    # Linha de Cabeçalho das Colunas (A3:H3)
    ws1.cell(row=3, column=1, value="POSTO / DIAS").font = font_header
    ws1.cell(row=3, column=1).fill = navy_fill
    ws1.cell(row=3, column=1).alignment = Alignment(horizontal="center", vertical="center")
    ws1.cell(row=3, column=1).border = thin_border

    dias = dados_semana.get("dias", [])
    for idx, d in enumerate(dias, start=2):
        col_cell = ws1.cell(row=3, column=idx)
        # Formato: QUI (10)
        dt_parts = d["data"].split("-")
        dia_num = dt_parts[2] if len(dt_parts) == 3 else ""
        col_cell.value = f"{d['dia_semana']} ({dia_num})"
        col_cell.border = thin_border
        col_cell.alignment = Alignment(horizontal="center", vertical="center")

        if d["tipo_escala"] == "VERMELHA":
            col_cell.fill = red_header_fill
            col_cell.font = font_header
        else:
            col_cell.fill = navy_fill
            col_cell.font = font_header

    ws1.row_dimensions[3].height = 24

    # Linha do Posto: SGT DE DIA
    ws1.cell(row=4, column=1, value="SGT DE DIA").font = font_bold
    ws1.cell(row=4, column=1).alignment = Alignment(horizontal="center", vertical="center")
    ws1.cell(row=4, column=1).border = thin_border
    ws1.cell(row=4, column=1).fill = gray_fill

    for idx, d in enumerate(dias, start=2):
        cell = ws1.cell(row=4, column=idx)
        cell.border = thin_border
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

        if d["tipo_escala"] == "VERMELHA":
            cell.fill = red_col_fill

        if d.get("caneta_nome"):
            # Houve troca a caneta: mostra o titular impresso riscado e o substituto
            cell.value = f"3º Sgt {d['impresso_nome']}\n[CANETA: {d['caneta_nome']}]"
        else:
            cell.value = f"3º Sgt {d['impresso_nome']}"
            cell.font = font_regular

    ws1.row_dimensions[4].height = 42

    # Linha de Observações / Feriados
    ws1.cell(row=5, column=1, value="OBSERVAÇÕES").font = Font(name="Calibri", size=9, bold=True, color="64748B")
    ws1.cell(row=5, column=1).alignment = Alignment(horizontal="center", vertical="center")
    ws1.cell(row=5, column=1).border = thin_border

    for idx, d in enumerate(dias, start=2):
        cell = ws1.cell(row=5, column=idx)
        cell.border = thin_border
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        obs_text = []
        if d.get("feriado_descricao"):
            obs_text.append(f"Feriado: {d['feriado_descricao']}")
        if d.get("observacoes"):
            obs_text.append(d["observacoes"])
        cell.value = " | ".join(obs_text)
        cell.font = Font(name="Calibri", size=8, italic=True, color="64748B")

    ws1.row_dimensions[5].height = 24

    # Ajuste de largura das colunas
    ws1.column_dimensions["A"].width = 22
    for c in ["B", "C", "D", "E", "F", "G", "H"]:
        ws1.column_dimensions[c].width = 20

    # -------------------------------------------------------------
    # ABA 2: Extrato de Permutas (Trocas a Caneta)
    # -------------------------------------------------------------
    ws2 = wb.create_sheet(title="Extrato de Permutas")
    ws2.views.sheetView[0].showGridLines = True

    headers_permutas = [
        "Data do Serviço",
        "Semana",
        "Dia",
        "Tipo",
        "Militar Cedente (Impresso)",
        "Militar Substituto (Caneta)",
        "Motivo da Troca",
        "Autorizado Por",
    ]

    for col_idx, h in enumerate(headers_permutas, 1):
        c = ws2.cell(row=1, column=col_idx, value=h)
        c.font = font_header
        c.fill = navy_fill
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border = thin_border

    ws2.row_dimensions[1].height = 24

    for row_idx, p in enumerate(permutas, start=2):
        ws2.cell(row=row_idx, column=1, value=p["data_servico"]).alignment = Alignment(horizontal="center")
        ws2.cell(row=row_idx, column=2, value=f"{p['semana_ano']}ª Sem").alignment = Alignment(horizontal="center")
        ws2.cell(row=row_idx, column=3, value=p["dia_semana"]).alignment = Alignment(horizontal="center")
        ws2.cell(row=row_idx, column=4, value=p["tipo_escala"]).alignment = Alignment(horizontal="center")
        ws2.cell(row=row_idx, column=5, value=f"{p['cedente_graduacao']} {p['cedente_nome']}").alignment = Alignment(horizontal="left")
        ws2.cell(row=row_idx, column=6, value=f"{p['substituto_graduacao']} {p['substituto_nome']}").alignment = Alignment(horizontal="left")
        ws2.cell(row=row_idx, column=7, value=p.get("motivo", "")).alignment = Alignment(horizontal="left")
        ws2.cell(row=row_idx, column=8, value=p.get("autorizado_por", "")).alignment = Alignment(horizontal="center")

        for col_idx in range(1, 9):
            ws2.cell(row=row_idx, column=col_idx).border = thin_border
            ws2.cell(row=row_idx, column=col_idx).font = font_regular

    for col in ws2.columns:
        max_len = max(len(str(cell.value or "")) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws2.column_dimensions[col_letter].width = max(max_len + 4, 14)

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output


def _get_browser_path() -> str | None:
    """Localiza executável do Microsoft Edge ou Google Chrome no Windows."""
    candidates = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    for c in candidates:
        if Path(c).exists():
            return c
    return None


def gerar_png_escala_semanal(
    semana_ano: int,
    posto_codigo: str = "SGT_DE_DIA",
    dados_custom: dict[str, Any] | None = None,
) -> io.BytesIO:
    """Gera imagem visual de alta definição (PNG 1600x900) da previsão da escala.

    Pronta para divulgação no WhatsApp, mural ou arquivamento.
    """
    import os
    import subprocess
    import tempfile
    import uuid

    if dados_custom:
        dados = dados_custom
    else:
        dados = obter_escala_semana(semana_ano, posto_codigo=posto_codigo)

    dias = dados.get("dias", [])
    data_inicio = dados.get("data_inicio", "")
    data_fim = dados.get("data_fim", "")

    # Monta as colunas de dias em HTML
    cols_html = []
    for d in dias:
        is_red = d["tipo_escala"] == "VERMELHA"
        has_swap = bool(d.get("caneta_nome"))

        dt_parts = d["data"].split("-")
        dia_num = dt_parts[2] if len(dt_parts) == 3 else ""

        col_bg = "rgba(239, 68, 68, 0.08)" if is_red else "rgba(30, 41, 59, 0.7)"
        border_color = "rgba(239, 68, 68, 0.4)" if is_red else "rgba(51, 65, 85, 0.8)"
        header_bg = "rgba(239, 68, 68, 0.25)" if is_red else "rgba(15, 23, 42, 0.9)"
        title_color = "#F87171" if is_red else "#F1F5F9"

        swap_html = ""
        if has_swap:
            swap_html = f"""
            <div style="background: rgba(59, 130, 246, 0.2); border: 1.5px dashed #3B82F6; border-radius: 6px; padding: 6px 8px; margin-top: 8px;">
              <div style="font-size: 11px; font-weight: 800; color: #60A5FA; text-transform: uppercase;">Assumiu (Caneta)</div>
              <div style="font-size: 15px; font-weight: 800; color: #93C5FD;">{d['caneta_graduacao']} {d['caneta_nome']}</div>
              <div style="font-size: 10px; color: #BAE6FD; margin-top: 2px;">{d.get('permuta_motivo') or 'Permuta Operacional'}</div>
            </div>
            """
            militar_class = "text-decoration: line-through; opacity: 0.6; font-size: 13px; color: #94A3B8;"
        else:
            militar_class = "font-size: 17px; font-weight: 800; color: #FFFFFF;"

        obs_text = d.get("feriado_descricao") or d.get("observacoes") or ("Escala Vermelha" if is_red else "Expediente")

        cols_html.append(f"""
        <div style="flex: 1; background: {col_bg}; border: 1px solid {border_color}; border-radius: 10px; display: flex; flex-direction: column; overflow: hidden;">
          <div style="background: {header_bg}; padding: 12px 8px; text-align: center; border-bottom: 1px solid {border_color};">
            <div style="font-size: 16px; font-weight: 800; color: {title_color};">{d['dia_semana']} ({dia_num})</div>
            <div style="font-size: 12px; color: #94A3B8; font-weight: 600; margin-top: 2px;">{d['data']}</div>
            {"<span style='background:#EF4444; color:#FFF; font-size: 9px; font-weight:800; padding:2px 8px; border-radius:12px; margin-top:4px; display:inline-block;'>VERMELHA</span>" if is_red else ""}
          </div>
          <div style="flex: 1; padding: 18px 10px; display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center;">
            <div style="font-size: 12px; color: #94A3B8; font-weight: 700; text-transform: uppercase;">{d['impresso_graduacao']}</div>
            <div style="{militar_class} margin: 4px 0;">{d['impresso_nome']}</div>
            {swap_html}
          </div>
          <div style="background: rgba(15, 23, 42, 0.6); padding: 8px; font-size: 11px; color: #94A3B8; text-align: center; border-top: 1px solid rgba(255,255,255,0.05);">
            {obs_text}
          </div>
        </div>
        """)

    grid_content = "".join(cols_html)

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: #0B132B;
    color: #FFFFFF;
    font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Arial, sans-serif;
    padding: 30px;
    width: 1600px;
    height: 900px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
  }}
  .main-card {{
    background: #0F172A;
    border: 2px solid #1E3A8A;
    border-radius: 16px;
    padding: 24px 30px;
    box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.7);
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
  }}
  .header {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-bottom: 2px solid #1E293B;
    padding-bottom: 16px;
  }}
  .header-left {{
    display: flex;
    align-items: center;
    gap: 20px;
  }}
  .title-h1 {{
    font-size: 24px;
    font-weight: 800;
    letter-spacing: -0.5px;
    color: #F8FAFC;
  }}
  .title-sub {{
    font-size: 14px;
    color: #94A3B8;
    margin-top: 2px;
  }}
  .badge-om {{
    background: #14532D;
    color: #86EFAC;
    border: 1px solid #22C55E;
    font-size: 13px;
    font-weight: 800;
    padding: 6px 14px;
    border-radius: 30px;
    text-transform: uppercase;
  }}
  .grid-days {{
    display: flex;
    gap: 12px;
    margin: 20px 0;
    flex: 1;
  }}
  .footer-note {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-top: 14px;
    border-top: 1px solid #1E293B;
    font-size: 11px;
    color: #64748B;
    font-weight: 600;
  }}
</style>
</head>
<body>
  <div class="main-card">
    <div class="header">
      <div class="header-left">
        <div>
          <div class="title-h1">BATALHÃO CENTRAL DE MANUTENÇÃO E SUPRIMENTO (BCMS)</div>
          <div class="title-sub">{semana_ano}ª SEMANA &bull; PREVISÃO DA ESCALA DE SERVIÇO ({data_inicio} A {data_fim}) &bull; SGT DE DIA</div>
        </div>
      </div>
      <div>
        <span class="badge-om">UASG 160329 &bull; SERVIÇO OFICIAL</span>
      </div>
    </div>

    <div class="grid-days">
      {grid_content}
    </div>

    <div class="footer-note">
      <div>BATALHÃO CENTRAL DE MANUTENÇÃO E SUPRIMENTO &bull; BASE DE APOIO LOGÍSTICO DO EXÉRCITO</div>
      <div>EscalaPro BCMS &bull; Previsão Gerada Automaticamente pelo Sistema</div>
    </div>
  </div>
</body>
</html>"""

    browser_exe = _get_browser_path()
    if browser_exe:
        temp_dir = Path(tempfile.gettempdir()) / "escalapro_png"
        temp_dir.mkdir(parents=True, exist_ok=True)
        uid = uuid.uuid4().hex
        temp_html = temp_dir / f"escala_{uid}.html"
        temp_png = temp_dir / f"escala_{uid}.png"

        temp_html.write_text(html, encoding="utf-8")

        cmd = [
            browser_exe,
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            "--hide-scrollbars",
            f"--screenshot={str(temp_png)}",
            "--window-size=1600,900",
            f"file:///{str(temp_html).replace(chr(92), '/')}",
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            if temp_png.exists() and temp_png.stat().st_size > 0:
                data = temp_png.read_bytes()
                output = io.BytesIO(data)
                output.seek(0)
                return output
        finally:
            if temp_html.exists():
                temp_html.unlink(missing_ok=True)
            if temp_png.exists():
                temp_png.unlink(missing_ok=True)

    # Fallback Pillow
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (1600, 900), color=(11, 19, 43))
    draw = ImageDraw.Draw(img)
    draw.rectangle([(20, 20), (1580, 880)], outline=(30, 58, 138), width=3)
    draw.text((50, 40), f"BCMS - ESCALA DA {semana_ano}ª SEMANA ({data_inicio} a {data_fim})", fill=(255, 255, 255))
    output = io.BytesIO()
    img.save(output, format="PNG")
    output.seek(0)
    return output


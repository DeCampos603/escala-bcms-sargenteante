# 🎖️ EscalaPro BCMS — Módulo Sargenteante & Previsão de Escalas

[![Apresentação Online](https://img.shields.io/badge/Apresenta%C3%A7%C3%A3o-GitHub%20Pages-success?style=for-the-badge&logo=github)](https://decampos603.github.io/escala-bcms-sargenteante/)
[![Testes Automatizados](https://img.shields.io/badge/Testes-15%2F15%20Passing-brightgreen?style=for-the-badge&logo=pytest)](tests/)
[![Python Version](https://img.shields.io/badge/Python-3.14-blue?style=for-the-badge&logo=python)](app/)
[![Frontend](https://img.shields.io/badge/UI-HTML5%20%2F%20CSS%20Vanilla%2060fps-orange?style=for-the-badge)](index.html)

**Unidade Militar:** Batalhão Central de Manutenção e Suprimento (BCMS — UASG 160329)  
**Organização Superior:** Base de Apoio Logístico do Exército (Ba Ap Log Ex)  
**Posto Operacional:** 3º Sargento de Dia (com suporte a Comandante da Guarda e Oficiais)  
**Apresentação Interativa:** 👉 **[https://decampos603.github.io/escala-bcms-sargenteante/](https://decampos603.github.io/escala-bcms-sargenteante/)**

---

## 🌟 Visão Geral & Módulo da Sargenteação

O **EscalaPro BCMS** é uma solução completa para a gestão, previsão matemática e controle da escala de serviço militar, com interface especializada para a **Sargenteação**:

- ⠿ **Lista Arrastável de Antiguidade (Drag-and-Drop):** Reordenação interativa da precedência hierárquica do efetivo arrastando a alça `⠿` ou através dos botões de ajuste fino `▲ / ▼`, sincronizando instantaneamente no banco de dados SQLite e no cliente.
- ⚡ **Previsão Automática de 1 ou 2 Semanas:** Motor matemático que escala automaticamente quem possui maior tempo de folga, respeitando o interstício de 48h e as regras de Fila Dupla (Preta e Vermelha).
- 🔄 **Doutrina Militar da Fila Dupla:** Gestão independente entre dias úteis (**Escala Preta**) e fins de semana/feriados (**Escala Vermelha**).
- ✍️ **Registro Real de Trocas a Caneta:** Substituições operacionais são registradas sem alterar a folga oficial do militar impresso, preservando o direito de descanso e a justiça do rodízio.
- 🏖️ **Gestão de Afastamentos:** Férias, dispensas médicas (LTS) e missões externas removem o militar automaticamente das previsões durante o período.
- 📊 **Folgômetro em Tempo Real:** Visualização exata de quantos dias cada militar está de folga para cada escala.
- 🌐 **Modo Apresentação Standalone (GitHub Pages):** Opera 100% no navegador para demonstração sem requerer instalação ou servidor ativo.

---

## 📸 Base Histórica Consolidada (Semanas 37 a 42 de 2026)

O sistema conta com o histórico oficial de 42 dias corridos (10/09 a 21/10/2026):
- **28 3º Sargentos** ativos com ordem rigorosa de antiguidade e controle de folgas.
- **Novos Sargentos Integrados:** `3º Sgt SCHWEGER` (27º) e `3º Sgt PONCIANO` (28º).
- **Semana 41 (Oficial):** Permutas a caneta consolidadas (10/10 SAB: BARAUNA ➜ ANDRESSA; 11/10 DOM: SOUSA MOURA ➜ DE CAMPOS; 14/10 QUA: SOUSA MOURA titular).
- **Semana 42 (Nova Escala):** Cadastrada com os 7 dias completos (15/10 a 21/10).

---

## 🚀 Como Executar

### 1. Acesso Online (Sem Instalação)
Abra a apresentação pública diretamente no navegador:
👉 **[https://decampos603.github.io/escala-bcms-sargenteante/](https://decampos603.github.io/escala-bcms-sargenteante/)**

### 2. Início Rápido Local (Windows)
Dê dois cliques no arquivo:
```bat
iniciar.bat
```
O servidor FastAPI local iniciará na porta `8770` e abrirá `http://127.0.0.1:8770/sargenteante`.

### 3. Execução Manual via Terminal
```bash
py -3 -m uvicorn app.main:app --host 127.0.0.1 --port 8770 --reload
```

### 4. Suíte de Testes Automatizados (TDD)
```bash
py -3 -m pytest tests -v
```
*(15 testes cobrindo todas as regras de negócio, interstício de 48h, folgas e reordenação)*

---

## 🏛️ Estrutura do Projeto

```
Escala-Servico-BCMS/
├── index.html               # Interface principal de Apresentação (Modelo Sargenteante)
├── brasao.svg               # Brasão oficial do Exército Brasileiro
├── dados_apresentacao.json  # Base de dados estática para demonstração no GitHub Pages
├── css/
│   └── app.css              # Design System militar tático com drag-and-drop
├── js/
│   └── sargenteante.js      # Motor reativo, drag-and-drop e sincronização
├── app/
│   ├── db.py                # Conexão SQLite e migrações automáticas
│   ├── main.py              # API REST FastAPI e rotas de reordenação
│   ├── regras.py            # Motor algorítmico de previsão, folgas e interstício 48h
│   ├── relatorios.py        # Exportação de planilhas Excel (.xlsx) e relatórios
│   └── servicos.py          # Lógica de negócio, reordenação atômica e auditoria
├── dados/
│   ├── carga_inicial.json   # Histórico oficial das semanas 37 a 42 e 28 sargentos
│   ├── feriados_2026.json   # Feriados nacionais e de expediente militar
│   └── escalas.db           # Banco SQLite com as 42 escalas gravadas
├── tests/
│   └── test_escalas.py      # 15 testes automatizados (100% passing)
├── CLAUDE.md                # Diretrizes doutrinárias e regras inegociáveis
├── README.md                # Manual executivo de apresentação
└── iniciar.bat              # Script de inicialização rápida
```

---

## ⚖️ Conformidade Militar & Doutrina

- **RISG (Regulamento Interno e dos Serviços Gerais):** Cumprimento estrito do interstício de 48h e ordem de folga.
- **Transparência & Justiça de Escala:** Folgômetro visível para toda a subunidade e auditabilidade das trocas.

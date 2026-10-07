/**
 * ESCALAPRO BCMS - MÓDULO DA SARGENTEAÇÃO
 * Interface operacional focada no Sargenteante:
 * - Sem contabilidade de permutas (apenas registro direto de quem assumiu)
 * - Previsão flexível de até 2 semanas (7 ou 14 dias)
 * - Seleção dinâmica de dias entre Preta e Vermelha
 * - Gestão completa do efetivo (Adicionar e Excluir militares)
 */

const API_BASE = '/api';

// Estado Reativo do Sargenteante
const state = {
  activeTab: 'tab-sgtte-escala',
  semanaSelecionada: 41,
  semanasDisponiveis: [],
  escalaAtual: null,
  dashboard: null,
  militares: [],
  afastamentos: [],
  diaParaTroca: null,
  previsaoCalculada: null,
  previsaoHorizonte: 1, // 1 ou 2 semanas
  previsaoCustomTipos: {}, // { 'YYYY-MM-DD': 'PRETA' | 'VERMELHA' }
  militarParaExcluir: null,
  escalasCache: {},
  modoApresentacao: false,
};

// Inicialização
document.addEventListener('DOMContentLoaded', async () => {
  setupTabs();
  setupEventListeners();
  await carregarDadosIniciais();
});

async function carregarDadosIniciais() {
  mostrarLoading(true);
  try {
    // Tenta carregar via API REST FastAPI local
    const testApi = await fetch(`${API_BASE}/dashboard`).catch(() => null);

    if (testApi && testApi.ok) {
      await Promise.all([
        carregarDashboard(),
        carregarSemanas(),
        carregarMilitares(),
        carregarAfastamentos(),
      ]);

      if (state.semanasDisponiveis.length > 0) {
        const ultima = state.semanasDisponiveis[state.semanasDisponiveis.length - 1];
        state.semanaSelecionada = ultima.semana_ano;
      }
      await carregarEscalaSemana(state.semanaSelecionada);
    } else {
      // Fallback: Modo Apresentação Estática (GitHub Pages / Offline)
      console.info('API local indisponível. Carregando dados estáticos de apresentação (dados_apresentacao.json)...');
      await carregarModoApresentacaoEstatico();
    }
  } catch (err) {
    console.warn('Erro ao inicializar via API, ativando fallback estático:', err);
    await carregarModoApresentacaoEstatico();
  } finally {
    mostrarLoading(false);
  }
}

async function carregarModoApresentacaoEstatico() {
  state.modoApresentacao = true;
  try {
    const res = await fetch('./dados_apresentacao.json');
    if (!res.ok) throw new Error('Arquivo de dados de apresentação não encontrado.');
    const dados = await res.json();

    state.dashboard = dados.dashboard;
    state.semanasDisponiveis = dados.semanas;
    state.escalasCache = dados.escalas || {};
    state.militares = dados.militares || [];
    state.afastamentos = dados.afastamentos || [];

    // Restaurar reordenação de antiguidade do LocalStorage se existir
    try {
      const salva = localStorage.getItem('escalapro_sgtte_militares_ordem');
      if (salva) {
        const ordemIds = JSON.parse(salva);
        if (Array.isArray(ordemIds) && ordemIds.length > 0) {
          const mapaPos = new Map(ordemIds.map((id, idx) => [id, idx + 1]));
          state.militares.forEach(m => {
            if (mapaPos.has(m.id)) {
              m.antiguidade = mapaPos.get(m.id);
            }
          });
        }
      }
    } catch (e) {
      console.warn('Erro ao ler ordem do localStorage:', e);
    }

    renderizarDashboard();
    renderizarBotoesSemanas();
    renderizarTabelaFolgas();
    renderizarTabelaMilitares();
    renderizarTabelaAfastamentos();
    popularSelectMilitares();
    popularSelectMilitaresAfastamento();

    if (state.semanasDisponiveis.length > 0) {
      const ultima = state.semanasDisponiveis[state.semanasDisponiveis.length - 1];
      state.semanaSelecionada = ultima.semana_ano;
      await carregarEscalaSemana(ultima.semana_ano);
    }

    const badgeStatus = document.getElementById('antiguidade-status-badge');
    if (badgeStatus) {
      badgeStatus.innerHTML = '<span style="color:#38BDF8; font-weight:700;">🌐 Modo Apresentação Online Ativo</span>';
    }
    mostrarToast('EscalaPro BCMS — Apresentação Ativa (Semanas 37 a 42)!', 'info');
  } catch (e) {
    console.error('Falha crítica ao carregar dados estáticos:', e);
    mostrarToast('Falha ao carregar dados da apresentação.', 'danger');
  }
}

// --- Funções de API & Fallback ---

async function carregarDashboard() {
  const res = await fetch(`${API_BASE}/dashboard`);
  if (!res.ok) return;
  state.dashboard = await res.json();
  renderizarDashboard();
}

async function carregarSemanas() {
  const res = await fetch(`${API_BASE}/semanas`);
  if (!res.ok) return;
  state.semanasDisponiveis = await res.json();
  renderizarBotoesSemanas();
}

async function carregarEscalaSemana(semanaAno) {
  try {
    let dadosSemana = null;
    if (!state.modoApresentacao) {
      const res = await fetch(`${API_BASE}/escala/${semanaAno}`).catch(() => null);
      if (res && res.ok) {
        dadosSemana = await res.json();
      }
    }

    // Se a API não respondeu ou estamos em modo apresentação, busca do cache
    if (!dadosSemana && state.escalasCache[String(semanaAno)]) {
      dadosSemana = state.escalasCache[String(semanaAno)];
    }

    if (!dadosSemana) {
      throw new Error(`Semana ${semanaAno} não encontrada`);
    }

    state.escalaAtual = dadosSemana;
    state.semanaSelecionada = semanaAno;
    renderizarBotoesSemanas();
    renderizarQuadroSemanal();
    renderizarDashboard();
  } catch (err) {
    console.error('Erro ao buscar escala:', err);
    mostrarToast(`Erro ao carregar Semana ${semanaAno}`, 'danger');
  }
}

async function carregarMilitares() {
  const res = await fetch(`${API_BASE}/militares`);
  if (!res.ok) return;
  state.militares = await res.json();
  renderizarTabelaFolgas();
  renderizarTabelaMilitares();
  popularSelectMilitares();
}

async function carregarAfastamentos() {
  const res = await fetch(`${API_BASE}/afastamentos`);
  if (!res.ok) return;
  state.afastamentos = await res.json();
  renderizarTabelaAfastamentos();
  popularSelectMilitaresAfastamento();
}

// --- Renderização da Interface ---

function renderizarDashboard() {
  const d = state.dashboard;
  if (!d) return;

  const ef = document.getElementById('kpi-sgtte-efetivo');
  if (ef) ef.innerText = d.total_efetivo || '0';

  const esc = document.getElementById('kpi-sgtte-escalas');
  if (esc) esc.innerText = d.total_escalas_registradas || '0';

  const sem = document.getElementById('kpi-sgtte-semana-atual');
  if (sem) sem.innerText = `${state.semanaSelecionada || '--'}ª Sem`;

  const af = document.getElementById('kpi-sgtte-afastados');
  if (af) af.innerText = d.afastados_hoje || '0';
}

function renderizarBotoesSemanas() {
  const container = document.getElementById('sgtte-week-buttons-container');
  if (!container) return;

  container.innerHTML = '';
  state.semanasDisponiveis.forEach(sem => {
    const btn = document.createElement('button');
    btn.className = `week-badge-btn ${sem.semana_ano === state.semanaSelecionada ? 'active' : ''}`;
    btn.innerHTML = `<strong>${sem.semana_ano}ª Sem</strong> <span style="font-size:0.7em; opacity:0.8;">(${sem.data_inicio.slice(5)})</span>`;
    btn.onclick = () => carregarEscalaSemana(sem.semana_ano);
    container.appendChild(btn);
  });
}

function renderizarQuadroSemanal() {
  const esc = state.escalaAtual;
  if (!esc || !esc.dias) return;

  document.getElementById('sgtte-sheet-title-text').innerText = `${esc.semana_ano}ª SEMANA - PREVISÃO DA ESCALA DE SERVIÇO`;
  document.getElementById('sgtte-sheet-period-text').innerText = `Período Oficial: ${formatarDataBr(esc.data_inicio)} a ${formatarDataBr(esc.data_fim)}`;

  const grid = document.getElementById('sgtte-schedule-grid-container');
  grid.innerHTML = '';

  esc.dias.forEach(dia => {
    const isRed = dia.tipo_escala === 'VERMELHA';
    const hasSwap = !!dia.caneta_nome;

    const col = document.createElement('div');
    col.className = `day-column ${isRed ? 'is-red' : ''}`;

    const diaNum = dia.data.split('-')[2];
    col.innerHTML = `
      <div class="day-header">
        <div class="day-name">${dia.dia_semana} (${diaNum})</div>
        <div class="day-date">${formatarDataBr(dia.data)}</div>
        <div style="margin-top: 4px;">
          <button class="type-toggle-btn ${isRed ? 'vermelha' : 'preta'}" onclick="alternarTipoDia(${dia.id}, '${isRed ? 'PRETA' : 'VERMELHA'}')" title="Clique para alternar entre Preta e Vermelha">
            ${isRed ? '🔴 VERMELHA' : '⚫ PRETA'} ⇄
          </button>
        </div>
      </div>

      <div class="duty-slot ${hasSwap ? 'has-swap' : ''}">
        <span class="rank-label">${dia.impresso_graduacao}</span>
        <div class="military-name ${hasSwap ? 'struck' : ''}">${dia.impresso_nome}</div>

        ${hasSwap ? `
          <div class="pen-swap-badge" style="background: rgba(59, 130, 246, 0.15); border-color: #3B82F6;">
            <span class="pen-label" style="color: #93C5FD;">Assumiu o Serviço</span>
            <span class="pen-name" style="color: #FFFFFF;">${dia.caneta_graduacao} ${dia.caneta_nome}</span>
            <div style="font-size:0.68em; color:#93C5FD; margin-top:2px;">${dia.permuta_motivo || 'Troca Registrada'}</div>
          </div>
        ` : ''}

        <div style="display:flex; gap:4px; justify-content:center; margin-top: 8px;">
          <button class="slot-action-btn" onclick="abrirModalTrocaSgtte(${dia.id})" title="Marcar ou alterar troca de serviço">
            🖋️ ${hasSwap ? 'Alterar Troca' : 'Marcar Troca'}
          </button>
          ${hasSwap ? `
            <button class="slot-action-btn" onclick="desfazerTrocaSgtte(${dia.id})" title="Cancelar troca e voltar ao titular" style="color:#F87171;">
              ✕
            </button>
          ` : ''}
        </div>
      </div>

      <div class="day-footer">
        ${dia.feriado_descricao ? `🎉 <strong>${dia.feriado_descricao}</strong>` : (dia.observacoes || (isRed ? 'Final de Semana / Feriado' : 'Expediente Normal'))}
      </div>
    `;

    grid.appendChild(col);
  });
}

window.alternarTipoDia = async function(diaId, novoTipo) {
  try {
    const res = await fetch(`${API_BASE}/escala/dia/${diaId}/tipo`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tipo_escala: novoTipo }),
    });
    if (!res.ok) throw new Error('Falha ao alterar tipo do dia.');
    mostrarToast(`Dia alterado para Escala ${novoTipo}!`, 'success');
    await carregarEscalaSemana(state.semanaSelecionada);
  } catch (err) {
    mostrarToast(err.message, 'danger');
  }
};

function renderizarTabelaFolgas() {
  const tbody = document.getElementById('tbody-sgtte-folgas');
  if (!tbody) return;

  tbody.innerHTML = '';
  const sorted = [...state.militares].sort((a, b) => b.folga_preta - a.folga_preta);

  sorted.forEach(m => {
    const tr = document.createElement('tr');

    let badgeClassPreta = 'green';
    if (m.folga_preta < 5) badgeClassPreta = 'red';
    else if (m.folga_preta < 15) badgeClassPreta = 'amber';

    let badgeClassVerm = 'green';
    if (m.folga_vermelha < 7) badgeClassVerm = 'red';
    else if (m.folga_vermelha < 20) badgeClassVerm = 'amber';

    const textoFolgaPreta = m.folga_preta >= 900 ? 'Sem registro (>30d)' : `${m.folga_preta} dias`;
    const textoFolgaVerm = m.folga_vermelha >= 900 ? 'Sem registro (>30d)' : `${m.folga_vermelha} dias`;

    tr.innerHTML = `
      <td><strong>${m.antiguidade}º</strong></td>
      <td><strong>${m.posto_graduacao} ${m.nome_guerra}</strong></td>
      <td>
        <span class="rest-badge ${badgeClassPreta}">
          🌙 ${textoFolgaPreta}
        </span>
        <div style="font-size:0.75em; color:var(--text-muted); margin-top:2px;">Último: ${m.ult_servico_preta ? formatarDataBr(m.ult_servico_preta) : 'N/D'}</div>
      </td>
      <td>
        <span class="rest-badge ${badgeClassVerm}">
          ☀️ ${textoFolgaVerm}
        </span>
        <div style="font-size:0.75em; color:var(--text-muted); margin-top:2px;">Último: ${m.ult_servico_vermelha ? formatarDataBr(m.ult_servico_vermelha) : 'N/D'}</div>
      </td>
      <td>
        ${m.afastamento_ativo ? `
          <span style="background:rgba(239,68,68,0.2); color:#F87171; padding:2px 8px; border-radius:4px; font-size:0.75em; font-weight:700;">
            ${m.afastamento_ativo.motivo} (${m.afastamento_ativo.periodo})
          </span>
        ` : `
          <span style="color:#34D399; font-size:0.8em; font-weight:600;">✓ Pronto p/ Escala</span>
        `}
      </td>
    `;
    tbody.appendChild(tr);
  });
}

let draggedRow = null;

function renderizarTabelaMilitares() {
  const tbody = document.getElementById('tbody-sgtte-militares');
  if (!tbody) return;

  tbody.innerHTML = '';
  const sorted = [...state.militares].sort((a, b) => a.antiguidade - b.antiguidade);

  sorted.forEach((m, idx) => {
    const tr = document.createElement('tr');
    tr.className = 'draggable-row';
    tr.draggable = true;
    tr.dataset.id = m.id;
    tr.dataset.antiguidade = m.antiguidade;

    tr.innerHTML = `
      <td class="drag-handle" title="Segure e arraste para reordenar antiguidade" style="text-align: center; cursor: grab;">⠿</td>
      <td style="text-align: center;"><span class="antiguidade-badge">${m.antiguidade || (idx + 1)}º</span></td>
      <td>${m.posto_graduacao}</td>
      <td><strong>${m.nome_guerra}</strong></td>
      <td>BCMS</td>
      <td><span style="color: #60A5FA; font-weight: 700;">${m.folga_preta >= 900 ? '>30d' : m.folga_preta + 'd'}</span></td>
      <td><span style="color: #F87171; font-weight: 700;">${m.folga_vermelha >= 900 ? '>30d' : m.folga_vermelha + 'd'}</span></td>
      <td>
        <span style="color: #34D399; font-size: 0.8rem; font-weight: 700;">● Ativo</span>
      </td>
      <td style="text-align: center; white-space: nowrap;">
        <button class="btn-nudge" title="Mover para cima (mais antigo)" onclick="moverAntiguidade(${m.id}, -1)">▲</button>
        <button class="btn-nudge" title="Mover para baixo (mais moderno)" onclick="moverAntiguidade(${m.id}, 1)">▼</button>
        <button class="btn btn-secondary" style="padding: 0.25rem 0.5rem; font-size: 0.72rem; border-color: #EF4444; color: #F87171; margin-left: 4px;" onclick="abrirModalExcluirMilitar(${m.id}, '${m.posto_graduacao} ${m.nome_guerra}')">
          🗑️
        </button>
      </td>
    `;

    // Eventos de Drag & Drop HTML5
    tr.addEventListener('dragstart', (e) => {
      draggedRow = tr;
      tr.classList.add('is-dragging');
      e.dataTransfer.effectAllowed = 'move';
      e.dataTransfer.setData('text/plain', String(m.id));
    });

    tr.addEventListener('dragend', () => {
      tr.classList.remove('is-dragging');
      tbody.querySelectorAll('.draggable-row').forEach(row => {
        row.classList.remove('drop-target-above', 'drop-target-below');
      });
      draggedRow = null;
    });

    tr.addEventListener('dragover', (e) => {
      e.preventDefault();
      e.dataTransfer.dropEffect = 'move';
      if (!draggedRow || draggedRow === tr) return;

      const rect = tr.getBoundingClientRect();
      const mid = rect.top + rect.height / 2;
      if (e.clientY < mid) {
        tr.classList.add('drop-target-above');
        tr.classList.remove('drop-target-below');
      } else {
        tr.classList.add('drop-target-below');
        tr.classList.remove('drop-target-above');
      }
    });

    tr.addEventListener('dragleave', () => {
      tr.classList.remove('drop-target-above', 'drop-target-below');
    });

    tr.addEventListener('drop', (e) => {
      e.preventDefault();
      tr.classList.remove('drop-target-above', 'drop-target-below');
      if (!draggedRow || draggedRow === tr) return;

      const rect = tr.getBoundingClientRect();
      const mid = rect.top + rect.height / 2;
      if (e.clientY < mid) {
        tbody.insertBefore(draggedRow, tr);
      } else {
        tbody.insertBefore(draggedRow, tr.nextSibling);
      }
      atualizarBadgesAposReordenacao();
    });

    tbody.appendChild(tr);
  });
}

function atualizarBadgesAposReordenacao() {
  const tbody = document.getElementById('tbody-sgtte-militares');
  if (!tbody) return;

  const rows = tbody.querySelectorAll('tr.draggable-row');
  rows.forEach((row, idx) => {
    const badge = row.querySelector('.antiguidade-badge');
    if (badge) badge.innerText = `${idx + 1}º`;
  });

  const btnSalvar = document.getElementById('btn-salvar-antiguidade');
  if (btnSalvar) btnSalvar.style.display = 'inline-flex';

  const statusBadge = document.getElementById('antiguidade-status-badge');
  if (statusBadge) {
    statusBadge.innerHTML = '<span style="color: #F59E0B; font-weight: 700;">⚠️ Nova antiguidade pendente de salvamento</span>';
  }
}

window.moverAntiguidade = function(militarId, direcao) {
  const tbody = document.getElementById('tbody-sgtte-militares');
  if (!tbody) return;

  const row = tbody.querySelector(`tr[data-id="${militarId}"]`);
  if (!row) return;

  if (direcao === -1 && row.previousElementSibling) {
    tbody.insertBefore(row, row.previousElementSibling);
    atualizarBadgesAposReordenacao();
  } else if (direcao === 1 && row.nextElementSibling) {
    tbody.insertBefore(row, row.nextElementSibling.nextSibling);
    atualizarBadgesAposReordenacao();
  }
};

window.salvarOrdemAntiguidade = async function() {
  const tbody = document.getElementById('tbody-sgtte-militares');
  if (!tbody) return;

  const rows = Array.from(tbody.querySelectorAll('tr[data-id]'));
  const ordemIds = rows.map(r => parseInt(r.dataset.id));

  const btnSalvar = document.getElementById('btn-salvar-antiguidade');
  const statusBadge = document.getElementById('antiguidade-status-badge');

  if (btnSalvar) btnSalvar.disabled = true;

  try {
    const res = await fetch(`${API_BASE}/militares/reordenar-antiguidade`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ordem_ids: ordemIds }),
    });

    if (!res.ok) {
      throw new Error('Falha no servidor ao salvar antiguidade.');
    }

    // Sucesso via API
    ordemIds.forEach((id, idx) => {
      const mil = state.militares.find(m => m.id === id);
      if (mil) mil.antiguidade = idx + 1;
    });

    mostrarToast('Nova antiguidade dos militares gravada com sucesso!', 'success');
    if (btnSalvar) {
      btnSalvar.style.display = 'none';
      btnSalvar.disabled = false;
    }
    if (statusBadge) {
      statusBadge.innerHTML = '<span style="color: #10B981; font-weight: 700;">✓ Ordem sincronizada com o banco de dados</span>';
    }
    popularSelectMilitares();
  } catch (err) {
    console.warn('Erro na requisição da API de reordenação, ativando fallback local:', err);

    // Fallback: modo estático / GitHub Pages / LocalStorage
    ordemIds.forEach((id, idx) => {
      const mil = state.militares.find(m => m.id === id);
      if (mil) mil.antiguidade = idx + 1;
    });

    try {
      localStorage.setItem('escalapro_sgtte_militares_ordem', JSON.stringify(ordemIds));
    } catch (e) {
      console.warn('Erro ao salvar no localStorage:', e);
    }

    mostrarToast('Nova antiguidade salva com sucesso (Modo Apresentação)!', 'success');
    if (btnSalvar) {
      btnSalvar.style.display = 'none';
      btnSalvar.disabled = false;
    }
    if (statusBadge) {
      statusBadge.innerHTML = '<span style="color: #38BDF8; font-weight: 700;">✓ Ordem salva localmente (Modo Apresentação)</span>';
    }
    popularSelectMilitares();
  }
};

function renderizarTabelaAfastamentos() {
  const tbody = document.getElementById('tbody-sgtte-afastamentos');
  if (!tbody) return;

  tbody.innerHTML = '';
  if (state.afastamentos.length === 0) {
    tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; color:var(--text-muted);">Nenhum militar afastado no momento.</td></tr>';
    return;
  }

  state.afastamentos.forEach(a => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><strong>${a.posto_graduacao} ${a.nome_guerra}</strong></td>
      <td><span style="background:rgba(239,68,68,0.15); color:#F87171; padding:2px 8px; border-radius:4px; font-weight:700; font-size:0.8rem;">${a.motivo}</span></td>
      <td>${formatarDataBr(a.data_inicio)}</td>
      <td>${formatarDataBr(a.data_fim)}</td>
      <td style="color:var(--text-muted);">${a.observacao || '--'}</td>
    `;
    tbody.appendChild(tr);
  });
}

// --- Gestão de Militares (Adicionar / Excluir) ---

window.abrirModalNovoMilitar = function() {
  const modal = document.getElementById('modal-sgtte-novo-militar');
  document.getElementById('novo-militar-nome').value = '';
  document.getElementById('novo-militar-antiguidade').value = state.militares.length + 1;
  modal.classList.add('active');
};

window.fecharModalNovoMilitar = function() {
  document.getElementById('modal-sgtte-novo-militar').classList.remove('active');
};

window.salvarNovoMilitar = async function() {
  const graduacao = document.getElementById('novo-militar-graduacao').value;
  const nomeGuerra = document.getElementById('novo-militar-nome').value.trim().toUpperCase();
  const antiguidade = parseInt(document.getElementById('novo-militar-antiguidade').value) || 999;
  const subunidade = document.getElementById('novo-militar-subunidade').value.trim() || 'BCMS';

  if (!nomeGuerra) {
    mostrarToast('Por favor, informe o Nome de Guerra do militar.', 'warning');
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/militares`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        posto_graduacao: graduacao,
        nome_guerra: nomeGuerra,
        antiguidade_ordem: antiguidade,
        escala_habilitada: 'SGT_DE_DIA',
        subunidade: subunidade,
      }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Erro ao cadastrar militar.');
    }

    mostrarToast(`Militar ${graduacao} ${nomeGuerra} cadastrado com sucesso!`, 'success');
    fecharModalNovoMilitar();
    await carregarMilitares();
    await carregarDashboard();
  } catch (err) {
    mostrarToast(err.message, 'danger');
  }
};

window.abrirModalExcluirMilitar = function(militarId, nomeCompleto) {
  state.militarParaExcluir = { id: militarId, nome: nomeCompleto };
  document.getElementById('excluir-militar-nome-destaque').innerText = nomeCompleto;
  document.getElementById('modal-sgtte-excluir-militar').classList.add('active');
};

window.fecharModalExcluirMilitar = function() {
  state.militarParaExcluir = null;
  document.getElementById('modal-sgtte-excluir-militar').classList.remove('active');
};

window.confirmarExcluirMilitar = async function() {
  if (!state.militarParaExcluir) return;

  try {
    const res = await fetch(`${API_BASE}/militares/${state.militarParaExcluir.id}`, {
      method: 'DELETE',
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Erro ao excluir militar.');
    }

    const data = await res.json();
    mostrarToast(data.mensagem || 'Militar excluído do efetivo.', 'success');
    fecharModalExcluirMilitar();
    await carregarMilitares();
    await carregarDashboard();
  } catch (err) {
    mostrarToast(err.message, 'danger');
  }
};

// --- Trocas de Serviço Simples (Sem permutas) ---

window.abrirModalTrocaSgtte = function(escalaDiaId) {
  const dia = state.escalaAtual.dias.find(d => d.id === escalaDiaId);
  if (!dia) return;

  state.diaParaTroca = dia;
  document.getElementById('modal-sgtte-troca-dia-info').innerText = `${dia.dia_semana} (${formatarDataBr(dia.data)}) - Escala ${dia.tipo_escala}`;
  document.getElementById('modal-sgtte-troca-titular-nome').innerText = `${dia.impresso_graduacao} ${dia.impresso_nome}`;

  popularSelectMilitares(dia.impresso_id);

  const select = document.getElementById('modal-sgtte-troca-substituto');
  if (dia.caneta_id) select.value = dia.caneta_id;
  else select.value = '';

  document.getElementById('modal-sgtte-troca-motivo').value = dia.permuta_motivo || '';
  document.getElementById('modal-sgtte-troca').classList.add('active');
};

window.fecharModalTrocaSgtte = function() {
  state.diaParaTroca = null;
  document.getElementById('modal-sgtte-troca').classList.remove('active');
};

window.confirmarTrocaSgtte = async function() {
  if (!state.diaParaTroca) return;

  const substitutoId = document.getElementById('modal-sgtte-troca-substituto').value;
  const motivo = document.getElementById('modal-sgtte-troca-motivo').value.trim() || 'Troca de Serviço';

  if (!substitutoId) {
    mostrarToast('Selecione o militar substituto que assumirá o serviço.', 'warning');
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/trocas`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        escala_dia_id: state.diaParaTroca.id,
        militar_substituto_id: parseInt(substitutoId),
        motivo: motivo,
        autorizado_por: 'Sargenteante de Dia',
      }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Erro ao registrar troca');
    }

    mostrarToast('Troca de serviço registrada com sucesso!', 'success');
    fecharModalTrocaSgtte();
    await carregarEscalaSemana(state.semanaSelecionada);
    await carregarDashboard();
  } catch (err) {
    mostrarToast(err.message, 'danger');
  }
};

window.desfazerTrocaSgtte = async function(escalaDiaId) {
  try {
    const res = await fetch(`${API_BASE}/trocas/${escalaDiaId}`, { method: 'DELETE' });
    if (!res.ok) throw new Error('Erro ao desfazer troca');

    mostrarToast('Troca cancelada! O serviço retornou ao titular.', 'info');
    await carregarEscalaSemana(state.semanaSelecionada);
    await carregarDashboard();
  } catch (err) {
    mostrarToast(err.message, 'danger');
  }
};

// --- Previsão de até 2 Semanas com Seleção de Preta/Vermelha ---

window.abrirModalPrevisaoSgtte = function() {
  const modal = document.getElementById('modal-sgtte-previsao');
  const ultimaSem = state.semanasDisponiveis.length > 0
    ? state.semanasDisponiveis[state.semanasDisponiveis.length - 1]
    : { semana_ano: 42, data_fim: '2026-10-21' };
  const proximaSemana = ultimaSem.semana_ano + 1;
  document.getElementById('sgtte-prev-semana-num').value = proximaSemana;

  // Próxima quinta-feira após o último dia cadastrado (quarta-feira)
  const ultDataFim = new Date(ultimaSem.data_fim + 'T12:00:00');
  ultDataFim.setDate(ultDataFim.getDate() + 1);
  document.getElementById('sgtte-prev-data-inicio').value = ultDataFim.toISOString().split('T')[0];

  selecionarHorizonte(1);
  modal.classList.add('active');
};

window.fecharModalPrevisaoSgtte = function() {
  document.getElementById('modal-sgtte-previsao').classList.remove('active');
};

window.selecionarHorizonte = function(qtdSemanas) {
  state.previsaoHorizonte = qtdSemanas;
  document.getElementById('pill-1sem').classList.toggle('active', qtdSemanas === 1);
  document.getElementById('pill-2sem').classList.toggle('active', qtdSemanas === 2);
  atualizarDiasSetupPrevisao();
};

window.atualizarDiasSetupPrevisao = function() {
  const container = document.getElementById('sgtte-day-setup-container');
  if (!container) return;

  const dataInicioStr = document.getElementById('sgtte-prev-data-inicio').value;
  if (!dataInicioStr) return;

  const totalDias = 7 * state.previsaoHorizonte;
  const dtInicio = new Date(dataInicioStr + 'T12:00:00');

  container.innerHTML = '';
  state.previsaoCustomTipos = {};

  const nomesDias = ['DOM', 'SEG', 'TER', 'QUA', 'QUI', 'SEX', 'SAB'];

  for (let i = 0; i < totalDias; i++) {
    const dt = new Date(dtInicio);
    dt.setDate(dtInicio.getDate() + i);
    const dtStr = dt.toISOString().split('T')[0];
    const diaSemanaNum = dt.getDay();
    const diaSemanaNome = nomesDias[diaSemanaNum];

    // Por padrão: Sáb (6) e Dom (0) são VERMELHA; dias úteis são PRETA
    const tipoPadrao = (diaSemanaNum === 0 || diaSemanaNum === 6) ? 'VERMELHA' : 'PRETA';
    state.previsaoCustomTipos[dtStr] = tipoPadrao;

    const card = document.createElement('div');
    card.className = 'day-type-setup-card';
    card.id = `setup-card-${dtStr}`;

    const diaNum = dtStr.split('-')[2];
    card.innerHTML = `
      <div class="day-type-setup-title">${diaSemanaNome} (${diaNum})</div>
      <button type="button" class="type-toggle-btn ${tipoPadrao.toLowerCase()}" id="btn-toggle-setup-${dtStr}" onclick="toggleTipoDiaSetup('${dtStr}')">
        ${tipoPadrao === 'VERMELHA' ? '🔴 VERM' : '⚫ PRETA'}
      </button>
    `;
    container.appendChild(card);
  }
};

window.toggleTipoDiaSetup = function(dtStr) {
  const tipoAtual = state.previsaoCustomTipos[dtStr] || 'PRETA';
  const novoTipo = tipoAtual === 'PRETA' ? 'VERMELHA' : 'PRETA';
  state.previsaoCustomTipos[dtStr] = novoTipo;

  const btn = document.getElementById(`btn-toggle-setup-${dtStr}`);
  if (btn) {
    btn.className = `type-toggle-btn ${novoTipo.toLowerCase()}`;
    btn.innerText = novoTipo === 'VERMELHA' ? '🔴 VERM' : '⚫ PRETA';
  }
};

window.calcularPrevisaoSgtte = async function() {
  const semNum = parseInt(document.getElementById('sgtte-prev-semana-num').value);
  const dataInicio = document.getElementById('sgtte-prev-data-inicio').value;

  if (!semNum || !dataInicio) {
    mostrarToast('Preencha a semana e a data de início.', 'warning');
    return;
  }

  mostrarLoading(true);
  try {
    const res = await fetch(`${API_BASE}/previsao/calcular`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        semana_ano: semNum,
        data_inicio_quinta: dataInicio,
        posto_codigo: 'SGT_DE_DIA',
        qtd_semanas: state.previsaoHorizonte,
        custom_tipos_dias: state.previsaoCustomTipos,
      }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Erro ao calcular previsão.');
    }

    const data = await res.json();
    state.previsaoCalculada = data.previsao;
    renderizarPreviewPrevisaoSgtte(data.previsao);
  } catch (err) {
    mostrarToast(err.message, 'danger');
  } finally {
    mostrarLoading(false);
  }
};

function renderizarPreviewPrevisaoSgtte(previsao) {
  const tbody = document.getElementById('tbody-sgtte-preview-previsao');
  const container = document.getElementById('sgtte-previsao-preview-container');
  tbody.innerHTML = '';

  document.getElementById('sgtte-preview-titulo').innerText =
    `Resultado da Simulação (${previsao.length} Dias &bull; ${state.previsaoHorizonte} Semana(s)):`;

  previsao.forEach(p => {
    const tr = document.createElement('tr');
    const isRed = p.tipo_escala === 'VERMELHA';
    const folga = isRed ? p.folga_vermelha_acumulada : p.folga_preta_acumulada;

    tr.innerHTML = `
      <td><strong>${p.semana_ano}ª Sem</strong></td>
      <td><strong>${p.dia_semana}</strong> (${formatarDataBr(p.data)})</td>
      <td>
        <span class="badge-tag" style="${isRed ? 'background:#FEE2E2; color:#991B1B;' : 'background:#E2E8F0; color:#0F172A;'} font-size:0.75rem; font-weight:700; padding:2px 6px; border-radius:4px;">
          ${p.tipo_escala}
        </span>
      </td>
      <td><strong>${p.posto_graduacao} ${p.nome_guerra}</strong></td>
      <td><span style="color:#34D399; font-weight:700;">${folga >= 900 ? '>30 dias' : folga + ' dias'}</span></td>
    `;
    tbody.appendChild(tr);
  });

  container.style.display = 'block';
  document.getElementById('btn-sgtte-salvar-previsao').style.display = 'inline-flex';
}

window.salvarPrevisaoSgtte = async function() {
  if (!state.previsaoCalculada) return;

  mostrarLoading(true);
  try {
    const res = await fetch(`${API_BASE}/previsao/salvar`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ previsao: state.previsaoCalculada }),
    });

    if (!res.ok) throw new Error('Erro ao salvar previsão');

    mostrarToast(`Previsão aprovada e salva com sucesso na escala!`, 'success');
    const semanaSalva = state.previsaoCalculada[0].semana_ano;
    fecharModalPrevisaoSgtte();

    await carregarSemanas();
    await carregarEscalaSemana(semanaSalva);
    await carregarDashboard();
    await carregarMilitares();
  } catch (err) {
    mostrarToast(err.message, 'danger');
  } finally {
    mostrarLoading(false);
  }
};

// --- Afastamentos Modal ---

window.abrirModalNovoAfastamento = function() {
  document.getElementById('modal-sgtte-novo-afastamento').classList.add('active');
};

window.fecharModalNovoAfastamento = function() {
  document.getElementById('modal-sgtte-novo-afastamento').classList.remove('active');
};

window.salvarNovoAfastamento = async function() {
  const militarId = document.getElementById('afastamento-militar-select').value;
  const dataInicio = document.getElementById('afastamento-data-inicio').value;
  const dataFim = document.getElementById('afastamento-data-fim').value;
  const motivo = document.getElementById('afastamento-motivo').value;
  const obs = document.getElementById('afastamento-obs').value;

  if (!militarId || !dataInicio || !dataFim) {
    mostrarToast('Preencha o militar e as datas de início e término.', 'warning');
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/afastamentos`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        militar_id: parseInt(militarId),
        data_inicio: dataInicio,
        data_fim: dataFim,
        motivo: motivo,
        observacao: obs,
      }),
    });

    if (!res.ok) throw new Error('Erro ao cadastrar afastamento.');

    mostrarToast('Afastamento registrado!', 'success');
    fecharModalNovoAfastamento();
    await carregarAfastamentos();
    await carregarMilitares();
    await carregarDashboard();
  } catch (err) {
    mostrarToast(err.message, 'danger');
  }
};

function popularSelectMilitaresAfastamento() {
  const select = document.getElementById('afastamento-militar-select');
  if (!select) return;
  select.innerHTML = '<option value="">-- Selecione o Militar --</option>';
  state.militares.forEach(m => {
    const opt = document.createElement('option');
    opt.value = m.id;
    opt.innerText = `${m.posto_graduacao} ${m.nome_guerra}`;
    select.appendChild(opt);
  });
}

// --- Helpers e Exports ---

window.baixarExcel = function() {
  window.location.href = `${API_BASE}/exportar/excel/${state.semanaSelecionada}`;
};

window.baixarPngPrevisao = function() {
  const semana = state.semanaSelecionada || 41;
  mostrarToast(`Gerando imagem PNG da previsão da ${semana}ª Semana...`, 'info');
  const link = document.createElement('a');
  link.href = `${API_BASE}/exportar/png/${semana}`;
  link.download = `Previsao_Escala_BCMS_Semana_${semana}.png`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
};

function popularSelectMilitares(excluirId = null) {
  const select = document.getElementById('modal-sgtte-troca-substituto');
  if (!select) return;

  select.innerHTML = '<option value="">-- Selecione o Substituto --</option>';
  state.militares.forEach(m => {
    if (m.id === excluirId) return;
    const opt = document.createElement('option');
    opt.value = m.id;
    opt.innerText = `${m.posto_graduacao} ${m.nome_guerra} (Folga: ${m.folga_preta}d Preta / ${m.folga_vermelha}d Verm)`;
    select.appendChild(opt);
  });
}

function setupTabs() {
  const tabButtons = document.querySelectorAll('.tab-btn');
  tabButtons.forEach(btn => {
    btn.addEventListener('click', async () => {
      tabButtons.forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));

      btn.classList.add('active');
      const targetId = btn.dataset.tab;
      const targetPanel = document.getElementById(targetId);
      if (targetPanel) targetPanel.classList.add('active');
      state.activeTab = targetId;

      if (targetId.includes('folgas')) await carregarMilitares();
      if (targetId.includes('militares')) await carregarMilitares();
      if (targetId.includes('afastamentos')) await carregarAfastamentos();
    });
  });
}

function setupEventListeners() {
  const themeBtn = document.getElementById('btn-theme-toggle');
  if (themeBtn) {
    themeBtn.addEventListener('click', () => {
      const current = document.documentElement.getAttribute('data-theme') || 'dark';
      const next = current === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', next);
      themeBtn.innerText = next === 'dark' ? '☀️' : '🌙';
    });
  }
}

function formatarDataBr(dataStr) {
  if (!dataStr) return '';
  const parts = dataStr.split('-');
  if (parts.length === 3) return `${parts[2]}/${parts[1]}/${parts[0]}`;
  return dataStr;
}

function mostrarToast(mensagem, tipo = 'info') {
  const toast = document.getElementById('toast');
  if (!toast) return;

  toast.innerText = mensagem;
  toast.className = `toast-notification ${tipo} active`;

  setTimeout(() => {
    toast.classList.remove('active');
  }, 4000);
}

function mostrarLoading(mostrar) {
  const loader = document.getElementById('global-loader');
  if (loader) loader.style.display = mostrar ? 'flex' : 'none';
}

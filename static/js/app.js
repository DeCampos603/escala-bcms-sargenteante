/**
 * ESCALAPRO BCMS - CLIENTE JS MODERNO (ES MODULES)
 * Gestão Preditiva e Controle de Escalas de Serviço
 */

const API_BASE = '/api';

// Estado Reativo da Aplicação
const state = {
  activeTab: 'escala',
  semanaSelecionada: 41,
  semanasDisponiveis: [],
  escalaAtual: null,
  dashboard: null,
  militares: [],
  permutas: [],
  afastamentos: [],
  diaParaTroca: null,
  previsaoCalculada: null,
};

// --- Inicialização ---
document.addEventListener('DOMContentLoaded', async () => {
  setupTabs();
  setupEventListeners();
  await carregarDadosIniciais();
});

async function carregarDadosIniciais() {
  mostrarLoading(true);
  try {
    await Promise.all([
      carregarDashboard(),
      carregarSemanas(),
      carregarMilitares(),
    ]);

    // Se temos semanas cadastradas, seleciona a última por padrão
    if (state.semanasDisponiveis.length > 0) {
      const ultima = state.semanasDisponiveis[state.semanasDisponiveis.length - 1];
      state.semanaSelecionada = ultima.semana_ano;
    }

    await carregarEscalaSemana(state.semanaSelecionada);
  } catch (err) {
    console.error('Erro na inicialização:', err);
    mostrarToast('Falha ao conectar com o servidor local.', 'danger');
  } finally {
    mostrarLoading(false);
  }
}

// --- Funções de API ---

async function carregarDashboard() {
  const res = await fetch(`${API_BASE}/dashboard`);
  if (!res.ok) throw new Error('Erro ao carregar dashboard');
  state.dashboard = await res.json();
  renderizarDashboard();
}

async function carregarSemanas() {
  const res = await fetch(`${API_BASE}/semanas`);
  if (!res.ok) throw new Error('Erro ao carregar semanas');
  state.semanasDisponiveis = await res.json();
  renderizarBotoesSemanas();
}

async function carregarEscalaSemana(semanaAno) {
  try {
    const res = await fetch(`${API_BASE}/escala/${semanaAno}`);
    if (!res.ok) throw new Error(`Semana ${semanaAno} não encontrada`);
    state.escalaAtual = await res.json();
    state.semanaSelecionada = semanaAno;
    renderizarBotoesSemanas();
    renderizarQuadroSemanal();
  } catch (err) {
    console.error('Erro ao buscar escala:', err);
    mostrarToast(`Erro ao carregar Semana ${semanaAno}`, 'danger');
  }
}

async function carregarMilitares() {
  const res = await fetch(`${API_BASE}/militares`);
  if (!res.ok) throw new Error('Erro ao carregar militares');
  state.militares = await res.json();
  renderizarTabelaFolgas();
  popularSelectMilitares();
}

async function carregarPermutas() {
  const res = await fetch(`${API_BASE}/permutas`);
  if (!res.ok) throw new Error('Erro ao carregar permutas');
  state.permutas = await res.json();
  renderizarTabelaPermutas();
}

async function carregarAfastamentos() {
  const res = await fetch(`${API_BASE}/afastamentos`);
  if (!res.ok) throw new Error('Erro ao carregar afastamentos');
  state.afastamentos = await res.json();
  renderizarTabelaAfastamentos();
}

// --- Renderização da Interface ---

function renderizarDashboard() {
  const d = state.dashboard;
  if (!d) return;

  document.getElementById('kpi-efetivo').innerText = d.total_efetivo || '0';
  document.getElementById('kpi-escalas').innerText = d.total_escalas_registradas || '0';
  document.getElementById('kpi-permutas').innerText = d.total_permutas_registradas || '0';
  document.getElementById('kpi-afastados').innerText = d.afastados_hoje || '0';
}

function renderizarBotoesSemanas() {
  const container = document.getElementById('week-buttons-container');
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

  document.getElementById('sheet-title-text').innerText = `${esc.semana_ano}ª SEMANA - PREVISÃO DA ESCALA DE SERVIÇO`;
  document.getElementById('sheet-period-text').innerText = `Período Oficial: ${formatarDataBr(esc.data_inicio)} a ${formatarDataBr(esc.data_fim)}`;

  const grid = document.getElementById('schedule-grid-container');
  grid.innerHTML = '';

  esc.dias.forEach(dia => {
    const isRed = dia.tipo_escala === 'VERMELHA';
    const hasSwap = !!dia.caneta_nome;

    const col = document.createElement('div');
    col.className = `day-column ${isRed ? 'is-red' : ''}`;

    // Cabeçalho do dia
    const diaNum = dia.data.split('-')[2];
    col.innerHTML = `
      <div class="day-header">
        <div class="day-name">${dia.dia_semana} (${diaNum})</div>
        <div class="day-date">${formatarDataBr(dia.data)}</div>
        ${isRed ? `<span class="red-scale-tag">Escala Vermelha</span>` : ''}
      </div>

      <div class="duty-slot ${hasSwap ? 'has-swap' : ''}">
        <span class="rank-label">${dia.impresso_graduacao}</span>
        <div class="military-name ${hasSwap ? 'struck' : ''}">${dia.impresso_nome}</div>

        ${hasSwap ? `
          <div class="pen-swap-badge" title="Troca a caneta: folga oficial permanece no titular impresso">
            <span class="pen-label">Assumiu (Caneta)</span>
            <span class="pen-name">${dia.caneta_graduacao} ${dia.caneta_nome}</span>
            <div style="font-size:0.68em; color:#93C5FD; margin-top:2px;">${dia.permuta_motivo || 'Permuta'}</div>
          </div>
        ` : ''}

        <div style="display:flex; gap:4px; justify-content:center;">
          <button class="slot-action-btn" onclick="abrirModalTroca(${dia.id})" title="Registrar ou alterar troca a caneta">
            🖋️ ${hasSwap ? 'Editar Troca' : 'Permuta'}
          </button>
          ${hasSwap ? `
            <button class="slot-action-btn" onclick="desfazerTroca(${dia.id})" title="Cancelar troca e voltar ao titular" style="color:#F87171;">
              ✕
            </button>
          ` : ''}
        </div>
      </div>

      <div class="day-footer">
        ${dia.feriado_descricao ? `🎉 <strong>${dia.feriado_descricao}</strong>` : (dia.observacoes || (isRed ? 'Final de Semana' : 'Expediente Normal'))}
      </div>
    `;

    grid.appendChild(col);
  });
}

function renderizarTabelaFolgas() {
  const tbody = document.getElementById('tbody-folgas');
  if (!tbody) return;

  tbody.innerHTML = '';
  // Ordena por maior folga na preta por padrão
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
        <span style="font-weight:700; color:${m.saldo_permuta > 0 ? '#34D399' : (m.saldo_permuta < 0 ? '#F87171' : 'var(--text-muted)')};">
          ${m.saldo_permuta > 0 ? `+${m.saldo_permuta}` : m.saldo_permuta}
        </span>
        <span style="font-size:0.75em; color:var(--text-muted);">(${m.creditos_permuta} cobriu / ${m.debitos_permuta} cedeu)</span>
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

function renderizarTabelaPermutas() {
  const tbody = document.getElementById('tbody-permutas');
  if (!tbody) return;

  tbody.innerHTML = '';
  if (state.permutas.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding:2rem; color:var(--text-muted);">Nenhuma permuta registrada no período.</td></tr>`;
    return;
  }

  state.permutas.forEach(p => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><strong>${formatarDataBr(p.data_servico)}</strong></td>
      <td>${p.semana_ano}ª Sem (${p.dia_semana})</td>
      <td><span class="red-scale-tag" style="background:${p.tipo_escala === 'VERMELHA' ? '#EF4444' : '#1E293B'};">${p.tipo_escala}</span></td>
      <td><strong>${p.cedente_graduacao} ${p.cedente_nome}</strong></td>
      <td style="color:#60A5FA;"><strong>${p.substituto_graduacao} ${p.substituto_nome}</strong></td>
      <td>${p.motivo || 'Permuta de Serviço'}</td>
      <td><span style="font-size:0.85em; color:var(--text-muted);">${p.autorizado_por || 'Fiscal de Dia'}</span></td>
    `;
    tbody.appendChild(tr);
  });
}

function renderizarTabelaAfastamentos() {
  const tbody = document.getElementById('tbody-afastamentos');
  if (!tbody) return;

  tbody.innerHTML = '';
  if (state.afastamentos.length === 0) {
    tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; padding:2rem; color:var(--text-muted);">Nenhum militar em afastamento programado.</td></tr>`;
    return;
  }

  state.afastamentos.forEach(a => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><strong>${a.posto_graduacao} ${a.nome_guerra}</strong></td>
      <td><span style="background:rgba(245,158,11,0.2); color:#FBBF24; padding:2px 8px; border-radius:4px; font-weight:700;">${a.motivo}</span></td>
      <td>${formatarDataBr(a.data_inicio)}</td>
      <td>${formatarDataBr(a.data_fim)}</td>
      <td style="color:var(--text-muted);">${a.observacao || '—'}</td>
    `;
    tbody.appendChild(tr);
  });
}

// --- Modais e Ações do Usuário ---

window.abrirModalTroca = function(escalaDiaId) {
  const dia = state.escalaAtual.dias.find(d => d.id === escalaDiaId);
  if (!dia) return;

  state.diaParaTroca = dia;
  document.getElementById('modal-troca-dia-info').innerText = `${dia.dia_semana} (${formatarDataBr(dia.data)}) - ${dia.tipo_escala}`;
  document.getElementById('modal-troca-titular-nome').innerText = `${dia.impresso_graduacao} ${dia.impresso_nome}`;

  popularSelectMilitares(dia.impresso_id);
  document.getElementById('modal-troca-motivo').value = dia.permuta_motivo || 'Permuta operacional';

  document.getElementById('modal-troca').classList.add('active');
};

window.fecharModalTroca = function() {
  document.getElementById('modal-troca').classList.remove('active');
  state.diaParaTroca = null;
};

window.confirmarTroca = async function() {
  if (!state.diaParaTroca) return;

  const substitutoId = parseInt(document.getElementById('modal-troca-substituto').value);
  const motivo = document.getElementById('modal-troca-motivo').value.trim();

  if (!substitutoId) {
    mostrarToast('Selecione o militar substituto.', 'warning');
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/trocas`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        escala_dia_id: state.diaParaTroca.id,
        militar_substituto_id: substitutoId,
        motivo: motivo || 'Permuta de escala',
        autorizado_por: 'Fiscal de Dia',
      }),
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Erro ao registrar troca');

    mostrarToast('Troca a caneta registrada com sucesso!', 'success');
    fecharModalTroca();
    await carregarEscalaSemana(state.semanaSelecionada);
    await carregarDashboard();
    await carregarMilitares();
  } catch (err) {
    console.error('Erro na troca:', err);
    mostrarToast(err.message, 'danger');
  }
};

window.desfazerTroca = async function(escalaDiaId) {
  if (!confirm('Deseja cancelar esta troca e retornar o serviço ao titular impresso?')) return;

  try {
    const res = await fetch(`${API_BASE}/trocas/${escalaDiaId}`, { method: 'DELETE' });
    if (!res.ok) throw new Error('Erro ao desfazer troca');

    mostrarToast('Troca cancelada com sucesso.', 'success');
    await carregarEscalaSemana(state.semanaSelecionada);
    await carregarDashboard();
    await carregarMilitares();
  } catch (err) {
    console.error('Erro ao desfazer troca:', err);
    mostrarToast(err.message, 'danger');
  }
};

// --- Previsão de Nova Semana ---

window.abrirModalPrevisao = function() {
  // Sugere a próxima semana baseada na última
  const ultimaSem = state.semanasDisponiveis.length > 0
    ? state.semanasDisponiveis[state.semanasDisponiveis.length - 1]
    : { semana_ano: 41, data_fim: '2026-10-14' };

  const proximaSemanaNum = ultimaSem.semana_ano + 1;

  // Próxima quinta-feira após o último dia cadastrado (que costuma ser quarta-feira)
  const ultDataFim = new Date(ultimaSem.data_fim + 'T12:00:00');
  ultDataFim.setDate(ultDataFim.getDate() + 1); // Dia seguinte = Quinta-feira
  const dataInicioSugerida = ultDataFim.toISOString().split('T')[0];

  document.getElementById('prev-semana-num').value = proximaSemanaNum;
  document.getElementById('prev-data-inicio').value = dataInicioSugerida;
  document.getElementById('previsao-preview-container').style.display = 'none';
  document.getElementById('btn-salvar-previsao').style.display = 'none';

  document.getElementById('modal-previsao').classList.add('active');
};

window.fecharModalPrevisao = function() {
  document.getElementById('modal-previsao').classList.remove('active');
  state.previsaoCalculada = null;
};

window.calcularPrevisao = async function() {
  const semanaNum = parseInt(document.getElementById('prev-semana-num').value);
  const dataInicio = document.getElementById('prev-data-inicio').value;

  if (!semanaNum || !dataInicio) {
    mostrarToast('Preencha a semana e a data de início.', 'warning');
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/previsao/calcular`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        semana_ano: semanaNum,
        data_inicio_quinta: dataInicio,
        posto_codigo: 'SGT_DE_DIA',
      }),
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Erro ao calcular previsão');

    state.previsaoCalculada = data.previsao;
    renderizarPreviewPrevisao(data.previsao);
  } catch (err) {
    console.error('Erro no cálculo preditivo:', err);
    mostrarToast(err.message, 'danger');
  }
};

function renderizarPreviewPrevisao(previsao) {
  const container = document.getElementById('previsao-preview-container');
  const tbody = document.getElementById('tbody-preview-previsao');
  tbody.innerHTML = '';

  previsao.forEach(p => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><strong>${formatarDataBr(p.data)}</strong> (${p.dia_semana})</td>
      <td><span class="red-scale-tag" style="background:${p.tipo_escala === 'VERMELHA' ? '#EF4444' : '#1E293B'};">${p.tipo_escala}</span></td>
      <td><strong>${p.posto_graduacao} ${p.nome_guerra}</strong></td>
      <td>
        <span class="rest-badge green">
          ${p.tipo_escala === 'PRETA' ? `${p.folga_preta_acumulada} dias folga` : `${p.folga_vermelha_acumulada} dias folga`}
        </span>
      </td>
      <td style="font-size:0.8em; color:var(--text-muted);">${p.feriado || 'Escala Normal'}</td>
    `;
    tbody.appendChild(tr);
  });

  container.style.display = 'block';
  document.getElementById('btn-salvar-previsao').style.display = 'inline-flex';
}

window.salvarPrevisao = async function() {
  if (!state.previsaoCalculada) return;

  try {
    const res = await fetch(`${API_BASE}/previsao/salvar`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ previsao: state.previsaoCalculada }),
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Erro ao salvar previsão');

    mostrarToast(`Semana ${state.previsaoCalculada[0].semana_ano} gerada e salva com sucesso!`, 'success');
    const semanaSalva = state.previsaoCalculada[0].semana_ano;
    fecharModalPrevisao();

    await carregarSemanas();
    await carregarEscalaSemana(semanaSalva);
    await carregarDashboard();
    await carregarMilitares();
  } catch (err) {
    console.error('Erro ao salvar previsão:', err);
    mostrarToast(err.message, 'danger');
  }
};

// --- Exportação e Baixar PNG ---

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

window.abrirAbaFoto = function() {
  const btnFoto = document.querySelector('.tab-btn[data-tab="tab-foto"]');
  if (btnFoto) {
    btnFoto.click();
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }
};

// --- Módulo OCR / Visão de Fotos de Escala ---

let ocrArquivoSelecionado = null;
let ocrDadosReconhecidos = null;

window.aoSelecionarFoto = function(event) {
  const file = event.target.files && event.target.files[0];
  if (!file) return;
  carregarFotoNoDropzone(file);
};

function carregarFotoNoDropzone(file) {
  ocrArquivoSelecionado = file;
  const reader = new FileReader();
  reader.onload = function(e) {
    const thumb = document.getElementById('ocr-img-thumb');
    if (thumb) thumb.src = e.target.result;
    document.getElementById('ocr-preview-container').style.display = 'block';
    document.getElementById('ocr-resultado-card').style.display = 'none';
  };
  reader.readAsDataURL(file);
}

window.limparFotoSelecionada = function() {
  ocrArquivoSelecionado = null;
  ocrDadosReconhecidos = null;
  const input = document.getElementById('input-foto-escala');
  if (input) input.value = '';
  const prev = document.getElementById('ocr-preview-container');
  if (prev) prev.style.display = 'none';
  const resCard = document.getElementById('ocr-resultado-card');
  if (resCard) resCard.style.display = 'none';
};

window.cancelarReconhecimento = function() {
  limparFotoSelecionada();
  mostrarToast('Operação de leitura descartada.', 'info');
};

window.processarFotoEscala = async function() {
  if (!ocrArquivoSelecionado) {
    mostrarToast('Selecione ou arraste uma foto antes de continuar.', 'warning');
    return;
  }

  const btnProcessar = document.getElementById('btn-processar-foto');
  if (btnProcessar) {
    btnProcessar.disabled = true;
    btnProcessar.innerHTML = '⏳ Processando com IA (Gemini Vision)...';
  }
  mostrarLoading(true);

  try {
    const formData = new FormData();
    formData.append('arquivo', ocrArquivoSelecionado);

    const res = await fetch(`${API_BASE}/reconhecer-foto-escala`, {
      method: 'POST',
      body: formData,
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || 'Falha ao processar foto com a IA.');
    }

    const dados = await res.json();
    ocrDadosReconhecidos = dados;
    renderizarConferenciaOcr(dados);
    mostrarToast(`Escala da ${dados.semana_ano}ª Semana lida com sucesso!`, 'success');
  } catch (err) {
    console.error('Erro OCR:', err);
    mostrarToast(err.message, 'danger');
  } finally {
    mostrarLoading(false);
    if (btnProcessar) {
      btnProcessar.disabled = false;
      btnProcessar.innerHTML = '⚡ Analisar com IA & Extrair Escala';
    }
  }
};

function renderizarConferenciaOcr(dados) {
  document.getElementById('ocr-res-semana').innerText = `${dados.semana_ano || '--'}ª Semana`;
  document.getElementById('ocr-res-periodo').innerText = dados.periodo || `${dados.data_inicio} a ${dados.data_fim}`;
  document.getElementById('ocr-res-inicio').innerText = formatarDataBr(dados.data_inicio);
  document.getElementById('ocr-res-fim').innerText = formatarDataBr(dados.data_fim);

  const tbody = document.getElementById('tbody-ocr-dias');
  if (!tbody) return;
  tbody.innerHTML = '';

  const dias = dados.dias || [];
  dias.forEach((d) => {
    const tr = document.createElement('tr');
    const isRed = d.tipo_escala === 'VERMELHA';

    // Dropdown para Titular Impresso
    let optionsImpresso = `<option value="">-- Selecione o Titular --</option>`;
    state.militares.forEach(m => {
      const selected = (d.militar_impresso_id === m.id || (!d.militar_impresso_id && m.nome_guerra.toUpperCase() === (d.militar_impresso_nome || '').toUpperCase())) ? 'selected' : '';
      optionsImpresso += `<option value="${m.id}" ${selected}>${m.posto_graduacao} ${m.nome_guerra}</option>`;
    });

    // Dropdown para Caneta (Substituto)
    let optionsCaneta = `<option value="">(Nenhuma troca - Cumpriu o Titular)</option>`;
    state.militares.forEach(m => {
      const selected = (d.militar_caneta_id === m.id || (!d.militar_caneta_id && d.militar_caneta_nome && m.nome_guerra.toUpperCase() === d.militar_caneta_nome.toUpperCase())) ? 'selected' : '';
      optionsCaneta += `<option value="${m.id}" ${selected}>${m.posto_graduacao} ${m.nome_guerra}</option>`;
    });

    const temTroca = d.troca_detectada || !!d.militar_caneta_nome;

    tr.innerHTML = `
      <td>
        <strong>${d.dia_semana}</strong> (${formatarDataBr(d.data)})
        <input type="hidden" class="ocr-dia-data" value="${d.data}">
        <input type="hidden" class="ocr-dia-semana" value="${d.dia_semana}">
        <input type="hidden" class="ocr-tipo-escala" value="${d.tipo_escala}">
      </td>
      <td>
        <span class="badge-tag" style="${isRed ? 'background:#FEE2E2; color:#991B1B;' : 'background:#E2E8F0; color:#0F172A;'} font-size:0.75rem; font-weight:700; padding:2px 8px; border-radius:4px;">
          ${d.tipo_escala}
        </span>
      </td>
      <td>
        <select class="form-control ocr-select-impresso" style="font-size:0.85rem; padding:0.35rem 0.5rem; font-weight:700;">
          ${optionsImpresso}
        </select>
        ${d.militar_impresso_raw ? `<div style="font-size:0.72rem; color:var(--text-muted); margin-top:2px;">Detectado: "${d.militar_impresso_raw}"</div>` : ''}
      </td>
      <td>
        <select class="form-control ocr-select-caneta" style="font-size:0.85rem; padding:0.35rem 0.5rem; ${temTroca ? 'border-color:#38BDF8; font-weight:700;' : ''}">
          ${optionsCaneta}
        </select>
        ${d.militar_caneta_raw ? `<div style="font-size:0.72rem; color:#60A5FA; margin-top:2px;">Caneta: "${d.militar_caneta_raw}"</div>` : ''}
      </td>
      <td>
        ${temTroca ? `
          <span style="background:rgba(59,130,246,0.15); color:#60A5FA; border:1px solid #3B82F6; padding:3px 8px; border-radius:4px; font-size:0.75rem; font-weight:700;">
            🖋️ Troca a Caneta
          </span>
        ` : `
          <span style="background:rgba(16,185,129,0.15); color:#34D399; border:1px solid #10B981; padding:3px 8px; border-radius:4px; font-size:0.75rem; font-weight:700;">
            🟢 Titular Oficial
          </span>
        `}
      </td>
    `;
    tbody.appendChild(tr);
  });

  document.getElementById('ocr-resultado-card').style.display = 'block';
}

window.confirmarImportacaoOcr = async function() {
  if (!ocrDadosReconhecidos) return;

  const rows = document.querySelectorAll('#tbody-ocr-dias tr');
  if (rows.length === 0) {
    mostrarToast('Nenhum dia para importar.', 'warning');
    return;
  }

  const diasParaSalvar = [];
  for (const r of rows) {
    const data = r.querySelector('.ocr-dia-data').value;
    const dia_semana = r.querySelector('.ocr-dia-semana').value;
    const tipo_escala = r.querySelector('.ocr-tipo-escala').value;
    const selImpresso = r.querySelector('.ocr-select-impresso');
    const selCaneta = r.querySelector('.ocr-select-caneta');

    const militar_impresso_id = selImpresso.value ? parseInt(selImpresso.value) : null;
    const militar_caneta_id = selCaneta.value ? parseInt(selCaneta.value) : null;

    if (!militar_impresso_id) {
      mostrarToast(`Selecione o Titular Impresso para o dia ${data}`, 'warning');
      return;
    }

    diasParaSalvar.push({
      data: data,
      dia_semana: dia_semana,
      tipo_escala: tipo_escala,
      posto_codigo: 'SGT_DE_DIA',
      militar_impresso_id: militar_impresso_id,
      militar_caneta_id: militar_caneta_id,
      motivo: militar_caneta_id ? 'Anotação a caneta na escala oficial (Foto OCR)' : null,
    });
  }

  mostrarLoading(true);
  try {
    const res = await fetch(`${API_BASE}/confirmar-importacao-foto`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        semana_ano: ocrDadosReconhecidos.semana_ano,
        dias: diasParaSalvar,
      }),
    });

    const result = await res.json();
    if (!res.ok) throw new Error(result.detail || 'Falha ao confirmar importação da escala');

    mostrarToast(`Sucesso! Escala da ${ocrDadosReconhecidos.semana_ano}ª Semana salva e folgas recalculadas!`, 'success');

    // Atualiza semanas, escala, folgas e dashboard
    await carregarSemanas();
    await carregarEscalaSemana(ocrDadosReconhecidos.semana_ano);
    await carregarMilitares();
    await carregarPermutas();
    await carregarDashboard();

    // Redireciona para o Quadro Semanal
    const tabEscalaBtn = document.querySelector('.tab-btn[data-tab="tab-escala"]');
    if (tabEscalaBtn) tabEscalaBtn.click();

    limparFotoSelecionada();
  } catch (err) {
    console.error('Erro ao confirmar importação:', err);
    mostrarToast(err.message, 'danger');
  } finally {
    mostrarLoading(false);
  }
};

// --- Helpers e Utilitários ---

function popularSelectMilitares(excluirId = null) {
  const select = document.getElementById('modal-troca-substituto');
  if (!select) return;

  select.innerHTML = '<option value="">-- Selecione o Substituto (Caneta) --</option>';
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
      if (targetId.includes('permutas')) await carregarPermutas();
      if (targetId.includes('afastamentos')) await carregarAfastamentos();
    });
  });
}

function setupEventListeners() {
  // Toggle Tema Claro/Escuro
  const themeBtn = document.getElementById('btn-theme-toggle');
  if (themeBtn) {
    themeBtn.addEventListener('click', () => {
      const current = document.documentElement.getAttribute('data-theme') || 'dark';
      const next = current === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', next);
      themeBtn.innerText = next === 'dark' ? '☀️' : '🌙';
    });
  }

  // Drag and Drop para Dropzone de Foto
  const dropzone = document.getElementById('ocr-dropzone');
  if (dropzone) {
    ['dragenter', 'dragover'].forEach(eventName => {
      dropzone.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropzone.classList.add('drag-over');
      }, false);
    });
    ['dragleave', 'drop'].forEach(eventName => {
      dropzone.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropzone.classList.remove('drag-over');
      }, false);
    });
    dropzone.addEventListener('drop', (e) => {
      const dt = e.dataTransfer;
      const files = dt.files;
      if (files && files.length > 0) {
        carregarFotoNoDropzone(files[0]);
      }
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

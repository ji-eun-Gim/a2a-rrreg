function normalizeStatus(raw) {
  const v = String(raw || '').toLowerCase();
  if (v === 'active') return 'active';
  if (v === 'draft') return 'unapproved';
  if (v === 'deprecated' || v === 'retired') return 'inactive';
  return 'inactive';
}

function displayStatus(raw) {
  const norm = normalizeStatus(raw);
  if (norm === 'active') return '활동';
  if (norm === 'unapproved') return '미승인';
  return '비활동';
}

async function fetchList() {
  try {
    const q = document.getElementById('q').value;
    const namespace = document.getElementById('namespace').value;
    const uiStatus = document.getElementById('status').value;
    const params = new URLSearchParams();
    if (q) params.set('q', q);
    if (namespace) params.set('namespace', namespace);
    if (uiStatus === 'active') params.set('status', 'active');
    else if (uiStatus === 'unapproved') params.set('status', 'draft');
    const res = await fetch(`/v1/agents?${params.toString()}`);
    const data = await res.json();
    const grid = document.getElementById('cards');
    grid.innerHTML = '';
    const items = (uiStatus === 'inactive')
      ? (data.items || []).filter(it => ['deprecated', 'retired'].includes(String(it.status || '').toLowerCase()))
      : (data.items || []);
    for (const it of items) {
      const card = document.createElement('div');
      card.className = 'card';
      const name = it.name || '(no name)';
      const ns = it.namespace || 'default';
      const ver = it.version || '';
      const badgeClass = normalizeStatus(it.status);
      const badgeText = displayStatus(it.status);
      card.innerHTML = `
        <div class="card-header">
          <div class="card-title">${name}</div>
          <span class="badge ${badgeClass}">${badgeText}</span>
        </div>
        <div class="card-body">
          <div class="meta"><strong>Version:</strong> ${ver}</div>
          <div class="meta"><strong>Namespace:</strong> ${ns}</div>
        </div>
        <div class="card-actions">
          <button data-id="${it.id}" data-action="view">View</button>
          <button data-id="${it.id}" data-action="force" class="danger">Force</button>
        </div>
      `;
      grid.appendChild(card);
    }
  } catch (e) {
    console.error('List fetch error', e);
  }
}

document.getElementById('searchBtn').addEventListener('click', fetchList);
fetchList();

const modal = document.getElementById('modal');
document.getElementById('createBtn').addEventListener('click', ()=> modal.classList.remove('hidden'));
document.getElementById('closeBtn').addEventListener('click', ()=> modal.classList.add('hidden'));

// Validate 버튼 제거: Create에서 자동 검증 처리

document.getElementById('submitBtn').addEventListener('click', async ()=>{
  const text = document.getElementById('cardText').value || '{}';
  const idem = (window.crypto && crypto.randomUUID) ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  try {
    const res = await fetch('/v1/agents', {method:'POST', headers:{'Content-Type':'application/json','Idempotency-Key': idem}, body: text});
    const bodyText = await res.text();
    let payload;
    try { payload = JSON.parse(bodyText); } catch { payload = { status: res.status, body: bodyText }; }
    if (res.ok) {
      document.getElementById('result').textContent = '카드가 생성되었습니다.';
      fetchList(); fetchNotifications();
    } else {
      // 서버에서 전달한 에러 메시지가 있으면 그대로 표시
      const serverMsg = (payload && (payload.error || payload.detail)) ? (payload.error || payload.detail) : null;
      document.getElementById('result').textContent = serverMsg || '올바른 카드 형식이 아닙니다.';
    }
  } catch (e) {
      document.getElementById('result').textContent = `Create error: ${e}`;
  }
});


document.getElementById('cards').addEventListener('click', async (e)=>{
  if (e.target.tagName !== 'BUTTON' || !e.target.dataset.id) return;
  const id = e.target.dataset.id;
  const action = e.target.dataset.action || 'view';
  try {
    if (action === 'view') {
      openDetail(id);
    } else if (action === 'force') {
      if (!confirm(`정말 완전 삭제하시겠습니까?\nID: ${id}`)) return;
      const res = await fetch(`/v1/agents/${id}?force=true`, { method: 'DELETE' });
      const bodyText = await res.text();
      let payload; try { payload = JSON.parse(bodyText); } catch { payload = { status: res.status, body: bodyText }; }
      console.log(`Force delete ${id}:`, payload);
      if (res.ok) { fetchList(); fetchNotifications(); }
    }
  } catch (err) {
    console.error('Action error', err);
  }
});

// 상세 모달 로직: 카드/감사 로그 표시 + Force 버튼
let currentDetailId = null;
async function openDetail(id) {
  currentDetailId = id;
  const modal = document.getElementById('detailModal');
  const title = document.getElementById('detailTitle');
  const preCard = document.getElementById('detailCard');
  const preAudit = document.getElementById('detailAudit');
  preCard.textContent = 'Loading...';
  preAudit.textContent = '';
  modal.classList.remove('hidden');

  try {
    const [resAgent, resAudit] = await Promise.all([
      fetch(`/v1/agents/${id}`),
      fetch(`/v1/logs?target_id=${encodeURIComponent(id)}&limit=20`)
    ]);
    const agent = await resAgent.json();
    const audit = await resAudit.json();
    title.textContent = `Agent Detail — ${agent.card?.name || agent.name || ''} (${agent.id})`;
    preCard.textContent = JSON.stringify(agent, null, 2);
    preAudit.textContent = JSON.stringify(audit.items || [], null, 2);
  } catch (e) {
    preCard.textContent = `Error: ${e}`;
  }
}

document.getElementById('detailCloseBtn').addEventListener('click', ()=>{
  document.getElementById('detailModal').classList.add('hidden');
  currentDetailId = null;
});

document.getElementById('detailForceBtn').addEventListener('click', async ()=>{
  if (!currentDetailId) return;
  if (!confirm('정말 완전 삭제하시겠습니까?')) return;
  try {
    const res = await fetch(`/v1/agents/${currentDetailId}?force=true`, { method: 'DELETE' });
    const bodyText = await res.text();
    let payload; try { payload = JSON.parse(bodyText); } catch { payload = { status: res.status, body: bodyText }; }
    console.log(`Force delete ${currentDetailId}:`, payload);
    if (res.ok) { fetchList(); fetchNotifications(); document.getElementById('detailModal').classList.add('hidden'); }
  } catch (e) {
    console.error('Force error', e);
  }
});

// 알림: v3 로그 기반 (상태 변경 관련 이벤트만)
async function fetchNotifications() {
  try {
    const res = await fetch('/v1/logs?limit=50');
    const data = await res.json();
    const items = (data.items || []).filter(it => ['create','update','deprecate','retire','revoke','read'].includes(String(it.op)));
    const cntEl = document.getElementById('js-alarmCnt');
    if (items.length > 0) { cntEl.textContent = String(items.length); cntEl.classList.remove('hidden'); }
    else { cntEl.classList.add('hidden'); }
    return items;
  } catch (e) {
    console.error('Notify fetch error', e);
    return [];
  }
}

async function openNotifications() {
  const modal = document.getElementById('notifyModal');
  const list = document.getElementById('notifyList');
  list.innerHTML = 'Loading...';
  modal.classList.remove('hidden');
  const items = await fetchNotifications();
  if (!items.length) { list.innerHTML = '<div>새 알림이 없습니다.</div>'; return; }
  list.innerHTML = '';
  for (const it of items) {
    const el = document.createElement('div');
    el.style.border = '1px solid var(--border)';
    el.style.borderRadius = '8px';
    el.style.padding = '8px 10px';
    const id = it.data?.retire?.target_id || it.data?.revoke?.target_id || it.data?.deprecate?.target_id || it.data?.update?.target_id || it.data?.create?.target_id || it.data?.read?.selected_id || '';
    const ts = it.ts || '';
    const _op = String(it.op);
    const label = ({create:'created', update:'updated', retire:'retired', revoke:'revoked', deprecate:'deprecated', read:'viewed'})[_op] || _op;
    let desc = ({
      create: '에이전트 카드가 등록되었습니다.',
      update: '에이전트 카드가 수정되었습니다.',
      retire: '에이전트 카드가 은퇴 처리되었습니다.',
      revoke: '에이전트 카드가 강제 삭제되었습니다.',
      deprecate: '에이전트 카드가 사용 중단(Deprecated)되었습니다.',
      read: `에이전트 카드가 조회되었습니다. by ${it.actor_sub || ''}`
    })[_op] || '';
    const status = Number(it.http_status || 0);
    const severity = String(it.severity || 'INFO');
    let badgeClass = 'badge';
    if (_op === 'create') {
      if (severity === 'INFO' && status === 201) { badgeClass = 'badge active'; desc = '에이전트 카드가 등록되었습니다.'; }
      else { badgeClass = 'badge error'; desc = `에이전트 카드 등록 실패${it.error_msg ? `: ${it.error_msg}` : ''}`; }
    } else if (_op === 'update') {
      if (severity === 'INFO' && status === 200) { badgeClass = 'badge active'; desc = '에이전트 카드가 수정되었습니다.'; }
      else { badgeClass = 'badge error'; desc = '에이전트 카드 수정 실패'; }
    } else if (_op === 'retire') {
      badgeClass = 'badge inactive';
    } else if (_op === 'revoke') {
      badgeClass = 'badge error';
    } else if (_op === 'deprecate') {
      badgeClass = 'badge inactive';
    } else if (_op === 'read') {
      badgeClass = 'badge';
    }
    el.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center;gap:8px">
        <div>
          <span class="${badgeClass}">${label}</span>
          <strong style="margin-left:6px">${id}</strong>
        </div>
        <div style="color:var(--muted);font-size:12px">${ts}</div>
      </div>
      ${desc ? `<div style="margin-top:6px;color:#374151;font-size:13px">${desc}</div>` : ''}
    `;
    list.appendChild(el);
  }
  // 사용자가 확인했으므로 뱃지 초기화
  clearNotificationsBadge();
}

document.getElementById('js-bell').addEventListener('click', openNotifications);
document.getElementById('notifyCloseBtn').addEventListener('click', ()=> {
  document.getElementById('notifyModal').classList.add('hidden');
  clearNotificationsBadge();
});

// 초기 알림 카운트 갱신
fetchNotifications();

// 실시간 알림: SSE 연결 (fallback: 폴링)
(function initRealtime() {
  const ops = ['create','update','deprecate','retire','revoke','read'].join(',');
  try {
    const es = new EventSource(`/v1/logs:stream?ops=${encodeURIComponent(ops)}`);
    es.onmessage = (e) => {
      try {
        const ev = JSON.parse(e.data);
        // 알림용 이벤트만 반영
        const t = String(ev.op);
        if (!['create','update','deprecate','retire','revoke','read'].includes(t)) return;
        // 카운트 뱃지 갱신
        const cntEl = document.getElementById('js-alarmCnt');
        const cur = parseInt(cntEl.textContent || '0', 10) || 0;
        cntEl.textContent = String(cur + 1);
        cntEl.classList.remove('hidden');
        // 모달이 열려 있으면 리스트도 갱신
        const modal = document.getElementById('notifyModal');
        if (modal && !modal.classList.contains('hidden')) {
          openNotifications();
        }
      } catch {}
    };
    es.onerror = () => {
      // fallback to polling if SSE fails
      setInterval(() => {
        if (document.visibilityState === 'visible') fetchNotifications();
      }, 8000);
    };
  } catch (e) {
    setInterval(() => {
      if (document.visibilityState === 'visible') fetchNotifications();
    }, 8000);
  }
  // 목록은 10초 주기로 갱신 유지
  setInterval(() => {
    if (document.visibilityState === 'visible') fetchList();
  }, 10000);
})();

function clearNotificationsBadge() {
  const cntEl = document.getElementById('js-alarmCnt');
  if (!cntEl) return;
  cntEl.textContent = '0';
  cntEl.classList.add('hidden');
}

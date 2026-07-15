// ── State ────────────────────────────────────────────
let authToken = sessionStorage.getItem('admin_token') || '';
let currentComicId = null;
let currentComic = null;
let templates = {};
let providers = {};
let statusTimer = null;

// ── API helper ──────────────────────────────────────
async function api(url, opts = {}) {
  opts.headers = opts.headers || {};
  if (authToken) opts.headers['Authorization'] = `Bearer ${authToken}`;
  if (opts.body && typeof opts.body === 'object') {
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(opts.body);
  }
  const res = await fetch(url, opts);
  if (res.status === 401) { showLogin(); throw new Error('未登录'); }
  return res;
}

// ── Auth ─────────────────────────────────────────────
let captchaId = '';

async function refreshCaptcha() {
  const res = await fetch('/api/captcha');
  const data = await res.json();
  captchaId = data.captcha_id;
  const img = res.headers.get('X-Captcha-Image');
  document.getElementById('captchaImg').src = 'data:image/png;base64,' + img;
}

async function handleLogin(e) {
  e.preventDefault();
  const errEl = document.getElementById('loginError');
  errEl.textContent = '';

  const res = await fetch('/api/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      username: document.getElementById('loginUser').value,
      password: document.getElementById('loginPass').value,
      captcha_id: captchaId,
      captcha_code: document.getElementById('loginCaptcha').value,
    }),
  });
  const data = await res.json();
  if (!res.ok) {
    errEl.textContent = data.error || '登录失败';
    refreshCaptcha();
    return;
  }
  authToken = data.token;
  sessionStorage.setItem('admin_token', authToken);
  showApp();
}

async function checkAuth() {
  if (!authToken) return false;
  try {
    const res = await fetch('/api/check-auth', {
      headers: { 'Authorization': `Bearer ${authToken}` },
    });
    return res.ok;
  } catch { return false; }
}

function showLogin() {
  authToken = '';
  sessionStorage.removeItem('admin_token');
  document.getElementById('loginOverlay').style.display = 'flex';
  document.getElementById('appContainer').style.display = 'none';
  refreshCaptcha();
}

function showApp() {
  document.getElementById('loginOverlay').style.display = 'none';
  document.getElementById('appContainer').style.display = 'flex';
  init();
}

function logout() {
  fetch('/api/logout', {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${authToken}` },
  });
  showLogin();
}

// ── Mobile sidebar ──────────────────────────────────
function toggleSidebar() {
  document.getElementById('sidebar').classList.toggle('open');
  document.getElementById('sidebarOverlay').classList.toggle('show');
}
function closeSidebar() {
  document.getElementById('sidebar').classList.remove('open');
  document.getElementById('sidebarOverlay').classList.remove('show');
}

// ── Toast ────────────────────────────────────────────
function toast(msg) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.classList.add('show');
  setTimeout(() => el.classList.remove('show'), 2000);
}

// ── Init ─────────────────────────────────────────────
async function init() {
  // Load templates and providers in parallel
  const [tplRes, provRes] = await Promise.all([
    api('/api/comic-templates'),
    api('/api/providers'),
  ]);
  templates = await tplRes.json();
  providers = await provRes.json();

  // Populate template dropdown
  const tplSel = document.getElementById('comicTemplate');
  tplSel.innerHTML = '';
  for (const [key, tpl] of Object.entries(templates)) {
    const opt = document.createElement('option');
    opt.value = key;
    opt.textContent = `${tpl.name} (${tpl.pages}页)`;
    tplSel.appendChild(opt);
  }
  tplSel.addEventListener('change', () => {
    const t = templates[tplSel.value];
    document.getElementById('templateDesc').textContent = t ? `${t.desc} — ${t.structure}` : '';
  });
  tplSel.dispatchEvent(new Event('change'));

  // Populate provider dropdown
  const provSel = document.getElementById('comicProvider');
  provSel.innerHTML = '';
  for (const [name, cfg] of Object.entries(providers)) {
    const opt = document.createElement('option');
    opt.value = name;
    opt.textContent = `${name} (${cfg.model})`;
    if (!cfg.available) opt.disabled = true;
    provSel.appendChild(opt);
  }

  // Tab switching
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => switchTab(btn.dataset.tab));
  });

  // Load comic list
  await loadComicList();
}

// ── Tab switching ────────────────────────────────────
function switchTab(tab) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.toggle('active', b.dataset.tab === tab));
  document.querySelectorAll('.tab-pane').forEach(p => p.classList.toggle('active', p.id === `tab-${tab}`));
}

// ── Comic List ───────────────────────────────────────
async function loadComicList() {
  const res = await api('/api/comics');
  const comics = await res.json();
  const list = document.getElementById('comicList');
  list.innerHTML = '';

  if (comics.length === 0) {
    list.innerHTML = '<div style="padding:20px;text-align:center;color:rgba(255,255,255,0.4);font-size:13px;">暂无项目</div>';
    document.getElementById('emptyState').style.display = 'block';
    document.getElementById('tabBar').style.display = 'none';
    return;
  }

  for (const c of comics) {
    const div = document.createElement('div');
    div.className = `project-item${c.id === currentComicId ? ' active' : ''}`;
    div.innerHTML = `
      <div class="pj-topic">${esc(c.topic)}</div>
      <div class="pj-meta">${esc(c.child_name || '')} · ${c.pages_count || 0}页 · ${c.updated_at ? c.updated_at.slice(5, 16) : ''}</div>
    `;
    div.onclick = () => selectComic(c.id);
    list.appendChild(div);
  }
}

// ── Select Comic ─────────────────────────────────────
async function selectComic(cid) {
  currentComicId = cid;
  closeSidebar();

  const res = await api(`/api/comics/${cid}`);
  currentComic = await res.json();

  document.getElementById('currentTitle').textContent = currentComic.topic;
  document.getElementById('mobileTitle').textContent = currentComic.topic;

  // Fill form
  document.getElementById('comicTopic').value = currentComic.topic || '';
  document.getElementById('comicChildName').value = currentComic.child_name || '';
  document.getElementById('comicAge').value = currentComic.age || 5;
  document.getElementById('comicTemplate').value = currentComic.template || 'custom';
  document.getElementById('comicTemplate').dispatchEvent(new Event('change'));
  document.getElementById('comicExtra').value = currentComic.extra || '';

  // Show tabs
  document.getElementById('emptyState').style.display = 'none';
  document.getElementById('tabBar').style.display = 'flex';
  switchTab('info');

  // Render pages
  renderPages();
  renderOutputs();

  // Highlight in list
  document.querySelectorAll('.project-item').forEach(el => el.classList.remove('active'));
  // Re-highlight
  loadComicList();

  // Check generation status
  pollStatus();
}

// ── Create Comic ─────────────────────────────────────
async function createComic() {
  const res = await api('/api/comics', {
    method: 'POST',
    body: { topic: '新故事', child_name: '小朋友', age: 5, template: 'custom' },
  });
  const data = await res.json();
  await loadComicList();
  selectComic(data.id);
}

// ── Save Info ────────────────────────────────────────
async function saveComicInfo() {
  if (!currentComicId) return;
  await api(`/api/comics/${currentComicId}`, {
    method: 'PUT',
    body: {
      topic: document.getElementById('comicTopic').value,
      child_name: document.getElementById('comicChildName').value,
      age: parseInt(document.getElementById('comicAge').value) || 5,
      template: document.getElementById('comicTemplate').value,
      extra: document.getElementById('comicExtra').value,
    },
  });
  toast('保存成功');
  loadComicList();
}

// ── Delete Comic ─────────────────────────────────────
async function deleteComic() {
  if (!currentComicId) return;
  if (!confirm('确定要删除这个漫画项目吗？')) return;
  await api(`/api/comics/${currentComicId}`, { method: 'DELETE' });
  currentComicId = null;
  currentComic = null;
  document.getElementById('currentTitle').textContent = '选择或新建漫画项目';
  document.getElementById('tabBar').style.display = 'none';
  document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
  document.getElementById('emptyState').style.display = 'block';
  loadComicList();
  toast('已删除');
}

// ── Render Pages ─────────────────────────────────────
function renderPages() {
  const pages = currentComic?.pages || [];
  document.getElementById('pageCount').textContent = pages.length;
  const container = document.getElementById('pagesList');
  container.innerHTML = '';

  if (pages.length === 0) {
    container.innerHTML = '<div class="empty"><h3>暂无页面</h3><p>点击「生成」标签开始生成漫画</p></div>';
    return;
  }

  for (const page of pages) {
    const div = document.createElement('div');
    div.className = 'page-card';

    let content = `<div class="page-title">${esc(page.title || '')}</div>`;
    if (page.story_text) {
      content += `<div class="page-text">${esc(page.story_text)}</div>`;
    }
    if (page.dialogue && page.dialogue.length > 0) {
      content += '<div class="page-dialogue">';
      for (const d of page.dialogue) {
        content += `<div class="dlg-line"><span class="dlg-char">${esc(d.character)}:</span> ${esc(d.text)}</div>`;
      }
      content += '</div>';
    }
    if (page.sound_effect) {
      content += `<div class="page-sfx">${esc(page.sound_effect)}</div>`;
    }

    const emojis = (page.scene_emojis || []).join(' ');
    const sceneEmoji = page.scene_emoji || '';

    div.innerHTML = `
      <div class="page-num">${page.page_num || '?'}</div>
      <div class="page-body">
        <div class="page-meta">
          <span class="type-badge">${page.page_type || '?'}</span>
          <span class="act-badge">Act ${page.act || '?'}</span>
          <span class="page-emoji">${sceneEmoji}</span>
          ${emojis ? `<span style="font-size:14px;">${emojis}</span>` : ''}
        </div>
        ${content}
      </div>
    `;
    container.appendChild(div);
  }
}

// ── Render Outputs ───────────────────────────────────
function renderOutputs() {
  const outputs = currentComic?.outputs || [];
  const container = document.getElementById('comicOutputList');
  container.innerHTML = '';

  if (outputs.length === 0) {
    container.innerHTML = '<div class="empty"><h3>暂无输出文件</h3><p>生成后文件会显示在这里</p></div>';
    return;
  }

  for (const out of outputs) {
    const div = document.createElement('div');
    div.className = 'output-item';
    div.innerHTML = `
      <div class="out-icon ${out.ext.slice(1)}">${out.ext.slice(1).toUpperCase()}</div>
      <div class="out-info">
        <div class="out-name">${esc(out.name)}</div>
        <div class="out-meta">${out.size_kb} KB · ${out.created}</div>
      </div>
      <div class="out-actions">
        <a href="/api/comics/${currentComicId}/output/${encodeURIComponent(out.name)}" target="_blank" class="btn btn-secondary btn-sm">查看</a>
      </div>
    `;
    container.appendChild(div);
  }
}

// ── Generate ─────────────────────────────────────────
async function generateComic() {
  if (!currentComicId) return;
  const provider = document.getElementById('comicProvider').value;
  const fmt = document.getElementById('comicFormat').value;

  const btn = document.getElementById('btnGenComic');
  btn.disabled = true;
  btn.textContent = '生成中...';

  const statusEl = document.getElementById('comicGenStatus');
  statusEl.className = 'gen-status show running';
  statusEl.textContent = '正在启动...';

  await api(`/api/comics/${currentComicId}/generate`, {
    method: 'POST',
    body: { provider, format: fmt },
  });

  pollStatus();
}

function pollStatus() {
  if (statusTimer) clearInterval(statusTimer);
  statusTimer = setInterval(async () => {
    if (!currentComicId) { clearInterval(statusTimer); return; }
    const res = await api(`/api/comics/${currentComicId}/status`);
    const s = await res.json();
    const statusEl = document.getElementById('comicGenStatus');
    const btn = document.getElementById('btnGenComic');

    if (s.status === 'running') {
      statusEl.className = 'gen-status show running';
      statusEl.textContent = s.progress;
    } else if (s.status === 'done') {
      statusEl.className = 'gen-status show done';
      statusEl.textContent = s.progress;
      btn.disabled = false;
      btn.textContent = '开始生成';
      clearInterval(statusTimer);
      // Reload comic data to show new pages + outputs
      selectComic(currentComicId);
    } else if (s.status === 'error') {
      statusEl.className = 'gen-status show error';
      statusEl.textContent = s.progress;
      btn.disabled = false;
      btn.textContent = '开始生成';
      clearInterval(statusTimer);
    } else {
      // idle — do nothing
    }
  }, 2000);
}

// ── Preview ──────────────────────────────────────────
async function previewComic() {
  if (!currentComicId) return;
  try {
    const res = await api(`/api/comics/${currentComicId}/preview`, { method: 'POST' });
    const data = await res.json();
    if (data.ok && data.outputs?.length > 0) {
      window.open(data.outputs[0].url, '_blank');
    } else {
      toast(data.error || '预览失败');
    }
  } catch (e) {
    toast('预览失败: ' + e.message);
  }
}

// ── Utils ────────────────────────────────────────────
function esc(s) {
  const div = document.createElement('div');
  div.textContent = s;
  return div.innerHTML;
}

// ── Bootstrap ────────────────────────────────────────
document.getElementById('loginForm').addEventListener('submit', handleLogin);

(async () => {
  if (await checkAuth()) {
    showApp();
  } else {
    showLogin();
  }
})();

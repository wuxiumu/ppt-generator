// ── State ────────────────────────────────────────
let currentProject = null;
let currentId = null;
let selectedSlideIndex = null;
let allProjects = [];

// ── API helpers ──────────────────────────────────
async function api(url, method = 'GET', body = null) {
  const opts = { method, headers: { 'Content-Type': 'application/json' } };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(url, opts);
  return res.json();
}

function toast(msg = '已保存') {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 1500);
}

// ── Project List ─────────────────────────────────
async function loadProjects() {
  allProjects = await api('/api/projects');
  const list = document.getElementById('projectList');
  const more = document.getElementById('projectMore');
  const count = document.getElementById('projectCount');

  // Show first 10 projects in sidebar
  const displayProjects = allProjects.slice(0, 10);
  list.innerHTML = displayProjects.map(p => `
    <div class="project-item ${p.id === currentId ? 'active' : ''}" onclick="selectProject('${p.id}')">
      <div class="pj-topic">${esc(p.topic)}</div>
      <div class="pj-meta">${esc(p.audience || '')}</div>
    </div>
  `).join('');

  // Show "view all" button if more than 10
  if (allProjects.length > 10) {
    more.style.display = 'block';
    count.textContent = allProjects.length;
  } else {
    more.style.display = 'none';
  }
}

function showAllProjects() {
  const modal = document.getElementById('allProjectsModal');
  const list = document.getElementById('allProjectsList');
  const total = document.getElementById('totalProjects');

  total.textContent = allProjects.length;
  list.innerHTML = allProjects.map(p => `
    <div class="all-project-item" onclick="selectProjectFromModal('${p.id}')">
      <div class="ap-topic">${esc(p.topic)}</div>
      <div class="ap-meta">${esc(p.audience || '未设置受众')} · ${p.slides_count || 0} 张幻灯片</div>
    </div>
  `).join('');

  modal.classList.add('show');
}

function closeAllProjects() {
  document.getElementById('allProjectsModal').classList.remove('show');
}

function selectProjectFromModal(id) {
  closeAllProjects();
  selectProject(id);
}

async function createProject() {
  const topic = prompt('输入主题名称：');
  if (!topic) return;
  const res = await api('/api/projects', 'POST', { topic });
  await loadProjects();
  selectProject(res.id);
}

async function selectProject(id) {
  currentId = id;
  currentProject = await api(`/api/projects/${id}`);
  selectedSlideIndex = null;
  renderProject();
  loadProjects();
}

// ── Render Project ───────────────────────────────
function renderProject() {
  const p = currentProject;
  if (!p) return;

  document.getElementById('headerTitle').textContent = p.topic;
  document.getElementById('btnSave').style.display = '';
  document.getElementById('btnDelete').style.display = '';
  document.getElementById('tabBar').style.display = '';
  document.getElementById('emptyState').style.display = 'none';

  // Basic info
  document.getElementById('f-topic').value = p.topic || '';
  document.getElementById('f-brief').value = p.brief || '';
  document.getElementById('f-audience').value = p.audience || '';

  // Prompts
  document.getElementById('f-planner-system').value = p.planner_system || '';
  document.getElementById('f-planner-prompt').value = p.planner_prompt || '';
  document.getElementById('f-writer-system').value = p.writer_system || '';
  document.getElementById('f-writer-prompt').value = p.writer_prompt || '';

  // Slides
  renderSlides();

  // Outputs
  renderOutputs();

  // Providers
  loadProviders();

  // Activate first tab
  switchTab('info');
}

function renderSlides() {
  const slides = currentProject.slides || [];
  const container = document.getElementById('slidesList');
  const empty = document.getElementById('slidesEmpty');
  const toolbar = document.getElementById('slidesToolbar');

  if (!slides.length) {
    container.innerHTML = '';
    empty.style.display = '';
    toolbar.style.display = 'none';
    return;
  }

  empty.style.display = 'none';
  toolbar.style.display = '';
  container.innerHTML = slides.map((s, i) => `
    <div class="slide-card ${selectedSlideIndex === i ? 'selected' : ''}" onclick="selectSlide(${i})">
      <div class="slide-num">${s.slide_num || i + 1}</div>
      <div class="slide-body">
        <div class="slide-meta">
          <span>${esc(s.layout || 'bullets')}</span>
          <span>Act ${s.act || '?'}</span>
        </div>
        <h4><input value="${esc(s.title || '')}" onchange="updateSlide(${i}, 'title', this.value)" onclick="event.stopPropagation()" style="border:none;padding:0;font-size:14px;font-weight:600;width:100%"></h4>
        <textarea onchange="updateSlide(${i}, 'body_text', this.value)" onclick="event.stopPropagation()" placeholder="正文/要点...">${esc(s.body_text || '')}</textarea>
        ${(s.bullets || []).length ? `<div style="margin-top:6px;font-size:12px;color:var(--text3)">要点: ${s.bullets.map(b => esc(b)).join(' / ')}</div>` : ''}
      </div>
    </div>
  `).join('');
}

function selectSlide(index) {
  selectedSlideIndex = index;
  renderSlides();
}

function moveSlide(direction) {
  if (selectedSlideIndex === null) {
    toast('请先点击选择一张幻灯片');
    return;
  }

  const slides = currentProject.slides || [];
  const newIndex = selectedSlideIndex + direction;

  if (newIndex < 0 || newIndex >= slides.length) {
    toast('已经到达边界');
    return;
  }

  // Swap slides
  const temp = slides[selectedSlideIndex];
  slides[selectedSlideIndex] = slides[newIndex];
  slides[newIndex] = temp;

  // Update slide numbers
  slides[selectedSlideIndex].slide_num = selectedSlideIndex + 1;
  slides[newIndex].slide_num = newIndex + 1;

  selectedSlideIndex = newIndex;
  renderSlides();
  toast('顺序已调整');
}

function renderOutputs() {
  const outputs = currentProject.outputs || [];
  const container = document.getElementById('outputsList');
  const empty = document.getElementById('outputsEmpty');

  if (!outputs.length) {
    container.innerHTML = '';
    empty.style.display = '';
    return;
  }

  empty.style.display = 'none';
  container.innerHTML = outputs.map(o => `
    <div class="output-item">
      <div class="out-icon ${o.ext.slice(1)}">${o.ext.slice(1).toUpperCase()}</div>
      <div class="out-info">
        <div class="out-name">${esc(o.name)}</div>
        <div class="out-meta">${o.size_kb} KB · ${o.created}</div>
      </div>
      <div class="out-actions">
        ${o.ext === '.html' ? `
          <button class="btn btn-sm btn-secondary" onclick="previewOutput('${esc(o.name)}')">👁 预览</button>
          <button class="btn btn-sm btn-primary" onclick="showShareModal('${currentId}', '${esc(o.name)}')">📤 分享</button>
        ` : ''}
        <a class="btn btn-sm btn-primary" href="/api/projects/${currentId}/output/${encodeURIComponent(o.name)}" download>⬇ 下载</a>
      </div>
    </div>
  `).join('');
}

function updateSlide(index, field, value) {
  if (currentProject.slides[index]) {
    currentProject.slides[index][field] = value;
  }
}

// ── Save ─────────────────────────────────────────
async function saveProject() {
  if (!currentId) return;
  const data = {
    topic: document.getElementById('f-topic').value,
    brief: document.getElementById('f-brief').value,
    audience: document.getElementById('f-audience').value,
    planner_system: document.getElementById('f-planner-system').value,
    planner_prompt: document.getElementById('f-planner-prompt').value,
    writer_system: document.getElementById('f-writer-system').value,
    writer_prompt: document.getElementById('f-writer-prompt').value,
  };
  await api(`/api/projects/${currentId}`, 'PUT', data);
  await api(`/api/projects/${currentId}/slides`, 'PUT', currentProject.slides || []);
  toast('已保存');
  currentProject = await api(`/api/projects/${currentId}`);
  loadProjects();
}

// ── Delete ───────────────────────────────────────
async function deleteProject() {
  if (!currentId) return;
  if (!confirm(`确定要删除项目「${currentProject.topic}」吗？此操作不可恢复。`)) return;

  await api(`/api/projects/${currentId}`, 'DELETE');
  toast('项目已删除');

  // Reset state
  currentId = null;
  currentProject = null;
  selectedSlideIndex = null;

  // Reset UI
  document.getElementById('headerTitle').textContent = '选择一个项目';
  document.getElementById('btnSave').style.display = 'none';
  document.getElementById('btnDelete').style.display = 'none';
  document.getElementById('tabBar').style.display = 'none';
  document.getElementById('emptyState').style.display = '';

  // Reload project list
  await loadProjects();
}

// ── Generate ─────────────────────────────────────
async function generate() {
  if (!currentId) return;
  await saveProject();

  const provider = document.getElementById('f-provider').value;
  const format = document.getElementById('f-format').value;
  const btn = document.getElementById('btnGenerate');
  const status = document.getElementById('genStatus');

  btn.disabled = true;
  btn.textContent = '⏳ 生成中...';
  status.className = 'gen-status show running';
  status.textContent = '正在启动...';

  await api(`/api/projects/${currentId}/generate`, 'POST', { provider, format });

  // Poll status
  const poll = setInterval(async () => {
    const s = await api(`/api/projects/${currentId}/status`);
    status.textContent = s.progress;

    if (s.status === 'done') {
      clearInterval(poll);
      status.className = 'gen-status show done';
      status.innerHTML = `✅ ${s.progress}<br>输出: ${(s.outputs || []).join(', ')}`;
      btn.disabled = false;
      btn.textContent = '🚀 开始生成';
      currentProject = await api(`/api/projects/${currentId}`);
      renderSlides();
      renderOutputs();
    } else if (s.status === 'error') {
      clearInterval(poll);
      status.className = 'gen-status show error';
      status.textContent = '❌ ' + s.progress;
      btn.disabled = false;
      btn.textContent = '🚀 开始生成';
    }
  }, 1500);
}

// ── Providers ────────────────────────────────────
async function loadProviders() {
  const providers = await api('/api/providers');
  const sel = document.getElementById('f-provider');
  sel.innerHTML = Object.entries(providers).map(([name, cfg]) =>
    `<option value="${name}" ${cfg.available ? '' : 'disabled'}>${name} — ${cfg.model} ${cfg.available ? '' : '(未配置)'}</option>`
  ).join('');
}

// ── Reset Prompts ────────────────────────────────
async function resetPrompts(type) {
  if (!confirm(`恢复${type === 'planner' ? '规划' : '内容生成'}提示词为默认值？`)) return;
  const defaults = await api('/api/prompts/default');
  if (type === 'planner') {
    document.getElementById('f-planner-system').value = defaults.planner_system;
    document.getElementById('f-planner-prompt').value = defaults.planner_prompt;
  } else {
    document.getElementById('f-writer-system').value = defaults.writer_system;
    document.getElementById('f-writer-prompt').value = defaults.writer_prompt;
  }
  toast('已恢复默认');
}

// ── Preview ──────────────────────────────────────
function previewOutput(filename) {
  window.open(`/api/projects/${currentId}/output/${encodeURIComponent(filename)}`, '_blank');
}

// ── Tab Switching ────────────────────────────────
function switchTab(name) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.toggle('active', b.dataset.tab === name));
  document.querySelectorAll('.tab-pane').forEach(p => p.classList.toggle('active', p.id === `pane-${name}`));
}

document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => switchTab(btn.dataset.tab));
});

// ── Helpers ──────────────────────────────────────
function esc(s) { if (!s) return ''; const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }

// ── Init ─────────────────────────────────────────
loadProjects();

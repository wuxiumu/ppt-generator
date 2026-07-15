// ── State ────────────────────────────────────────
let currentProject = null;
let currentId = null;
let selectedSlideIndex = null;
let allProjects = [];
let editingSlideIndex = null;
let editingSlideData = null;
let authToken = null;  // Session token
let captchaId = null;  // Current captcha ID

// ── Auth ─────────────────────────────────────────
function loadToken() {
  try { authToken = sessionStorage.getItem('admin_token') || null; } catch(e) {}
}

function saveToken(token) {
  authToken = token;
  try { sessionStorage.setItem('admin_token', token); } catch(e) {}
}

function clearToken() {
  authToken = null;
  try { sessionStorage.removeItem('admin_token'); } catch(e) {}
}

async function refreshCaptcha() {
  try {
    const res = await fetch('/api/captcha');
    const data = await res.json();
    captchaId = data.captcha_id;
    const img = document.getElementById('captchaImg');
    if (img) {
      const b64 = res.headers.get('X-Captcha-Image');
      img.src = 'data:image/png;base64,' + b64;
    }
  } catch(e) {
    console.error('Captcha load failed:', e);
  }
}

async function handleLogin(e) {
  e.preventDefault();
  const btn = document.getElementById('loginBtn');
  const errEl = document.getElementById('loginError');
  errEl.textContent = '';

  const username = document.getElementById('loginUser').value.trim();
  const password = document.getElementById('loginPass').value;
  const captchaCode = document.getElementById('loginCaptcha').value.trim();

  if (!username || !password) { errEl.textContent = '请输入账号和密码'; return; }
  if (!captchaCode) { errEl.textContent = '请输入验证码'; return; }

  btn.disabled = true;
  btn.textContent = '登录中...';

  try {
    const res = await fetch('/api/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password, captcha_id: captchaId, captcha_code: captchaCode })
    });
    const data = await res.json();

    if (res.ok && data.token) {
      saveToken(data.token);
      showApp();
    } else {
      errEl.textContent = data.error || '登录失败';
      refreshCaptcha();
      document.getElementById('loginCaptcha').value = '';
    }
  } catch(err) {
    errEl.textContent = '网络错误，请重试';
    refreshCaptcha();
  }

  btn.disabled = false;
  btn.textContent = '登 录';
}

async function logout() {
  try {
    await fetch('/api/logout', {
      method: 'POST',
      headers: { 'Authorization': 'Bearer ' + (authToken || '') }
    });
  } catch(e) {}
  clearToken();
  location.reload();
}

function showApp() {
  document.getElementById('loginOverlay').classList.add('hidden');
}

function showLogin() {
  document.getElementById('loginOverlay').classList.remove('hidden');
  refreshCaptcha();
}

async function checkAuth() {
  loadToken();
  if (!authToken) { showLogin(); return false; }
  try {
    const res = await fetch('/api/check-auth', {
      headers: { 'Authorization': 'Bearer ' + authToken }
    });
    if (res.ok) { showApp(); return true; }
  } catch(e) {}
  clearToken();
  showLogin();
  return false;
}

// ── Mobile Sidebar ───────────────────────────────
function toggleSidebar() {
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('sidebarOverlay');
  const btn = document.getElementById('hamburgerBtn');
  const isOpen = sidebar.classList.contains('open');

  sidebar.classList.toggle('open');
  overlay.classList.toggle('show');
  btn.classList.toggle('active');
}

function closeSidebar() {
  document.getElementById('sidebar').classList.remove('open');
  document.getElementById('sidebarOverlay').classList.remove('show');
  document.getElementById('hamburgerBtn').classList.remove('active');
}

// ── URL Routing ──────────────────────────────────
function updateURL() {
  const hash = currentId ? `#${currentId}/${currentTab || 'info'}` : '';
  history.replaceState(null, '', hash || window.location.pathname);
}

function parseURL() {
  const hash = window.location.hash.slice(1);
  if (!hash) return { projectId: null, tab: 'info' };
  const [projectId, tab] = hash.split('/');
  return { projectId, tab: tab || 'info' };
}

let currentTab = 'info';

// ── API helpers ──────────────────────────────────
async function api(url, method = 'GET', body = null) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json' }
  };
  if (authToken) opts.headers['Authorization'] = 'Bearer ' + authToken;
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(url, opts);

  // Auto-logout on 401
  if (res.status === 401) {
    clearToken();
    showLogin();
    throw new Error('Session expired');
  }

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
  updateURL();

  // Mobile: close sidebar and update title
  closeSidebar();
  const mt = document.getElementById('mobileTitle');
  if (mt) mt.textContent = currentProject.topic || 'PPT Generator';
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
  container.innerHTML = slides.map((s, i) => {
    // Build preview content based on layout
    let preview = '';

    if (s.bullets && s.bullets.length > 0) {
      preview = `<div class="slide-preview-bullets">${s.bullets.map(b => `• ${esc(b)}`).join('<br>')}</div>`;
    } else if (s.body_text) {
      preview = `<div class="slide-preview-text">${esc(s.body_text)}</div>`;
    } else if (s.highlight) {
      preview = `<div class="slide-preview-highlight">${esc(s.highlight)}</div>`;
    } else if (s.code) {
      preview = `<div class="slide-preview-code">${esc(s.code).substring(0, 100)}${s.code.length > 100 ? '...' : ''}</div>`;
    } else if (s.left_title || s.right_title) {
      preview = `<div class="slide-preview-comparison">
        <div class="comp-col"><strong>${esc(s.left_title || '左栏')}</strong>: ${(s.left_bullets || []).length} 项</div>
        <div class="comp-col"><strong>${esc(s.right_title || '右栏')}</strong>: ${(s.right_bullets || []).length} 项</div>
      </div>`;
    }

    return `
    <div class="slide-card ${selectedSlideIndex === i ? 'selected' : ''}" onclick="selectSlide(${i})">
      <div class="slide-num">${s.slide_num || i + 1}</div>
      <div class="slide-body">
        <div class="slide-header">
          <div class="slide-meta">
            <span class="layout-badge">${esc(s.layout || 'bullets')}</span>
            <span class="act-badge">Act ${s.act || '?'}</span>
          </div>
          <button class="btn-copy-md" onclick="event.stopPropagation(); copySlideAsMarkdown(${i})" title="复制为 Markdown">📋</button>
        </div>
        <h4 class="slide-title">${esc(s.title || '无标题')}</h4>
        ${s.subtitle ? `<div class="slide-subtitle">${esc(s.subtitle)}</div>` : ''}
        ${preview}
        <div class="slide-actions">
          <button class="btn-edit" onclick="event.stopPropagation(); openSlideEditor(${i})">✏️ 编辑</button>
        </div>
      </div>
    </div>
    `;
  }).join('');
}

function selectSlide(index) {
  selectedSlideIndex = selectedSlideIndex === index ? null : index;
  renderSlides();
}

// ── Copy as Markdown ─────────────────────────────
function copySlideAsMarkdown(index) {
  const slide = currentProject.slides[index];
  if (!slide) return;

  let md = '';

  // Title
  md += `## ${slide.title || '无标题'}\n\n`;

  // Subtitle
  if (slide.subtitle) {
    md += `**${slide.subtitle}**\n\n`;
  }

  // Body text
  if (slide.body_text) {
    md += `${slide.body_text}\n\n`;
  }

  // Bullets
  if (slide.bullets && slide.bullets.length > 0) {
    md += slide.bullets.map(b => `- ${b}`).join('\n') + '\n\n';
  }

  // Highlight (big_number)
  if (slide.highlight) {
    md += `> **${slide.highlight}**\n\n`;
  }

  // Code
  if (slide.code) {
    md += '```python\n' + slide.code + '\n```\n\n';
  }

  // Annotations
  if (slide.annotations && slide.annotations.length > 0) {
    md += '**注释：**\n';
    md += slide.annotations.map(a => `- ${a}`).join('\n') + '\n\n';
  }

  // Comparison
  if (slide.left_title || slide.right_title) {
    if (slide.left_title) {
      md += `### ${slide.left_title}\n`;
      if (slide.left_bullets && slide.left_bullets.length > 0) {
        md += slide.left_bullets.map(b => `- ${b}`).join('\n') + '\n\n';
      }
    }
    if (slide.right_title) {
      md += `### ${slide.right_title}\n`;
      if (slide.right_bullets && slide.right_bullets.length > 0) {
        md += slide.right_bullets.map(b => `- ${b}`).join('\n') + '\n\n';
      }
    }
  }

  // Speaker notes
  if (slide.speaker_notes) {
    md += `---\n*演讲备注：${slide.speaker_notes}*\n`;
  }

  // Copy to clipboard
  navigator.clipboard.writeText(md).then(() => {
    toast('已复制为 Markdown');
  }).catch(err => {
    toast('复制失败：' + err.message);
  });
}

function copyAllSlidesAsMarkdown() {
  const slides = currentProject.slides || [];
  if (slides.length === 0) {
    toast('没有幻灯片可复制');
    return;
  }

  let allMd = '';
  const projectTitle = currentProject.topic || '演示文稿';

  // Add project title
  allMd += `# ${projectTitle}\n\n`;

  // Convert each slide
  slides.forEach((slide, index) => {
    let md = '';

    // Title
    md += `## ${slide.title || '无标题'}\n\n`;

    // Subtitle
    if (slide.subtitle) {
      md += `**${slide.subtitle}**\n\n`;
    }

    // Body text
    if (slide.body_text) {
      md += `${slide.body_text}\n\n`;
    }

    // Bullets
    if (slide.bullets && slide.bullets.length > 0) {
      md += slide.bullets.map(b => `- ${b}`).join('\n') + '\n\n';
    }

    // Highlight (big_number)
    if (slide.highlight) {
      md += `> **${slide.highlight}**\n\n`;
    }

    // Code
    if (slide.code) {
      md += '```python\n' + slide.code + '\n```\n\n';
    }

    // Annotations
    if (slide.annotations && slide.annotations.length > 0) {
      md += '**注释：**\n';
      md += slide.annotations.map(a => `- ${a}`).join('\n') + '\n\n';
    }

    // Comparison
    if (slide.left_title || slide.right_title) {
      if (slide.left_title) {
        md += `### ${slide.left_title}\n`;
        if (slide.left_bullets && slide.left_bullets.length > 0) {
          md += slide.left_bullets.map(b => `- ${b}`).join('\n') + '\n\n';
        }
      }
      if (slide.right_title) {
        md += `### ${slide.right_title}\n`;
        if (slide.right_bullets && slide.right_bullets.length > 0) {
          md += slide.right_bullets.map(b => `- ${b}`).join('\n') + '\n\n';
        }
      }
    }

    // Speaker notes
    if (slide.speaker_notes) {
      md += `*演讲备注：${slide.speaker_notes}*\n`;
    }

    // Add slide separator (except for the last slide)
    if (index < slides.length - 1) {
      md += '\n---\n\n';
    }

    allMd += md;
  });

  // Copy to clipboard
  navigator.clipboard.writeText(allMd).then(() => {
    toast(`已复制全部 ${slides.length} 张幻灯片`);
  }).catch(err => {
    toast('复制失败：' + err.message);
  });
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
  currentTab = name;
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.toggle('active', b.dataset.tab === name));
  document.querySelectorAll('.tab-pane').forEach(p => p.classList.toggle('active', p.id === `pane-${name}`));
  updateURL();
}

document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => switchTab(btn.dataset.tab));
});

// ── Helpers ──────────────────────────────────────
function esc(s) { if (!s) return ''; const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }

// ── Slide Editor ─────────────────────────────────
function getFieldsForLayout(layout) {
  const common = ['title', 'subtitle', 'body_text', 'speaker_notes'];
  const layoutFields = {
    title: ['subtitle'],
    section: [],
    bullets: ['bullets'],
    statement: [],
    comparison: ['left_title', 'left_bullets', 'right_title', 'right_bullets'],
    big_number: ['highlight'],
    code: ['code', 'annotations'],
    end: []
  };
  return [...new Set([...common, ...(layoutFields[layout] || [])])];
}

function openSlideEditor(index) {
  editingSlideIndex = index;
  editingSlideData = JSON.parse(JSON.stringify(currentProject.slides[index])); // Deep copy

  const modal = document.getElementById('slideEditorModal');
  const slideNum = document.getElementById('editorSlideNum');
  const layout = document.getElementById('editorLayout');
  const act = document.getElementById('editorAct');
  const body = document.getElementById('editorBody');

  slideNum.textContent = editingSlideData.slide_num || (index + 1);
  layout.textContent = editingSlideData.layout || 'bullets';
  act.textContent = `Act ${editingSlideData.act || '?'}`;

  renderEditorFields();
  modal.classList.add('show');
}

function renderEditorFields() {
  const body = document.getElementById('editorBody');
  const layout = editingSlideData.layout || 'bullets';
  const fields = getFieldsForLayout(layout);

  let html = '';

  // Title
  if (fields.includes('title')) {
    html += `
      <div class="editor-field">
        <label>标题</label>
        <input type="text" id="edit-title" value="${esc(editingSlideData.title || '')}" placeholder="幻灯片标题">
      </div>
    `;
  }

  // Subtitle
  if (fields.includes('subtitle')) {
    html += `
      <div class="editor-field">
        <label>副标题</label>
        <input type="text" id="edit-subtitle" value="${esc(editingSlideData.subtitle || '')}" placeholder="副标题（可选）">
      </div>
    `;
  }

  // Body text
  if (fields.includes('body_text')) {
    html += `
      <div class="editor-field">
        <label>正文</label>
        <textarea id="edit-body_text" rows="3" placeholder="正文内容">${esc(editingSlideData.body_text || '')}</textarea>
      </div>
    `;
  }

  // Bullets
  if (fields.includes('bullets')) {
    const bullets = editingSlideData.bullets || [];
    html += `
      <div class="editor-field">
        <label>要点列表</label>
        <div class="bullets-editor" id="edit-bullets">
          ${bullets.map((b, i) => `
            <div class="bullet-item">
              <input type="text" value="${esc(b)}" onchange="updateBullet(${i}, this.value)" placeholder="要点 ${i + 1}">
              <button class="btn-icon" onclick="removeBullet(${i})" title="删除">×</button>
            </div>
          `).join('')}
          <button class="btn btn-sm btn-secondary" onclick="addBullet()">+ 添加要点</button>
        </div>
      </div>
    `;
  }

  // Highlight (big_number)
  if (fields.includes('highlight')) {
    html += `
      <div class="editor-field">
        <label>大数字</label>
        <input type="text" id="edit-highlight" value="${esc(editingSlideData.highlight || '')}" placeholder="例: 300万+">
      </div>
    `;
  }

  // Code
  if (fields.includes('code')) {
    html += `
      <div class="editor-field">
        <label>代码</label>
        <textarea id="edit-code" rows="8" class="code-editor" placeholder="代码内容">${esc(editingSlideData.code || '')}</textarea>
      </div>
    `;
  }

  // Annotations
  if (fields.includes('annotations')) {
    const annotations = editingSlideData.annotations || [];
    html += `
      <div class="editor-field">
        <label>注释</label>
        <div class="annotations-editor" id="edit-annotations">
          ${annotations.map((a, i) => `
            <div class="annotation-item">
              <input type="text" value="${esc(a)}" onchange="updateAnnotation(${i}, this.value)" placeholder="注释 ${i + 1}">
              <button class="btn-icon" onclick="removeAnnotation(${i})" title="删除">×</button>
            </div>
          `).join('')}
          <button class="btn btn-sm btn-secondary" onclick="addAnnotation()">+ 添加注释</button>
        </div>
      </div>
    `;
  }

  // Comparison - Left
  if (fields.includes('left_title')) {
    html += `
      <div class="editor-field comparison-field">
        <label>左栏标题</label>
        <input type="text" id="edit-left_title" value="${esc(editingSlideData.left_title || '')}" placeholder="左栏标题">
      </div>
    `;
  }

  if (fields.includes('left_bullets')) {
    const leftBullets = editingSlideData.left_bullets || [];
    html += `
      <div class="editor-field comparison-field">
        <label>左栏要点</label>
        <div class="bullets-editor">
          ${leftBullets.map((b, i) => `
            <div class="bullet-item">
              <input type="text" value="${esc(b)}" onchange="updateLeftBullet(${i}, this.value)" placeholder="左栏要点 ${i + 1}">
              <button class="btn-icon" onclick="removeLeftBullet(${i})" title="删除">×</button>
            </div>
          `).join('')}
          <button class="btn btn-sm btn-secondary" onclick="addLeftBullet()">+ 添加</button>
        </div>
      </div>
    `;
  }

  // Comparison - Right
  if (fields.includes('right_title')) {
    html += `
      <div class="editor-field comparison-field">
        <label>右栏标题</label>
        <input type="text" id="edit-right_title" value="${esc(editingSlideData.right_title || '')}" placeholder="右栏标题">
      </div>
    `;
  }

  if (fields.includes('right_bullets')) {
    const rightBullets = editingSlideData.right_bullets || [];
    html += `
      <div class="editor-field comparison-field">
        <label>右栏要点</label>
        <div class="bullets-editor">
          ${rightBullets.map((b, i) => `
            <div class="bullet-item">
              <input type="text" value="${esc(b)}" onchange="updateRightBullet(${i}, this.value)" placeholder="右栏要点 ${i + 1}">
              <button class="btn-icon" onclick="removeRightBullet(${i})" title="删除">×</button>
            </div>
          `).join('')}
          <button class="btn btn-sm btn-secondary" onclick="addRightBullet()">+ 添加</button>
        </div>
      </div>
    `;
  }

  // Speaker notes
  if (fields.includes('speaker_notes')) {
    html += `
      <div class="editor-field">
        <label>演讲备注</label>
        <textarea id="edit-speaker_notes" rows="3" placeholder="演讲备注（可选）">${esc(editingSlideData.speaker_notes || '')}</textarea>
      </div>
    `;
  }

  body.innerHTML = html;
}

// Bullet management
function addBullet() {
  editingSlideData.bullets = editingSlideData.bullets || [];
  editingSlideData.bullets.push('');
  renderEditorFields();
}

function removeBullet(index) {
  editingSlideData.bullets.splice(index, 1);
  renderEditorFields();
}

function updateBullet(index, value) {
  editingSlideData.bullets[index] = value;
}

// Annotation management
function addAnnotation() {
  editingSlideData.annotations = editingSlideData.annotations || [];
  editingSlideData.annotations.push('');
  renderEditorFields();
}

function removeAnnotation(index) {
  editingSlideData.annotations.splice(index, 1);
  renderEditorFields();
}

function updateAnnotation(index, value) {
  editingSlideData.annotations[index] = value;
}

// Left bullets (comparison)
function addLeftBullet() {
  editingSlideData.left_bullets = editingSlideData.left_bullets || [];
  editingSlideData.left_bullets.push('');
  renderEditorFields();
}

function removeLeftBullet(index) {
  editingSlideData.left_bullets.splice(index, 1);
  renderEditorFields();
}

function updateLeftBullet(index, value) {
  editingSlideData.left_bullets[index] = value;
}

// Right bullets (comparison)
function addRightBullet() {
  editingSlideData.right_bullets = editingSlideData.right_bullets || [];
  editingSlideData.right_bullets.push('');
  renderEditorFields();
}

function removeRightBullet(index) {
  editingSlideData.right_bullets.splice(index, 1);
  renderEditorFields();
}

function updateRightBullet(index, value) {
  editingSlideData.right_bullets[index] = value;
}

function saveSlideEdit() {
  // Collect form data
  const fields = ['title', 'subtitle', 'body_text', 'highlight', 'code', 'speaker_notes', 'left_title', 'right_title'];

  fields.forEach(field => {
    const input = document.getElementById(`edit-${field}`);
    if (input) {
      editingSlideData[field] = input.value;
    }
  });

  // Update slide in project (save to memory only, not backend)
  currentProject.slides[editingSlideIndex] = editingSlideData;

  // Re-render slides list to show updated content
  renderSlides();
}

function closeSlideEditor() {
  // Save changes to memory before closing
  if (editingSlideIndex !== null && editingSlideData) {
    saveSlideEdit();
  }

  document.getElementById('slideEditorModal').classList.remove('show');
  editingSlideIndex = null;
  editingSlideData = null;
}

// ── Preview ──────────────────────────────────────
async function previewSlides() {
  if (!currentId) return;

  // Save current changes first
  await saveProject();

  toast('正在生成预览...');

  try {
    const result = await api(`/api/projects/${currentId}/preview`, 'POST', { format: 'html' });

    if (result.ok && result.outputs && result.outputs.length > 0) {
      const htmlOutput = result.outputs.find(o => o.type === 'html');
      if (htmlOutput) {
        // Open preview in new window
        window.open(htmlOutput.url, '_blank');
        toast('预览已生成');
      }
    } else {
      toast('预览生成失败：' + (result.error || '未知错误'));
    }
  } catch (error) {
    toast('预览生成失败：' + error.message);
  }
}

// ── History ──────────────────────────────────────
async function showHistory() {
  if (!currentId) return;

  try {
    const history = await api(`/api/projects/${currentId}/history`);

    const modal = document.getElementById('historyModal');
    const list = document.getElementById('historyList');
    const count = document.getElementById('historyCount');

    count.textContent = history.length;

    if (history.length === 0) {
      list.innerHTML = '<div class="empty"><h3>暂无历史版本</h3><p>编辑幻灯片后会自动保存版本</p></div>';
    } else {
      // Show in reverse order (newest first)
      list.innerHTML = history.slice().reverse().map(h => `
        <div class="history-item">
          <div class="history-info">
            <div class="history-version">版本 ${h.version}</div>
            <div class="history-time">${formatTime(h.timestamp)}</div>
            <div class="history-note">${esc(h.note || '无备注')}</div>
          </div>
          <div class="history-actions">
            <button class="btn btn-sm btn-secondary" onclick="rollbackToVersion(${h.version})">回滚到此版本</button>
          </div>
        </div>
      `).join('');
    }

    modal.classList.add('show');
  } catch (error) {
    toast('获取历史记录失败：' + error.message);
  }
}

async function rollbackToVersion(version) {
  if (!confirm(`确定要回滚到版本 ${version} 吗？当前内容会被覆盖。`)) return;

  try {
    const result = await api(`/api/projects/${currentId}/rollback/${version}`, 'POST');

    if (result.ok) {
      toast('已回滚到版本 ' + version);
      closeHistory();

      // Reload project
      currentProject = await api(`/api/projects/${currentId}`);
      renderSlides();
    } else {
      toast('回滚失败：' + (result.error || '未知错误'));
    }
  } catch (error) {
    toast('回滚失败：' + error.message);
  }
}

function closeHistory() {
  document.getElementById('historyModal').classList.remove('show');
}

function formatTime(timestamp) {
  if (!timestamp) return '';
  const date = new Date(timestamp);
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  });
}

// ── Info Modals ──────────────────────────────────
function showAbout() {
  renderModalContent('about');
  document.getElementById('aboutModal').classList.add('show');
}

function closeAbout() {
  document.getElementById('aboutModal').classList.remove('show');
}

function showContact() {
  renderModalContent('contact');
  document.getElementById('contactModal').classList.add('show');
}

function closeContact() {
  document.getElementById('contactModal').classList.remove('show');
}

function showPrivacy() {
  renderModalContent('privacy');
  document.getElementById('privacyModal').classList.add('show');
}

function closePrivacy() {
  document.getElementById('privacyModal').classList.remove('show');
}

// ── Init ─────────────────────────────────────────
async function init() {
  // Wire up login form
  document.getElementById('loginForm').addEventListener('submit', handleLogin);

  // Wire up hamburger
  document.getElementById('hamburgerBtn').addEventListener('click', toggleSidebar);

  // Check auth first
  const ok = await checkAuth();
  if (!ok) return;

  // Load app data
  await loadProjects();
  await loadFooter();
  await loadModals();

  // Restore state from URL
  const { projectId, tab } = parseURL();
  if (projectId && allProjects.find(p => p.id === projectId)) {
    await selectProject(projectId);
    switchTab(tab);
  }
}

async function loadFooter() {
  try {
    const config = await api('/api/config/footer');

    // Render links
    const linksContainer = document.getElementById('footerLinks');
    linksContainer.innerHTML = config.links.map(link => {
      if (link.external) {
        return `<a href="${link.url}" target="_blank">${link.icon} ${esc(link.text)}</a>`;
      } else if (link.action) {
        return `<a href="#" onclick="${link.action}(); return false;">${link.icon} ${esc(link.text)}</a>`;
      }
      return '';
    }).join('');

    // Render copyright
    const infoContainer = document.getElementById('footerInfo');
    infoContainer.innerHTML = config.copyright.map(line => `<p>${esc(line)}</p>`).join('');

  } catch (error) {
    console.error('Failed to load footer config:', error);
  }
}

let modalsConfig = null;

async function loadModals() {
  try {
    modalsConfig = await api('/api/config/modals');
  } catch (error) {
    console.error('Failed to load modals config:', error);
  }
}

function renderModalContent(modalKey) {
  if (!modalsConfig || !modalsConfig[modalKey]) return;

  const modal = modalsConfig[modalKey];
  const titleEl = document.getElementById(`${modalKey}Title`);
  const contentEl = document.getElementById(`${modalKey}Content`);

  if (titleEl) titleEl.textContent = modal.title;

  if (contentEl) {
    contentEl.innerHTML = modal.content.map(block => {
      if (block.type === 'paragraph') {
        const style = block.style === 'small' ? ' style="font-size:12px;color:var(--text3);margin-top:16px"' : '';
        return `<p${style}>${block.text}</p>`;
      } else if (block.type === 'heading') {
        return `<h4>${block.text}</h4>`;
      } else if (block.type === 'list') {
        return `<ul>${block.items.map(item => `<li>${item}</li>`).join('')}</ul>`;
      }
      return '';
    }).join('');
  }
}

init();

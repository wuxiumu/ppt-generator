// ── Share / QR Code ─────────────────────────────
let shareBaseUrl = '';

async function initShareInfo() {
  const info = await api('/api/share-info');
  shareBaseUrl = info.base_url;
}

async function showShareModal(pid, filename) {
  if (!shareBaseUrl) await initShareInfo();
  const url = `${shareBaseUrl}/share/${pid}/${encodeURIComponent(filename)}`;

  // Set URL input
  document.getElementById('shareUrlInput').value = url;
  document.getElementById('shareOpenBtn').href = url;

  // Generate QR code
  const container = document.getElementById('qrContainer');
  container.innerHTML = '';
  new QRCode(container, {
    text: url,
    width: 180,
    height: 180,
    colorDark: '#1a1a2e',
    colorLight: '#ffffff',
    correctLevel: QRCode.CorrectLevel.M,
  });

  document.getElementById('shareModal').classList.add('show');
}

function closeShareModal() {
  document.getElementById('shareModal').classList.remove('show');
}

function copyShareUrl() {
  const input = document.getElementById('shareUrlInput');
  input.select();
  navigator.clipboard.writeText(input.value).then(() => toast('链接已复制'));
}

// Close modal on overlay click
document.getElementById('shareModal').addEventListener('click', function(e) {
  if (e.target === this) closeShareModal();
});

// Close slide editor modal on overlay click
document.getElementById('slideEditorModal').addEventListener('click', function(e) {
  if (e.target === this) closeSlideEditor();
});

// Close history modal on overlay click
document.getElementById('historyModal').addEventListener('click', function(e) {
  if (e.target === this) closeHistory();
});

// Close modal on Escape key
document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape') {
    closeShareModal();
    closeAllProjects();
  }
});

// Init share info on load
initShareInfo();

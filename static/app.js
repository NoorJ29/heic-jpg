let currentFiles = [];
let currentQuality = 100;
let sidebarOpen = false;
let sessionId = null;

const tierColors = {
  lossless: '#3fb950', high: '#58a6ff', standard: '#d29922', low: '#f85149'
};
const tierHints = {
  lossless: '\u{1F4E6} Best quality, larger files',
  high: '\u{1F4E6} Best quality, larger files',
  standard: '\u{1F4E6} Balanced size & quality',
  low: '\u{1F4E6} Smaller files, quality loss'
};

function getTier(q) {
  if (q == 100) return 'lossless';
  if (q >= 95) return 'high';
  if (q >= 70) return 'standard';
  return 'low';
}

function setQuality(val) {
  currentQuality = val;
  document.getElementById('quality-slider').value = val;
  updateQuality(val);
  document.querySelectorAll('.preset-btn').forEach(b => {
    b.classList.toggle('active', parseInt(b.dataset.quality) === val);
  });
}

function updateQuality(val) {
  currentQuality = parseInt(val);
  const tier = getTier(currentQuality);
  const color = tierColors[tier];
  document.getElementById('quality-label').textContent = currentQuality + '%';
  document.getElementById('quality-tier').textContent = tier;
  document.getElementById('quality-tier').style.color = color;
  document.getElementById('quality-fill').style.width = currentQuality + '%';
  document.getElementById('quality-fill').style.background = `linear-gradient(90deg,#1f6feb,${color})`;
  document.getElementById('quality-hint').textContent = tierHints[tier];
  document.querySelectorAll('.preset-btn').forEach(b => {
    b.classList.toggle('active', parseInt(b.dataset.quality) === currentQuality);
  });
}

function toggleSidebar() {
  sidebarOpen = !sidebarOpen;
  document.getElementById('sidebar').classList.toggle('open', sidebarOpen);
  document.getElementById('sidebar-overlay').classList.toggle('show', sidebarOpen);
  document.getElementById('sidebar-toggle').innerHTML = sidebarOpen ? '&times;' : '&#9776;';
}

function closeSidebar() {
  sidebarOpen = false;
  document.getElementById('sidebar').classList.remove('open');
  document.getElementById('sidebar-overlay').classList.remove('show');
  document.getElementById('sidebar-toggle').innerHTML = '&#9776;';
}

document.getElementById('sidebar-overlay').onclick = closeSidebar;

const dropzone = document.getElementById('dropzone');
dropzone.addEventListener('dragover', e => { e.preventDefault(); dropzone.classList.add('dragover'); });
dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dragover'));
dropzone.addEventListener('drop', e => {
  e.preventDefault();
  dropzone.classList.remove('dragover');
  handleFiles(e.dataTransfer.files);
});

function handleFiles(files) {
  const valid = [];
  for (const f of files) {
    const ext = f.name.split('.').pop().toLowerCase();
    if (['heic', 'heif'].includes(ext)) valid.push(f);
  }
  if (!valid.length) return;
  currentFiles = currentFiles.concat(valid);
  renderFileList();
}

function renderFileList() {
  const container = document.getElementById('file-list');
  if (!currentFiles.length) {
    container.innerHTML = '';
    document.getElementById('convert-btn').disabled = true;
    return;
  }
  document.getElementById('convert-btn').disabled = false;
  let html = `<div class="text-xs text-[#8b949e] mb-1"><strong class="text-[#58a6ff]">${currentFiles.length}</strong> file(s) selected</div>`;
  for (const f of currentFiles) {
    const stem = f.name.replace(/\.[^.]+$/, '');
    const kb = f.size / 1024;
    const sizeStr = kb < 1024 ? kb.toFixed(1) + ' KB' : (kb / 1024).toFixed(1) + ' MB';
    html += `<div class="file-row">
      <span class="text-[#e6edf3]">${f.name}</span>
      <span><span class="text-[#8b949e]">${sizeStr}</span>
      <span class="text-[#8b949e] mx-1">&rarr;</span>
      <span class="text-[#3fb950]">${stem}.jpg</span></span>
    </div>`;
  }
  container.innerHTML = html;
}

function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / 1048576).toFixed(1) + ' MB';
}

async function convertFiles() {
  if (!currentFiles.length) return;
  const btn = document.getElementById('convert-btn');
  const progressArea = document.getElementById('progress-area');
  const progressFill = document.getElementById('progress-fill');
  const statusText = document.getElementById('status-text');
  const resultsArea = document.getElementById('results-area');

  btn.disabled = true;
  btn.textContent = 'Converting...';
  progressArea.classList.remove('hidden');
  resultsArea.classList.add('hidden');

  const formData = new FormData();
  for (const f of currentFiles) {
    formData.append('files', f);
  }
  formData.append('quality', String(currentQuality));

  try {
    statusText.textContent = 'Uploading...';
    progressFill.style.width = '10%';

    const resp = await fetch('/api/convert', { method: 'POST', body: formData });
    if (!resp.ok) throw new Error('Conversion failed');
    const data = await resp.json();

    progressFill.style.width = '100%';
    statusText.textContent = 'Done!';

    sessionId = data.session_id;
    showResults(data);
    currentFiles = [];
    renderFileList();
    loadHistory();
  } catch (err) {
    statusText.textContent = 'Error: ' + err.message;
    progressFill.style.width = '0%';
  } finally {
    btn.disabled = false;
    btn.textContent = 'Convert All';
  }
}

function showResults(data) {
  const area = document.getElementById('results-area');
  area.classList.remove('hidden');

  const { results, total, quality } = data;
  const savingsColor = total.savings > 0 ? '#3fb950' : '#8b949e';
  const savingsLabel = total.savings > 0 ? Math.abs(total.savings).toFixed(1) + '% smaller' : 'same size';

  let html = `
    <hr class="border-[#30363d] mb-4" />
    <h3 class="font-bold mb-3">Converted</h3>
    <div class="grid grid-cols-3 gap-2 mb-4">
      <div class="card text-center">
        <div class="text-2xl font-bold text-[#58a6ff]">${total.files}</div>
        <div class="text-xs text-[#8b949e]">FILES</div>
      </div>
      <div class="card text-center">
        <div class="text-2xl font-bold" style="color:${savingsColor}">${savingsLabel}</div>
        <div class="text-xs text-[#8b949e]">SIZE CHANGE</div>
      </div>
      <div class="card text-center">
        <div class="text-2xl font-bold text-[#e6edf3]">Q${quality}</div>
        <div class="text-xs text-[#8b949e]">QUALITY</div>
      </div>
    </div>
    <div class="text-xs text-[#8b949e] mb-2">
      <strong class="text-[#e6edf3]">Original:</strong> ${formatSize(total.original)} &rarr;
      <strong class="text-[#e6edf3]">JPG:</strong> ${formatSize(total.converted)}
    </div>
  `;

  for (const r of results) {
    const sc = r.savings > 0 ? '#3fb950' : '#f85149';
    html += `<div class="file-row">
      <span class="text-[#e6edf3]">${r.name}</span>
      <span>
        <span class="text-[#8b949e]">${formatSize(r.original)}</span>
        <span class="text-[#8b949e] mx-1">&rarr;</span>
        <span class="text-[#e6edf3]">${formatSize(r.size)}</span>
        <span class="ml-1" style="color:${sc}">${r.savings}%</span>
      </span>
    </div>`;
  }

  html += `
    <div class="flex gap-2 mt-3">
      <a href="/api/download/${sessionId}/zip" class="flex-1 py-2 rounded-lg text-center text-sm font-semibold bg-gradient-to-r from-[#1f6feb] to-[#58a6ff] text-white no-underline">Download All (${total.files} files)</a>
      <button onclick="resetApp()" class="flex-1 py-2 rounded-lg text-sm font-semibold bg-gradient-to-r from-[#1f6feb] to-[#58a6ff] text-white border-none cursor-pointer">Convert More</button>
    </div>
  `;

  area.innerHTML = html;
}

function resetApp() {
  document.getElementById('results-area').classList.add('hidden');
  document.getElementById('results-area').innerHTML = '';
  document.getElementById('progress-area').classList.add('hidden');
  sessionId = null;
}

async function loadHistory() {
  try {
    const resp = await fetch('/api/history');
    const data = await resp.json();
    const list = document.getElementById('history-list');
    const actions = document.getElementById('history-actions');
    const history = data.history || [];

    if (!history.length) {
      list.innerHTML = '<div class="history-item text-center">No sessions yet</div>';
      actions.style.display = 'none';
      return;
    }

    actions.style.display = 'flex';
    let html = '';
    for (const h of history.slice(-10).reverse()) {
      const ts = (h.timestamp || '?').slice(0, 19).replace('T', ' ');
      const convs = h.conversions || h.renames || [];
      html += `<div class="history-item"><strong>${convs.length} files</strong> &middot; Q${h.quality || '?'} &middot; ${ts}</div>`;
    }
    list.innerHTML = html;
  } catch (e) {
    console.error('Failed to load history', e);
  }
}

async function undoLast() {
  try {
    const resp = await fetch('/api/history/undo', { method: 'POST' });
    const data = await resp.json();
    loadHistory();
  } catch (e) {
    console.error('Undo failed', e);
  }
}

async function clearHistory() {
  try {
    await fetch('/api/history/clear', { method: 'POST' });
    loadHistory();
  } catch (e) {
    console.error('Clear failed', e);
  }
}

document.addEventListener('DOMContentLoaded', () => {
  setQuality(100);
  loadHistory();
});

/* Aria2c 下载器前端逻辑
 * 通信方式：唯一通道 window.pywebview.api（pywebview js_api 桥），
 * 数据更新由后端推送线程调用 window.__push(payload) 驱动。
 */
'use strict';

/* ---------- 工具 ---------- */

const $ = (sel) => document.querySelector(sel);

function fmtBytes(bytes) {
  if (!Number.isFinite(bytes) || bytes <= 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let i = 0, v = bytes;
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i++; }
  return `${v >= 100 || i === 0 ? Math.round(v) : v.toFixed(1)} ${units[i]}`;
}

const fmtSpeed = (n) => `${fmtBytes(n)}/s`;

function fmtPercent(progress) {
  if (!Number.isFinite(progress)) return '0%';
  const p = progress >= 99.95 ? 100 : progress;
  return `${p.toFixed(1)}%`;
}

function baseName(url) {
  try {
    const u = new URL(url);
    const seg = u.pathname.split('/').filter(Boolean).pop();
    return seg ? decodeURIComponent(seg) : u.hostname;
  } catch {
    return url.slice(0, 60);
  }
}

/* ---------- 状态 ---------- */

const state = {
  tasks: [],
  config: null,
  filter: 'all',
  aria2Ok: false,
  aria2Error: null,
  appVersion: '',
  torrentFile: null,   // 新建任务弹窗中已选择的 .torrent 文件路径
};

const STATUS_TEXT = {
  active: '下载中', waiting: '等待中', paused: '已暂停',
  error: '出错', complete: '已完成', removed: '已移除',
};

/* ---------- 后端桥接 ---------- */

async function callApi(method, ...args) {
  if (!window.pywebview || !window.pywebview.api) {
    throw new Error('后端尚未就绪');
  }
  return await window.pywebview.api[method](...args);
}

async function callWithToast(method, ...args) {
  try {
    const result = await callApi(method, ...args);
    if (result && result.message) toast(result.message, 'ok');
    return result;
  } catch (e) {
    toast(cleanError(e), 'error');
    throw e;
  }
}

function cleanError(e) {
  let msg = e instanceof Error ? e.message : String(e);
  // pydantic 校验错误信息太长，只取第一行
  msg = msg.split('\n')[0];
  return msg.length > 200 ? msg.slice(0, 200) + '…' : msg;
}

/* ---------- 渲染 ---------- */

const taskCards = new Map(); // gid -> {card, refs}

function statusBadge(status) {
  const el = document.createElement('span');
  el.className = `status-badge status-${status}`;
  el.textContent = STATUS_TEXT[status] || status;
  return el;
}

function createCard(task) {
  const card = document.createElement('div');
  card.className = 'task-card';
  card.innerHTML = `
    <div class="task-head">
      <div class="task-name"></div>
    </div>
    <div class="progress-wrap">
      <div class="progress"><div class="progress-bar"></div></div>
      <div class="progress-text"></div>
    </div>
    <div class="task-meta">
      <span class="meta-item size"></span>
      <span class="meta-item speed"></span>
      <span class="meta-item conn"></span>
      <div class="task-actions">
        <button class="icon-btn act-pause" title="暂停"></button>
        <button class="icon-btn act-resume" title="继续"></button>
        <button class="icon-btn act-folder" title="打开目录"></button>
        <button class="icon-btn danger act-delete" title="删除"></button>
      </div>
    </div>
    <div class="task-error"></div>`;

  const refs = {
    head: card.querySelector('.task-head'),
    name: card.querySelector('.task-name'),
    bar: card.querySelector('.progress-bar'),
    progressText: card.querySelector('.progress-text'),
    size: card.querySelector('.size'),
    speed: card.querySelector('.meta-item.speed'),
    conn: card.querySelector('.meta-item.conn'),
    err: card.querySelector('.task-error'),
    pause: card.querySelector('.act-pause'),
    resume: card.querySelector('.act-resume'),
    folder: card.querySelector('.act-folder'),
    del: card.querySelector('.act-delete'),
  };

  refs.pause.innerHTML = pauseSvg();
  refs.resume.innerHTML = playSvg();
  refs.folder.innerHTML = folderSvg();
  refs.del.innerHTML = trashSvg();

  refs.pause.addEventListener('click', () => callWithToast('pause_task', task.gid));
  refs.resume.addEventListener('click', () => callWithToast('resume_task', task.gid));
  refs.del.addEventListener('click', async () => {
    const name = displayName(task);
    if (confirm(`确定删除任务「${name}」吗？`)) {
      await callWithToast('remove_task', task.gid);
    }
  });
  refs.folder.addEventListener('click', () => {
    callWithToast('open_folder', task.save_dir).catch(() => {});
  });

  return { card, refs };
}

function displayName(task) {
  return task.filename || (task.urls && task.urls[0] ? baseName(task.urls[0]) : task.gid);
}

function updateCard(task) {
  let entry = taskCards.get(task.gid);
  if (!entry) {
    entry = createCard(task);
    taskCards.set(task.gid, entry);
    $('#taskList').appendChild(entry.card);
  }
  const { card, refs } = entry;

  refs.name.textContent = displayName(task);
  refs.name.title = task.urls ? task.urls.join('\n') : task.gid;

  // 状态徽章
  const badge = refs.head.querySelector('.status-badge');
  const badgeText = STATUS_TEXT[task.status] || task.status;
  if (!badge || badge.textContent !== badgeText) {
    if (badge) badge.remove();
    refs.head.appendChild(statusBadge(task.status));
  }

  refs.bar.style.width = `${task.progress}%`;
  refs.bar.classList.toggle('error', task.status === 'error');
  refs.progressText.textContent = fmtPercent(task.progress);

  refs.size.textContent = `${fmtBytes(task.completed_length)} / ${fmtBytes(task.total_length)}`;
  refs.speed.textContent = task.status === 'active' ? fmtSpeed(task.download_speed) : '';
  refs.speed.hidden = task.status !== 'active';
  refs.conn.textContent = btMetaText(task);
  refs.err.textContent = task.error_message || '';
  refs.err.hidden = !task.error_message;

  // 按钮显隐
  refs.pause.hidden = task.status !== 'active';
  refs.resume.hidden = task.status !== 'paused' && task.status !== 'waiting';
  refs.folder.hidden = !task.save_dir;
}

/* BT 任务元信息：做种中 / 做种人数 / 分享率 */
function btMetaText(task) {
  if (!task.is_bittorrent) {
    return task.connections ? `连接 ${task.connections}` : '';
  }
  // 元数据获取中：总大小未知
  if (!task.total_length && task.status === 'active') {
    return 'BT · 获取元数据中…';
  }
  const parts = [];
  const done = task.status === 'complete' || task.progress >= 100;
  if (done && task.status === 'active') {
    parts.push(task.upload_speed > 0 ? `做种中 ↑ ${fmtSpeed(task.upload_speed)}` : '做种中（等待 Peer）');
  }
  if (task.num_seeders != null && task.status === 'active') {
    parts.push(`做种 ${task.num_seeders}`);
  }
  if (done && task.total_length > 0) {
    parts.push(`分享率 ${(task.completed_length / task.total_length).toFixed(2)}`);
  }
  if (task.num_files != null && task.num_files > 1) {
    parts.push(`${task.num_files} 个文件`);
  }
  return parts.join(' · ');
}

function render() {
  const counts = { all: state.tasks.length, active: 0, waiting: 0, paused: 0, complete: 0, error: 0 };
  for (const t of state.tasks) {
    if (counts[t.status] !== undefined) counts[t.status]++;
  }
  document.querySelectorAll('[data-count]').forEach((el) => {
    el.textContent = counts[el.dataset.count] ?? 0;
  });

  const visible = state.tasks.filter((t) => {
    if (state.filter === 'all') return true;
    if (state.filter === 'active') return t.status === 'active';
    if (state.filter === 'waiting') return t.status === 'waiting';
    if (state.filter === 'paused') return t.status === 'paused';
    if (state.filter === 'complete') return t.status === 'complete';
    if (state.filter === 'error') return t.status === 'error';
    return true;
  });

  // 键控更新：复用已有卡片，删除消失的任务
  const alive = new Set(visible.map((t) => t.gid));
  for (const [gid, entry] of taskCards) {
    if (!alive.has(gid)) {
      entry.card.remove();
      taskCards.delete(gid);
    }
  }
  for (const task of visible) updateCard(task);

  $('#emptyState').hidden = visible.length > 0;
  $('#taskList').hidden = visible.length === 0;
}

function applyData(payload) {
  if (payload.config) state.config = payload.config;
  if (payload.app_version) {
    state.appVersion = payload.app_version;
    $('#appVersion').textContent = `版本 v${payload.app_version}`;
  }
  if (payload.tasks) {
    state.tasks = payload.tasks;
  }
  if (payload.aria2) {
    const info = payload.aria2;
    state.aria2Ok = !!info.ok;
    state.aria2Error = info.error;
    const starting = !!info.starting && !info.ok;
    const dot = $('#connDot');
    dot.className = `dot ${state.aria2Ok ? 'ok' : (starting ? 'warn' : '')}`;
    $('#connText').textContent = state.aria2Ok ? '已连接' : (starting ? '启动中' : '未连接');
    const banner = $('#offlineBanner');
    banner.hidden = state.aria2Ok;
    banner.classList.toggle('starting', starting);
    $('#offlineText').textContent = state.aria2Ok
      ? ''
      : (starting ? 'aria2c 启动中，请稍候…' : `aria2c 连接异常：${info.error || '未知错误'}`);
  }
  if (payload.stats) {
    $('#speedText').textContent = fmtSpeed(payload.stats.download_speed || 0);
  }
  if (payload.tasks) render();
}

/* 后端推送入口 */
window.__push = (payload) => {
  try { applyData(payload); } catch (e) { console.error('处理推送失败', e); }
};

/* ---------- 通知 ---------- */

function toast(message, type = 'ok') {
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.textContent = message;
  $('#toasts').appendChild(el);
  setTimeout(() => {
    el.style.opacity = '0';
    el.style.transition = 'opacity 0.25s';
    setTimeout(() => el.remove(), 250);
  }, type === 'error' ? 5000 : 2600);
}

/* ---------- 弹窗 ---------- */

function openModal(id) { document.getElementById(id).classList.remove('hidden'); }
function closeModal(id) { document.getElementById(id).classList.add('hidden'); }

document.querySelectorAll('[data-close]').forEach((btn) => {
  btn.addEventListener('click', () => closeModal(btn.dataset.close));
});
document.querySelectorAll('.modal-mask').forEach((mask) => {
  mask.addEventListener('click', (e) => { if (e.target === mask) mask.classList.add('hidden'); });
});

/* ---------- 新建任务 ---------- */

function openNewTask() {
  setTorrentChip(null); // 清除上次的种子文件选择
  $('#taskUrls').value = '';
  $('#taskSaveDir').value = state.config?.default_download_dir || '';
  $('#taskConnections').value = state.config?.default_connections ?? 16;
  $('#taskSplits').value = state.config?.default_splits ?? 16;
  $('#taskMaxSpeed').value = '';
  $('#taskFilename').value = '';
  openModal('newTaskModal');
  $('#taskUrls').focus();
}

async function chooseTorrent() {
  try {
    const path = await callApi('select_torrent_file');
    setTorrentChip(path || null);
  } catch (e) {
    toast(cleanError(e), 'error');
  }
}

function setTorrentChip(path) {
  state.torrentFile = path;
  const chip = $('#torrentChip');
  if (path) {
    const name = path.split(/[\\/]/).pop();
    chip.textContent = `✕ ${name}`;
    chip.title = `${path}\n（点击取消选择）`;
    chip.hidden = false;
    // 种子任务不需要连接数/分片数等 HTTP 专属项
    $('#taskUrls').placeholder = '已选择种子文件，链接输入框将被忽略';
  } else {
    chip.hidden = true;
    chip.textContent = '';
    $('#taskUrls').placeholder =
      '每行一个链接，每行将创建为独立任务\nhttps://example.com/file.zip\nmagnet:?xt=urn:btih:...（支持磁力/BT）';
  }
}

async function submitTask() {
  // 种子文件优先：选择了 .torrent 则忽略链接输入
  if (state.torrentFile) {
    try {
      await callWithToast('create_torrent_task', {
        path: state.torrentFile,
        save_dir: $('#taskSaveDir').value || null,
      });
      closeModal('newTaskModal');
    } catch (_) { /* 错误已提示 */ }
    return;
  }

  const urlsText = $('#taskUrls').value.trim();
  const urls = urlsText.split('\n').map(u => u.trim()).filter(Boolean);
  if (urls.length === 0) { toast('请至少输入一个下载链接，或选择种子文件', 'error'); return; }

  const payload = {
    urls,
    save_dir: $('#taskSaveDir').value || null,
    connections: clampInt($('#taskConnections').value, 1, 16, 16),
    splits: clampInt($('#taskSplits').value, 1, 16, 16),
  };
  const filename = $('#taskFilename').value.trim();
  if (filename && urls.length === 1) payload.filename = filename;
  const maxSpeed = $('#taskMaxSpeed').value.trim();
  if (maxSpeed) payload.max_speed = maxSpeed;

  try {
    await callWithToast('create_task', payload);
    closeModal('newTaskModal');
  } catch (_) { /* 错误已提示 */ }
}

function clampInt(v, min, max, dflt) {
  const n = parseInt(v, 10);
  if (!Number.isFinite(n)) return dflt;
  return Math.min(max, Math.max(1, n));
}

/* ---------- 设置 ---------- */

// 三种做种分享模式 → aria2 启动参数（--seed-ratio / --seed-time，任一先到即停）
const SEED_PRESETS = {
  none:     { ratio: 0.01, time: 1 },  // 下载完成后至多 1 分钟内停止上传
  standard: { ratio: 1.0,  time: 0 },  // 上传到下载量的 100% 后停止
  deep:     { ratio: 0,    time: 0 },  // 不限量永久做种，直到删除任务
};

function detectSeedPreset(ratio, time) {
  for (const [key, p] of Object.entries(SEED_PRESETS)) {
    if (Math.abs(p.ratio - ratio) < 1e-9 && p.time === time) return key;
  }
  return null; // 自定义
}

function setSeedPresetUI(preset) {
  document.querySelectorAll('#seedPresetGroup .preset-card').forEach((card) => {
    card.classList.toggle('active', card.dataset.preset === preset);
  });
  $('#seedAdv').classList.toggle('is-custom', preset === null);
}

function applySeedPreset(key) {
  const p = SEED_PRESETS[key];
  if (!p) return;
  $('#cfgSeedRatio').value = p.ratio;
  $('#cfgSeedTime').value = p.time;
  setSeedPresetUI(key);
}

function syncPresetFromInputs() {
  const ratio = clampFloat($('#cfgSeedRatio').value, 0, 100, 1);
  const time = parseInt($('#cfgSeedTime').value, 10) || 0;
  setSeedPresetUI(detectSeedPreset(ratio, time));
}

function openSettings() {
  const c = state.config || {};
  $('#cfgDownloadDir').value = c.default_download_dir || '';
  $('#cfgConnections').value = c.default_connections ?? 16;
  $('#cfgSplits').value = c.default_splits ?? 16;
  $('#cfgConcurrent').value = c.max_concurrent_downloads ?? 5;
  $('#cfgLimit').value = c.max_overall_download_limit || '';
  // BT / 做种：按比率/时长反推分享模式
  const ratio = c.bt_seed_ratio ?? 1;
  const time = c.bt_seed_time ?? 0;
  $('#cfgSeedRatio').value = ratio;
  $('#cfgSeedTime').value = time;
  setSeedPresetUI(detectSeedPreset(ratio, time));
  $('#cfgBtPort').value = c.bt_listen_port || '6881-6999';
  $('#cfgDht').checked = c.bt_enable_dht !== false;
  $('#cfgTrackers').value = c.bt_trackers || '';
  openModal('settingsModal');
}

async function browseConfigDir() {
  try {
    const dir = await callApi('select_directory');
    if (dir) $('#cfgDownloadDir').value = dir;
  } catch (e) {
    toast(cleanError(e), 'error');
  }
}

async function saveConfig() {
  try {
    await callWithToast('save_config', {
      default_download_dir: $('#cfgDownloadDir').value,
      default_connections: clampInt($('#cfgConnections').value, 1, 16, 16),
      default_splits: clampInt($('#cfgSplits').value, 1, 16, 16),
      max_concurrent_downloads: clampInt($('#cfgConcurrent').value, 1, 20, 5),
      max_overall_download_limit: $('#cfgLimit').value.trim() || null,
      bt_seed_ratio: clampFloat($('#cfgSeedRatio').value, 0, 100, 1),
      bt_seed_time: clampInt($('#cfgSeedTime').value, 0, 10080, 0),
      bt_listen_port: $('#cfgBtPort').value.trim() || '6881-6999',
      bt_enable_dht: $('#cfgDht').checked,
      bt_trackers: $('#cfgTrackers').value.trim() || null,
    });
    closeModal('settingsModal');
  } catch (_) { /* 错误已提示 */ }
}

function clampFloat(v, min, max, dflt) {
  const n = parseFloat(v);
  if (!Number.isFinite(n)) return dflt;
  return Math.min(max, Math.max(min, n));
}

/* ---------- 事件绑定 ---------- */

function bindEvents() {
  $('#btnNewTask').addEventListener('click', openNewTask);
  $('#btnEmptyNew').addEventListener('click', openNewTask);
  $('#btnSubmitTask').addEventListener('click', submitTask);
  $('#btnChooseTorrent').addEventListener('click', chooseTorrent);
  $('#torrentChip').addEventListener('click', () => setTorrentChip(null)); // 点击取消选择
  $('#btnChooseDir').addEventListener('click', async () => {
    try {
      const dir = await callApi('select_directory');
      if (dir) $('#taskSaveDir').value = dir;
    } catch (e) { toast(cleanError(e), 'error'); }
  });

  $('#btnSettings').addEventListener('click', openSettings);
  $('#btnCfgBrowse').addEventListener('click', browseConfigDir);
  $('#btnSaveConfig').addEventListener('click', saveConfig);

  // 做种分享模式：点击卡片套用预设；手动改高级输入后自动变为"自定义"
  $('#seedPresetGroup').addEventListener('click', (e) => {
    const card = e.target.closest('.preset-card');
    if (card) applySeedPreset(card.dataset.preset);
  });
  $('#seedPresetGroup').addEventListener('keydown', (e) => {
    if (e.key !== 'Enter' && e.key !== ' ') return;
    const card = e.target.closest('.preset-card');
    if (card) { e.preventDefault(); applySeedPreset(card.dataset.preset); }
  });
  $('#cfgSeedRatio').addEventListener('input', syncPresetFromInputs);
  $('#cfgSeedTime').addEventListener('input', syncPresetFromInputs);

  $('#btnPauseAll').addEventListener('click', () => callWithToast('pause_all'));
  $('#btnResumeAll').addEventListener('click', () => callWithToast('resume_all'));

  $('#filters').addEventListener('click', (e) => {
    const btn = e.target.closest('.filter');
    if (!btn) return;
    document.querySelectorAll('.filter').forEach((f) => f.classList.remove('active'));
    btn.classList.add('active');
    state.filter = btn.dataset.filter;
    render();
  });

  // 连接数/分片数步进器
  document.querySelectorAll('[data-step]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const input = document.getElementById(
        btn.dataset.step === 'connections' ? 'taskConnections' : 'taskSplits'
      );
      const current = parseInt(input.value, 10) || 16;
      const next = current + parseInt(btn.dataset.delta, 10);
      input.value = Math.min(16, Math.max(1, next));
    });
  });
}

/* ---------- 主题（跟随系统） ---------- */

function applyTheme() {
  const dark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  document.documentElement.dataset.theme = dark ? 'dark' : 'light';
}

/* ---------- 启动 ---------- */

async function waitForPywebview(timeoutMs = 8000) {
  const start = Date.now();
  while (!(window.pywebview && window.pywebview.api)) {
    if (Date.now() - start > 8000) throw new Error('后端初始化超时');
    await new Promise((r) => setTimeout(r, 100));
  }
}

async function bootstrap() {
  applyTheme();
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', applyTheme);
  bindEvents();

  try {
    await waitForPywebview();
    const payload = await window.pywebview.api.init();
    applyData(payload);
  } catch (e) {
    toast(cleanError(e), 'error');
  }
}

document.addEventListener('DOMContentLoaded', bootstrap);

/* ---------- SVG 图标 ---------- */
function pauseSvg() {
  return '<svg viewBox="0 0 24 24" width="15" height="15" fill="currentColor"><rect x="6" y="4" width="4" height="16" rx="1"/><rect x="14" y="4" width="4" height="16" rx="1"/></svg>';
}
function playSvg() {
  return '<svg viewBox="0 0 24 24" width="15" height="15" fill="currentColor"><polygon points="7 4 20 12 7 20 7 4"/></svg>';
}
function folderSvg() {
  return '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7z"/></svg>';
}
function trashSvg() {
  return '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2m3 0v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6h14z"/></svg>';
}

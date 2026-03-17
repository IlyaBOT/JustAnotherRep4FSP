const messagesNode = document.getElementById('messages');
const chatForm = document.getElementById('chatForm');
const chatInput = document.getElementById('chatInput');
const resetChatBtn = document.getElementById('resetChatBtn');
const template = document.getElementById('messageTemplate');
const documentUploadInput = document.getElementById('documentUploadInput');
const uploadDocumentsBtn = document.getElementById('uploadDocumentsBtn');

const STORAGE_KEY = 'svoy-chat-session-id';
let sessionId = localStorage.getItem(STORAGE_KEY);
let localUploadedFiles = [];

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function renderMessage(message) {
  const fragment = template.content.cloneNode(true);
  const row = fragment.querySelector('.message-row');
  const bubble = fragment.querySelector('.message-bubble');
  const buttonRow = fragment.querySelector('.button-row');

  row.classList.add(message.role);
  bubble.innerHTML = escapeHtml(message.text).replace(/\n/g, '<br>');

  if (message.buttons?.length) {
    message.buttons.forEach((button) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'quick-btn';
      btn.textContent = button.label;
      btn.addEventListener('click', () => sendMessage(button.value, true, button.label));
      buttonRow.appendChild(btn);
    });
  } else {
    buttonRow.remove();
  }

  messagesNode.appendChild(fragment);
  messagesNode.scrollTop = messagesNode.scrollHeight;
}

function renderMessages(messages) {
  messagesNode.innerHTML = '';
  messages.forEach(renderMessage);
  syncUploadButton(messages);
}

function formatFileSize(size) {
  if (!Number.isFinite(size) || size <= 0) return 'размер не указан';

  const units = ['Б', 'КБ', 'МБ', 'ГБ'];
  let value = size;
  let unitIndex = 0;

  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }

  const rounded = value >= 10 || unitIndex === 0 ? value.toFixed(0) : value.toFixed(1);
  return `${rounded} ${units[unitIndex]}`;
}

function resetUploadState() {
  localUploadedFiles = [];
  documentUploadInput.value = '';
  uploadDocumentsBtn.textContent = 'Загрузить файлы';
  uploadDocumentsBtn.title = '';
}

function updateUploadButtonState() {
  if (!localUploadedFiles.length) {
    uploadDocumentsBtn.textContent = 'Загрузить файлы';
    uploadDocumentsBtn.title = '';
    return;
  }

  const totalSize = localUploadedFiles.reduce((sum, file) => sum + file.size, 0);
  uploadDocumentsBtn.textContent = `Файлы: ${localUploadedFiles.length}`;
  uploadDocumentsBtn.title = `${localUploadedFiles.map((file) => file.name).join(', ')} • ${formatFileSize(totalSize)}`;
}

function syncUploadButton(messages) {
  const lastAssistantMessage = [...messages].reverse().find((message) => message.role === 'assistant');
  const showUploadButton = Boolean(lastAssistantMessage?.meta?.show_upload_button);

  uploadDocumentsBtn.hidden = !showUploadButton;
  if (!showUploadButton) {
    resetUploadState();
    return;
  }

  updateUploadButtonState();
}

function addLocalFiles(fileList) {
  const files = Array.from(fileList || []).map((file) => ({ name: file.name, size: file.size }));
  if (!files.length) return;

  const seen = new Set(localUploadedFiles.map((file) => `${file.name}:${file.size}`));
  const uniqueFiles = files.filter((file) => {
    const key = `${file.name}:${file.size}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });

  if (!uniqueFiles.length) {
    return;
  }

  localUploadedFiles = [...localUploadedFiles, ...uniqueFiles];
  updateUploadButtonState();
}

async function startSession() {
  const res = await fetch('/api/chat/start', { method: 'POST' });
  if (!res.ok) throw new Error('Не удалось стартовать чат');
  const data = await res.json();
  sessionId = data.session_id;
  localStorage.setItem(STORAGE_KEY, sessionId);
  resetUploadState();
  renderMessages(data.messages);
}

async function loadHistory() {
  if (!sessionId) {
    await startSession();
    return;
  }

  const res = await fetch(`/api/chat/history/${sessionId}`);
  if (!res.ok) {
    localStorage.removeItem(STORAGE_KEY);
    sessionId = null;
    await startSession();
    return;
  }

  const data = await res.json();
  renderMessages(data.messages);
}

async function sendMessage(text, echoUser = true, displayText = null) {
  if (!text?.trim()) return;
  const visibleText = displayText?.trim() || text;

  if (echoUser) {
    renderMessage({ role: 'user', text: visibleText, buttons: null });
  }

  const res = await fetch('/api/chat/message', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, text, display_text: displayText }),
  });

  if (!res.ok) {
    renderMessage({ role: 'assistant', text: 'Ошибка соединения. Попробуйте ещё раз.', buttons: null });
    return;
  }

  const data = await res.json();
  renderMessages(data.messages);
}

chatForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const text = chatInput.value.trim();
  chatInput.value = '';
  await sendMessage(text, true);
});

resetChatBtn.addEventListener('click', async () => {
  localStorage.removeItem(STORAGE_KEY);
  sessionId = null;
  await startSession();
});

uploadDocumentsBtn.addEventListener('click', () => {
  documentUploadInput.click();
});

documentUploadInput.addEventListener('change', (event) => {
  addLocalFiles(event.target.files);
  event.target.value = '';
});

resetUploadState();
loadHistory();

document.addEventListener('DOMContentLoaded', async () => {
  await checkNativeStatus();
  await loadLogs();
  
  document.getElementById('refresh').addEventListener('click', () => {
    checkNativeStatus();
    loadLogs();
  });
  document.getElementById('clear').addEventListener('click', clearLogs);
});

async function checkNativeStatus() {
  const statusEl = document.getElementById('native-status');
  
  try {
    const port = chrome.runtime.connectNative('com.applogs.chrome');
    port.onMessage.addListener((msg) => {
      if (msg.pong) {
        statusEl.textContent = 'Connected';
        statusEl.style.color = '#008800';
      }
      port.disconnect();
    });
    port.onDisconnect.addListener(() => {
      if (statusEl.textContent === 'Checking...') {
        statusEl.textContent = 'Not connected';
        statusEl.style.color = '#cc0000';
      }
    });
    port.postMessage({ action: 'ping' });
    statusEl.textContent = 'Checking...';
    statusEl.style.color = '#666';
  } catch (e) {
    statusEl.textContent = 'Not connected';
    statusEl.style.color = '#cc0000';
  }
}

async function loadLogs() {
  const { logs = [] } = await chrome.storage.local.get('logs');
  document.getElementById('count').textContent = logs.length;
}

async function clearLogs() {
  if (confirm('Clear local storage logs? (Native file logs are not affected)')) {
    await chrome.storage.local.set({ logs: [] });
    await loadLogs();
  }
}
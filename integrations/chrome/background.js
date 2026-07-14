const NATIVE_HOST = 'com.applogs.chrome';

let nativePort = null;
let nativeConnected = false;
let logQueue = [];
let lastUrl = null;
let lastTitle = null;
let startTime = null;

function connectNative() {
  if (nativePort) {
    return;
  }
  
  try {
    nativePort = chrome.runtime.connectNative(NATIVE_HOST);
    nativeConnected = true;
    
    nativePort.onDisconnect.addListener(() => {
      nativeConnected = false;
      nativePort = null;
      console.log('[AppLogs] Native host disconnected, will retry on next event');
    });
    
    nativePort.onMessage.addListener((msg) => {
      if (msg.status === 'error') {
        console.error('[AppLogs] Native host error:', msg.message);
      }
    });
    
    // Flush any queued logs
    while (logQueue.length > 0) {
      const entry = logQueue.shift();
      sendToNative(entry);
    }
  } catch (e) {
    console.error('[AppLogs] Failed to connect to native host:', e);
    nativeConnected = false;
  }
}

function sendToNative(entry) {
  if (!nativePort) {
    connectNative();
  }
  
  if (nativePort) {
    try {
      nativePort.postMessage({ action: 'log', entry: entry });
    } catch (e) {
      console.error('[AppLogs] Failed to send to native host:', e);
      logQueue.push(entry);
      nativePort = null;
      nativeConnected = false;
    }
  } else {
    logQueue.push(entry);
  }
}

function logAction(action) {
  const timestamp = new Date().toISOString();
  const logEntry = {
    timestamp,
    ...action
  };
  
  sendToNative(logEntry);
  console.log('[AppLogs]', logEntry);
}

chrome.tabs.onActivated.addListener(async (activeInfo) => {
  const tab = await chrome.tabs.get(activeInfo.tabId);
  handleTabFocus(tab);
});

chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === 'complete' && tab.active) {
    handleNavigation(tab);
  }
});

async function handleTabFocus(tab) {
  if (startTime && lastUrl) {
    logAction({
      type: 'tab_blur',
      url: lastUrl,
      title: lastTitle,
      duration_ms: Date.now() - startTime
    });
  }
  
  lastUrl = tab.url;
  lastTitle = tab.title;
  startTime = Date.now();
  
  logAction({
    type: 'tab_focus',
    url: tab.url,
    title: tab.title,
    windowId: tab.windowId
  });
}

async function handleNavigation(tab) {
  logAction({
    type: 'navigation',
    url: tab.url,
    title: tab.title,
    favIconUrl: tab.favIconUrl
  });
}

chrome.webNavigation.onCompleted.addListener((details) => {
  if (details.frameId === 0) {
    logAction({
      type: 'page_load',
      url: details.url,
      tabId: details.tabId,
      processId: details.processId
    });
  }
});

// Try to connect on startup
connectNative();
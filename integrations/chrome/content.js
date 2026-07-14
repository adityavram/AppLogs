let lastInputTime = null;
let inputBuffer = '';
const INPUT_THRESHOLD_MS = 500;

document.addEventListener('submit', async (e) => {
  const form = e.target;
  const formData = new FormData(form);
  const action = form.getAttribute('action');
  const method = form.getAttribute('method') || 'GET';
  
  const fields = {};
  for (let [key, value] of formData.entries()) {
    fields[key] = typeof value === 'string' ? value.slice(0, 200) : '[File or binary]';
  }
  
  chrome.runtime.sendMessage({
    type: 'form_submit',
    action: action || window.location.href,
    method: method.toUpperCase(),
    fields: Object.keys(fields),
    page_url: window.location.href,
    page_title: document.title
  });
});

document.addEventListener('input', (e) => {
  const now = Date.now();
  
  if (!lastInputTime || (now - lastInputTime) > INPUT_THRESHOLD_MS) {
    if (inputBuffer) {
      chrome.runtime.sendMessage({
        type: 'input_chunk',
        content: inputBuffer,
        element_type: e.target.type,
        element_name: e.target.name || e.target.id || 'unknown',
        page_url: window.location.href
      });
    }
    inputBuffer = '';
  }
  
  lastInputTime = now;
  
  const target = e.target;
  if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') {
    if (target.type !== 'password') {
      inputBuffer = target.value.slice(0, 500);
    }
  }
});

document.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA')) {
    chrome.runtime.sendMessage({
      type: 'submit_via_enter',
      element_type: e.target.type,
      element_name: e.target.name || e.target.id || 'unknown',
      page_url: window.location.href
    });
  }
});

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.type === 'ping') {
    sendResponse({ status: 'ok' });
  }
});
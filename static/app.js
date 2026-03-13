(function() {
  'use strict';
  function $(id) { return document.getElementById(id); }
  var isProcessing = false;
  var eventSource = null;
  var mediaRecorder = null;
  var voiceChunks = [];

  async function tryLogin() {
    var btn = $('login-btn');
    var pw = $('pw-input');
    var err = $('login-error');
    if (!btn || !pw || !err) return;
    err.textContent = '';
    if (!pw.value || !pw.value.trim()) {
      err.textContent = 'ENTER PASSWORD';
      return;
    }
    btn.disabled = true;
    btn.textContent = '...';
    try {
      var body = JSON.stringify({ password: pw.value.trim() });
      var r = await fetch('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: body
      });
      if (r.ok) {
        showApp();
      } else {
        err.textContent = 'ACCESS DENIED';
        pw.value = '';
      }
    } catch (e) {
      err.textContent = 'CONNECTION FAILED';
    }
    btn.disabled = false;
    btn.textContent = 'AUTHENTICATE';
  }

  function showApp() {
    var screen = $('login-screen');
    var app = $('app');
    if (screen) screen.style.display = 'none';
    if (app) app.classList.add('visible');
    loadMemory();
    loadLogs();
    loadToolHistory();
    connectSSE();
  }

  async function checkAuth() {
    try {
      var r = await fetch('/api/me');
      if (r.ok) showApp();
    } catch (e) {}
  }

  function loadMemory() {
    fetch('/api/memory').then(function(r) {
      if (r.ok) return r.json();
    }).then(function(d) {
      if (d) {
        var sp = $('scratchpad-editor');
        var id = $('identity-editor');
        if (sp) sp.value = d.scratchpad || '';
        if (id) id.value = d.identity || '';
      }
    }).catch(function() {});
  }

  function loadLogs() {
    fetch('/api/logs').then(function(r) {
      if (r.ok) return r.json();
    }).then(function(d) {
      if (d && d.logs) d.logs.forEach(addLogEntry);
    }).catch(function() {});
  }

  function loadToolHistory() {
    fetch('/api/tools/history').then(function(r) {
      if (r.ok) return r.json();
    }).then(function(d) {
      if (d && d.events) d.events.forEach(addToolEntry);
    }).catch(function() {});
  }

  function addLogEntry(entry) {
    var list = $('log-list');
    if (!list) return;
    var empty = list.querySelector('.empty-state');
    if (empty) empty.remove();
    var div = document.createElement('div');
    div.className = 'log-entry';
    div.innerHTML = '<span class="log-ts">' + (entry.ts || '') + '</span><span class="log-level ' + (entry.level || '') + '">' + (entry.level || '') + '</span><span class="log-msg">' + escapeHtml(entry.msg || '') + '</span>';
    list.appendChild(div);
    list.scrollTop = list.scrollHeight;
  }

  function addToolEntry(entry) {
    var list = $('tool-list');
    if (!list) return;
    var empty = list.querySelector('.empty-state');
    if (empty) empty.remove();
    var div = document.createElement('div');
    div.className = 'tool-entry';
    var status = entry.status || 'ok';
    var result = entry.result ? '<div class="tool-result">' + escapeHtml(entry.result) + '</div>' : '';
    div.innerHTML = '<div class="tool-header"><span class="tool-name">' + escapeHtml(entry.tool || '') + '</span><span class="tool-ts">' + (entry.ts || '') + '</span></div><span class="tool-status ' + status + '">' + status.toUpperCase() + '</span>' + result;
    list.insertBefore(div, list.firstChild);
  }

  function connectSSE() {
    eventSource = new EventSource('/api/events');
    eventSource.onopen = function() {
      var dot = $('status-dot');
      var label = $('status-label');
      if (dot) dot.classList.add('online');
      if (label) label.textContent = 'online';
    };
    eventSource.onerror = function() {
      var dot = $('status-dot');
      var label = $('status-label');
      if (dot) dot.classList.remove('online');
      if (label) label.textContent = 'reconnecting';
      setTimeout(connectSSE, 3000);
    };
    eventSource.onmessage = function(e) {
      try {
        var ev = JSON.parse(e.data);
        if (ev.type === 'log') addLogEntry(ev.data);
        if (ev.type === 'tool') addToolEntry(ev.data);
      } catch (err) {}
    };
  }

  function escapeHtml(str) {
    var s = String(str);
    return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function saveMemory(type) {
    var content = type === 'scratchpad' ? $('scratchpad-editor').value : $('identity-editor').value;
    fetch('/api/memory/' + type, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content: content })
    }).catch(function() {});
  }

  async function sendMessage() {
    if (isProcessing) return;
    var text = $('msg-input');
    if (!text || !text.value.trim()) return;
    var msg = text.value.trim();
    text.value = '';
    text.style.height = 'auto';
    isProcessing = true;
    var sendBtn = $('send-btn');
    if (sendBtn) sendBtn.disabled = true;
    appendMessage('user', msg);
    var thinking = appendThinking();
    try {
      var r = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: msg })
      });
      thinking.remove();
      if (r.ok) {
        var d = await r.json();
        appendMessage('agent', d.reply || '');
        loadMemory();
      } else {
        var errText = 'Error: ' + r.status;
        try {
          var errBody = await r.json();
          if (errBody && errBody.detail) errText = errBody.detail;
        } catch (_) {}
        appendMessage('agent', errText);
      }
    } catch (e) {
      thinking.remove();
      appendMessage('agent', 'Connection error');
    }
    isProcessing = false;
    if (sendBtn) sendBtn.disabled = false;
    if (text) text.focus();
  }

  function appendMessage(role, text) {
    var msgs = $('messages');
    if (!msgs) return null;
    var div = document.createElement('div');
    div.className = 'msg ' + role;
    var label = role === 'user' ? 'you' : 'VOR';
    div.innerHTML = '<div class="msg-label">' + label + '</div><div class="msg-bubble">' + escapeHtml(text) + '</div>';
    msgs.appendChild(div);
    msgs.scrollTop = msgs.scrollHeight;
    return div;
  }

  async function toggleVoice() {
    var micBtn = $('mic-btn');
    if (!micBtn) return;
    if (mediaRecorder && mediaRecorder.state === 'recording') {
      mediaRecorder.stop();
      micBtn.classList.remove('recording');
      return;
    }
    try {
      var stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorder = new MediaRecorder(stream);
      voiceChunks = [];
      mediaRecorder.ondataavailable = function(e) { if (e.data.size) voiceChunks.push(e.data); };
      mediaRecorder.onstop = function() {
        stream.getTracks().forEach(function(t) { t.stop(); });
        if (voiceChunks.length === 0) return;
        var blob = new Blob(voiceChunks, { type: 'audio/ogg' });
        var fd = new FormData();
        fd.append('audio', blob, 'voice.ogg');
        fetch('/api/voice/transcribe', { method: 'POST', body: fd, credentials: 'include' })
          .then(function(r) { return r.json(); })
          .then(function(d) {
            var txt = (d.text || '').trim();
            if (txt && !txt.startsWith('ERROR')) {
              var inp = $('msg-input');
              if (inp) inp.value = txt;
              sendMessage();
            }
          })
          .catch(function() {});
      };
      mediaRecorder.start();
      micBtn.classList.add('recording');
    } catch (e) {
      console.error('Mic error:', e);
    }
  }

  function appendThinking() {
    var msgs = $('messages');
    if (!msgs) return null;
    var div = document.createElement('div');
    div.className = 'msg agent msg-thinking';
    div.innerHTML = '<div class="msg-label">VOR</div><div class="msg-bubble thinking-dots"><span>.</span><span>.</span><span>.</span></div>';
    msgs.appendChild(div);
    msgs.scrollTop = msgs.scrollHeight;
    return div;
  }

  document.addEventListener('DOMContentLoaded', function() {
    var loginBtn = $('login-btn');
    var pwInput = $('pw-input');
    var logoutBtn = $('logout-btn');
    var sendBtn = $('send-btn');
    var msgInput = $('msg-input');
    var micBtn = $('mic-btn');

    if (loginBtn) loginBtn.onclick = tryLogin;
    if (micBtn) micBtn.onclick = toggleVoice;
    if (pwInput) pwInput.onkeydown = function(e) { if (e.key === 'Enter') tryLogin(); };
    if (logoutBtn) logoutBtn.onclick = function() { fetch('/api/logout', { method: 'POST' }).then(function() { location.reload(); }); };
    if (sendBtn) sendBtn.onclick = sendMessage;
    if (msgInput) {
      msgInput.onkeydown = function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          sendMessage();
        }
      };
      msgInput.oninput = function() {
        this.style.height = 'auto';
        this.style.height = Math.min(this.scrollHeight, 120) + 'px';
      };
    }

    document.querySelectorAll('.tab-btn').forEach(function(btn) {
      btn.onclick = function() {
        document.querySelectorAll('.tab-btn').forEach(function(b) { b.classList.remove('active'); });
        document.querySelectorAll('.tab-pane').forEach(function(p) { p.classList.remove('active'); });
        btn.classList.add('active');
        var tabId = 'tab-' + (btn.dataset.tab || '');
        var tab = document.getElementById(tabId);
        if (tab) tab.classList.add('active');
      };
    });

    var spSave = document.querySelector('[data-save="scratchpad"]');
    var idSave = document.querySelector('[data-save="identity"]');
    if (spSave) spSave.onclick = function() { saveMemory('scratchpad'); };
    if (idSave) idSave.onclick = function() { saveMemory('identity'); };

    checkAuth();
  });
})();

(function () {
  if (!window.cnAgentOS) window.cnAgentOS = {};
  if (window.cnAgentOS.voice) return;

  var MOD = {};
  window.cnAgentOS.voice = MOD;

  var STORAGE_KEY = 'voice_enabled';
  var DEBOUNCE_MS = 500;
  var _lastSpeak = 0;
  var _synth = null;

  try {
    _synth = window.speechSynthesis;
  } catch (e) {
    _synth = null;
  }

  MOD.isSupported = function () {
    return !!_synth;
  };

  MOD.isEnabled = function () {
    return localStorage.getItem(STORAGE_KEY) === '1';
  };

  MOD.toggle = function (enabled) {
    var val = typeof enabled === 'boolean' ? enabled : !MOD.isEnabled();
    localStorage.setItem(STORAGE_KEY, val ? '1' : '0');
    MOD._updateButton();
    return val;
  };

  MOD.speak = function (text) {
    if (!MOD.isSupported()) return;
    if (!MOD.isEnabled()) return;
    if (!text) return;
    var now = Date.now();
    if (now - _lastSpeak < DEBOUNCE_MS) return;
    _lastSpeak = now;

    try {
      _synth.cancel();
    } catch (e) {}

    var utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'zh-CN';
    utterance.rate = 1.0;
    utterance.pitch = 1.0;
    utterance.volume = 0.9;
    _synth.speak(utterance);
  };

  MOD._updateButton = function () {
    var btn = document.getElementById('voice-toggle-btn');
    if (!btn) return;
    var icon = btn.querySelector('i');
    if (!icon) return;
    if (MOD.isEnabled()) {
      icon.className = 'fas fa-volume-up';
      btn.title = '语音播报：已开启';
      btn.style.color = '#10b981';
    } else {
      icon.className = 'fas fa-volume-mute';
      btn.title = '语音播报：已关闭';
      btn.style.color = '#6b7280';
    }
  };

  MOD._createButton = function () {
    if (document.getElementById('voice-toggle-btn')) return;
    var btn = document.createElement('button');
    btn.id = 'voice-toggle-btn';
    btn.className = 'btn btn-sm';
    btn.style.cssText = 'position:fixed;right:20px;bottom:220px;z-index:9990;width:40px;height:40px;border-radius:50%;background:rgba(255,255,255,0.15);border:1px solid rgba(255,255,255,0.25);backdrop-filter:blur(8px);cursor:pointer;display:flex;align-items:center;justify-content:center;transition:all 0.2s;';
    btn.innerHTML = '<i class="fas fa-volume-up"></i>';
    btn.onclick = function () { MOD.toggle(); };
    document.body.appendChild(btn);
    MOD._updateButton();
  };

  MOD.init = function () {
    if (!MOD.isSupported()) return;
    MOD._createButton();

    window.addEventListener('cnagentos:new-message', function (e) {
      if (window.location.pathname.indexOf('/portal/chat') !== -1) return;
      MOD.speak('您有一条新消息');
    });

    window.addEventListener('cnagentos:task-complete', function (e) {
      var msg = (e.detail && e.detail.message) ? e.detail.message : '任务已完成';
      MOD.speak(msg);
    });

    var welcomeFlag = sessionStorage.getItem('voice_welcome');
    if (welcomeFlag) {
      sessionStorage.removeItem('voice_welcome');
      var usernameEl = document.querySelector('.badge-soft .fa-user');
      var username = '';
      if (usernameEl && usernameEl.parentElement) {
        var text = usernameEl.parentElement.textContent || '';
        var parts = text.split('·');
        username = (parts[0] || '').trim();
      }
      setTimeout(function () {
        MOD.speak(username ? '欢迎回来，' + username : '欢迎回来');
      }, 800);
    }
  };

  document.addEventListener('DOMContentLoaded', function () {
    if (document.body && document.body.classList.contains('portal-shell')) {
      MOD.init();
    }
    if (document.body && document.body.classList.contains('admin-shell')) {
      MOD.init();
    }
  });
})();

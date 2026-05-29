(function () {
  if (!window.cnAgentOS) window.cnAgentOS = {};
  if (window.cnAgentOS.voice) return;

  var MOD = {};
  window.cnAgentOS.voice = MOD;

  var STORAGE_KEY = 'voice_enabled';
  var DEBOUNCE_MS = 500;
  var _lastSpeak = 0;
  var _currentAudio = null;

  MOD.isEnabled = function () {
    return localStorage.getItem(STORAGE_KEY) === '1';
  };

  MOD.toggle = function (enabled) {
    var val = typeof enabled === 'boolean' ? enabled : !MOD.isEnabled();
    localStorage.setItem(STORAGE_KEY, val ? '1' : '0');
    MOD._updateButton();
    return val;
  };

  MOD._stopCurrentAudio = function () {
    if (_currentAudio) {
      try { _currentAudio.pause(); } catch (e) {}
      try { URL.revokeObjectURL(_currentAudio.src); } catch (e) {}
      _currentAudio = null;
    }
  };

  MOD.speak = function (text) {
    if (!MOD.isEnabled()) return;
    if (!text) return;
    var now = Date.now();
    if (now - _lastSpeak < DEBOUNCE_MS) return;
    _lastSpeak = now;

    MOD._stopCurrentAudio();

    var formData = new FormData();
    formData.append('text', text);

    fetch('/api/voice/tts', {
      method: 'POST',
      body: formData
    })
      .then(function (resp) {
        if (!resp.ok) throw new Error('TTS failed: ' + resp.status);
        return resp.blob();
      })
      .then(function (blob) {
        var url = URL.createObjectURL(blob);
        var audio = new Audio(url);
        _currentAudio = audio;
        audio.onended = function () {
          URL.revokeObjectURL(url);
          _currentAudio = null;
        };
        audio.onerror = function () {
          URL.revokeObjectURL(url);
          _currentAudio = null;
        };
        audio.play();
      })
      .catch(function (err) {
        console.warn('[voice] TTS 请求失败:', err.message);
      });
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
      btn.style.borderColor = 'rgba(16, 185, 129, 0.55)';
      btn.style.background = 'rgba(16, 185, 129, 0.12)';
    } else {
      icon.className = 'fas fa-volume-mute';
      btn.title = '语音播报：已关闭';
      btn.style.color = '#94a3b8';
      btn.style.borderColor = 'rgba(148, 163, 184, 0.45)';
      btn.style.background = 'rgba(255, 255, 255, 0.12)';
    }
  };

  MOD._createButton = function () {
    if (document.getElementById('voice-toggle-btn')) return;
    var btn = document.createElement('button');
    btn.id = 'voice-toggle-btn';
    btn.className = 'btn btn-sm';
    btn.style.cssText = 'position:fixed;right:20px;bottom:220px;z-index:9990;width:40px;height:40px;border-radius:50%;background:rgba(255,255,255,0.12);border:1.5px solid rgba(148,163,184,0.45);backdrop-filter:blur(8px);cursor:pointer;display:flex;align-items:center;justify-content:center;transition:all 0.25s;color:#94a3b8;font-size:16px;';
    btn.innerHTML = '<i class="fas fa-volume-up"></i>';
    btn.onclick = function () { MOD.toggle(); };
    document.body.appendChild(btn);
    MOD._updateButton();
  };

  MOD.init = function () {
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

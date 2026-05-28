(function () {
  if (!window.cnAgentOS) window.cnAgentOS = {};
  if (window.cnAgentOS.gesture) return;

  var MOD = {};
  window.cnAgentOS.gesture = MOD;

  var STORAGE_KEY = 'gesture_enabled';
  var MODEL_BASE = '/static/models/mediapipe/';
  var COOLDOWN_MS = 1500;
  var PROCESS_INTERVAL_MS = 33;
  var MODEL_INIT_TIMEOUT_MS = 10000;
  var RESULT_TIMEOUT_MS = 1800;
  var STALE_RESULT_RESET_MS = 2500;
  var MIN_GESTURE_SCORE = 0.78;
  var TRIGGER_SCORE = 1.75;
  var SCORE_DECAY = 0.55;
  var MAX_RESTARTS = 1;
  var PREPROCESS_SIZE = 256;

  var _lastTrigger = 0;
  var _video = null;
  var _stream = null;
  var _animationId = null;
  var _handsInstance = null;
  var _modelReady = false;
  var _modelTimeout = null;
  var _frameInFlight = false;
  var _frameSentAt = 0;
  var _lastResultsAt = 0;
  var _lastLoopAt = 0;
  var _sendErrorCount = 0;
  var _restartCount = 0;
  var _candidateGesture = 'unknown';
  var _candidateScore = 0;
  var _candidateSeenAt = 0;
  var _processingCanvas = null;
  var _processingCtx = null;
  var _sampleCounter = 0;
  var _sceneLuma = 128;
  var _loadScriptPromise = null;

  function _checkCooldown() {
    return Date.now() - _lastTrigger < COOLDOWN_MS;
  }

  function _resetCooldown() {
    _lastTrigger = Date.now();
  }

  function _clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
  }

  function _distance(a, b) {
    var dx = a.x - b.x;
    var dy = a.y - b.y;
    var dz = (a.z || 0) - (b.z || 0);
    return Math.sqrt(dx * dx + dy * dy + dz * dz);
  }

  function _vector(a, b) {
    return {
      x: b.x - a.x,
      y: b.y - a.y,
      z: (b.z || 0) - (a.z || 0)
    };
  }

  function _dot(a, b) {
    return a.x * b.x + a.y * b.y + (a.z || 0) * (b.z || 0);
  }

  function _length(v) {
    return Math.sqrt(_dot(v, v));
  }

  function _normalize(v) {
    var len = _length(v) || 1;
    return {
      x: v.x / len,
      y: v.y / len,
      z: (v.z || 0) / len
    };
  }

  function _angle(a, b, c) {
    var ab = _vector(b, a);
    var cb = _vector(b, c);
    var denom = (_length(ab) * _length(cb)) || 1;
    var cosine = _clamp(_dot(ab, cb) / denom, -1, 1);
    return Math.acos(cosine) * 180 / Math.PI;
  }

  function _average(points) {
    var acc = { x: 0, y: 0, z: 0 };
    for (var i = 0; i < points.length; i++) {
      acc.x += points[i].x;
      acc.y += points[i].y;
      acc.z += points[i].z || 0;
    }
    return {
      x: acc.x / points.length,
      y: acc.y / points.length,
      z: acc.z / points.length
    };
  }

  function _getPalmMetrics(lm) {
    var wrist = lm[0];
    var palmCenter = _average([lm[0], lm[5], lm[9], lm[13], lm[17]]);
    var palmSize = (
      _distance(wrist, lm[5]) +
      _distance(wrist, lm[9]) +
      _distance(wrist, lm[17])
    ) / 3;
    var palmAxis = _normalize(_vector(wrist, lm[9]));

    return {
      wrist: wrist,
      center: palmCenter,
      size: palmSize || 0.001,
      axis: palmAxis
    };
  }

  function _projectAlongAxis(origin, point, axis) {
    return _dot(_vector(origin, point), axis);
  }

  function _buildFingerDescriptor(lm, metrics, cfg) {
    var tipProjection = _projectAlongAxis(metrics.wrist, lm[cfg.tip], metrics.axis);
    var pipProjection = _projectAlongAxis(metrics.wrist, lm[cfg.pip], metrics.axis);
    var mcpProjection = _projectAlongAxis(metrics.wrist, lm[cfg.mcp], metrics.axis);
    var angle = _angle(lm[cfg.mcp], lm[cfg.pip], lm[cfg.tip]);
    var reachScore = _clamp((tipProjection - mcpProjection) / (metrics.size * 0.7), 0, 1);
    var separationScore = _clamp((tipProjection - pipProjection) / (metrics.size * 0.22), 0, 1);
    var straightScore = _clamp((angle - 120) / 45, 0, 1);
    var score = (reachScore * 0.4) + (separationScore * 0.3) + (straightScore * 0.3);
    var extended = score > 0.55 && tipProjection > pipProjection + metrics.size * 0.02;
    return {
      extended: extended,
      extendedScore: score,
      curledScore: _clamp(1 - ((reachScore * 0.65) + (straightScore * 0.35)), 0, 1)
    };
  }

  function _buildThumbDescriptor(lm, metrics) {
    var thumbAngle = _angle(lm[2], lm[3], lm[4]);
    var distanceFromPalm = _distance(lm[4], metrics.center);
    var thumbBaseDistance = _distance(lm[3], metrics.center);
    var spreadScore = _clamp((distanceFromPalm - thumbBaseDistance) / (metrics.size * 0.28), 0, 1);
    var awayFromIndexScore = _clamp(_distance(lm[4], lm[5]) / (metrics.size * 0.7), 0, 1);
    var straightScore = _clamp((thumbAngle - 120) / 45, 0, 1);
    var score = (spreadScore * 0.4) + (awayFromIndexScore * 0.35) + (straightScore * 0.25);
    return {
      extended: score > 0.52,
      extendedScore: score,
      curledScore: _clamp(1 - ((spreadScore * 0.7) + (straightScore * 0.3)), 0, 1),
      verticalScore: _clamp((lm[2].y - lm[4].y) / (metrics.size * 0.8), 0, 1)
    };
  }

  function _collectFingerStates(lm) {
    var metrics = _getPalmMetrics(lm);
    if (metrics.size < 0.055) {
      return null;
    }

    return {
      metrics: metrics,
      thumb: _buildThumbDescriptor(lm, metrics),
      index: _buildFingerDescriptor(lm, metrics, { mcp: 5, pip: 6, tip: 8 }),
      middle: _buildFingerDescriptor(lm, metrics, { mcp: 9, pip: 10, tip: 12 }),
      ring: _buildFingerDescriptor(lm, metrics, { mcp: 13, pip: 14, tip: 16 }),
      pinky: _buildFingerDescriptor(lm, metrics, { mcp: 17, pip: 18, tip: 20 })
    };
  }

  function _scoreAverage(values) {
    var total = 0;
    for (var i = 0; i < values.length; i++) {
      total += values[i];
    }
    return total / values.length;
  }

  function _classifyGesture(landmarks, handedness) {
    if (!landmarks || landmarks.length < 21) {
      return { gesture: 'unknown', score: 0 };
    }

    var state = _collectFingerStates(landmarks);
    if (!state) {
      return { gesture: 'unknown', score: 0 };
    }

    var thumb = state.thumb;
    var index = state.index;
    var middle = state.middle;
    var ring = state.ring;
    var pinky = state.pinky;
    var gestureScores = {
      open_palm: _scoreAverage([
        thumb.extendedScore,
        index.extendedScore,
        middle.extendedScore,
        ring.extendedScore,
        pinky.extendedScore
      ]),
      fist: _scoreAverage([
        thumb.curledScore,
        index.curledScore,
        middle.curledScore,
        ring.curledScore,
        pinky.curledScore
      ]),
      peace: _scoreAverage([
        index.extendedScore,
        middle.extendedScore,
        ring.curledScore,
        pinky.curledScore
      ]),
      point_up: _scoreAverage([
        index.extendedScore,
        middle.curledScore,
        ring.curledScore,
        pinky.curledScore
      ]),
      thumbs_up: _scoreAverage([
        thumb.extendedScore,
        thumb.verticalScore,
        index.curledScore,
        middle.curledScore,
        ring.curledScore,
        pinky.curledScore
      ])
    };

    if (!index.extended || !middle.extended) {
      gestureScores.peace *= 0.7;
    }
    if (!index.extended) {
      gestureScores.point_up *= 0.7;
    }
    if (!thumb.extended) {
      gestureScores.thumbs_up *= 0.65;
    }
    if (ring.extended || pinky.extended) {
      gestureScores.peace *= 0.72;
      gestureScores.point_up *= 0.68;
      gestureScores.thumbs_up *= 0.75;
    }
    if (index.extended || middle.extended || ring.extended || pinky.extended) {
      gestureScores.fist *= 0.7;
    }

    var bestGesture = 'unknown';
    var bestScore = 0;
    var secondScore = 0;
    var key;
    for (key in gestureScores) {
      if (!Object.prototype.hasOwnProperty.call(gestureScores, key)) continue;
      var score = gestureScores[key];
      if (score > bestScore) {
        secondScore = bestScore;
        bestScore = score;
        bestGesture = key;
      } else if (score > secondScore) {
        secondScore = score;
      }
    }

    if (bestScore < MIN_GESTURE_SCORE || bestScore - secondScore < 0.08) {
      return { gesture: 'unknown', score: bestScore, handedness: handedness || 'unknown' };
    }

    return {
      gesture: bestGesture,
      score: bestScore,
      handedness: handedness || 'unknown'
    };
  }

  function _showIndicator(text, tone, duration) {
    var el = document.getElementById('gesture-indicator');
    if (!el) return;
    el.textContent = text;
    el.className = '';
    el.id = 'gesture-indicator';
    if (tone) {
      el.classList.add(tone);
    }
    el.classList.add('show');
    clearTimeout(el._timeout);
    el._timeout = setTimeout(function () {
      el.classList.remove('show');
      el.classList.remove('warn');
      el.classList.remove('error');
    }, duration || 1200);
  }

  function _persistEnabled(enabled) {
    try {
      localStorage.setItem(STORAGE_KEY, enabled ? '1' : '0');
    } catch (e) { }
  }

  function _markDisabled() {
    _persistEnabled(false);
    _updateButton();
  }

  function _executeGesture(gesture) {
    if (_checkCooldown()) return;

    var label = '';
    switch (gesture) {
      case 'open_palm':
        label = '回到顶部';
        window.scrollTo({ top: 0, behavior: 'smooth' });
        break;
      case 'fist':
        if (window.history.length > 1) {
          label = '返回上一页';
          window.history.back();
        } else {
          label = '无可返回页面';
        }
        break;
      case 'peace':
        label = '刷新页面';
        window.location.reload();
        break;
      case 'thumbs_up':
        label = '向上滚动';
        window.scrollBy({ top: -300, behavior: 'smooth' });
        break;
      case 'point_up':
        label = '向下滚动';
        window.scrollBy({ top: 300, behavior: 'smooth' });
        break;
      default:
        return;
    }
    _resetCooldown();
    _showIndicator(label, 'success', 900);
  }

  function _resetGestureState() {
    _candidateGesture = 'unknown';
    _candidateScore = 0;
    _candidateSeenAt = 0;
  }

  function _applyGestureCandidate(gesture, score) {
    var now = Date.now();

    if (now - _lastResultsAt > STALE_RESULT_RESET_MS) {
      _resetGestureState();
    }

    if (gesture === 'unknown' || score < MIN_GESTURE_SCORE) {
      _candidateScore = Math.max(0, _candidateScore - SCORE_DECAY);
      if (_candidateScore === 0) {
        _candidateGesture = 'unknown';
      }
      return;
    }

    if (_candidateGesture !== gesture) {
      _candidateGesture = gesture;
      _candidateScore = score;
      _candidateSeenAt = now;
      return;
    }

    _candidateScore = Math.min(3, _candidateScore + score);
    if (_candidateScore >= TRIGGER_SCORE && now - _candidateSeenAt >= 66) {
      _executeGesture(gesture);
      _resetGestureState();
    }
  }

  function _pickBestGesture(results) {
    if (!results.multiHandLandmarks || !results.multiHandLandmarks.length) {
      return { gesture: 'unknown', score: 0 };
    }

    var best = { gesture: 'unknown', score: 0 };
    var second = { gesture: 'unknown', score: 0 };

    for (var i = 0; i < results.multiHandLandmarks.length; i++) {
      var handedness = 'unknown';
      if (results.multiHandedness && results.multiHandedness[i] && results.multiHandedness[i].label) {
        handedness = results.multiHandedness[i].label;
      }
      var candidate = _classifyGesture(results.multiHandLandmarks[i], handedness);
      if (candidate.score > best.score) {
        second = best;
        best = candidate;
      } else if (candidate.score > second.score) {
        second = candidate;
      }
    }

    if (best.gesture !== 'unknown' && second.gesture !== 'unknown' && best.gesture !== second.gesture && best.score - second.score < 0.08) {
      return { gesture: 'unknown', score: best.score };
    }

    return best;
  }

  function _handleRuntimeError(message, fatal) {
    console.warn('[gesture]', message);
    _showIndicator(message, fatal ? 'error' : 'warn', fatal ? 2200 : 1600);
    if (fatal) {
      MOD.stop({ silent: true, preserveEnabled: false });
      _markDisabled();
    }
  }

  function _scheduleRestart(reason) {
    if (_restartCount >= MAX_RESTARTS) {
      _handleRuntimeError(reason || '手势识别已停止', true);
      return;
    }
    _restartCount += 1;
    console.warn('[gesture] 准备重启:', reason);
    _showIndicator('识别中断，正在重试', 'warn', 1200);
    MOD.stop({ silent: true, preserveEnabled: true });
    setTimeout(function () {
      if (MOD.isEnabled()) {
        MOD.start();
      }
    }, 300);
  }

  function _bindTrackLifecycle(stream) {
    if (!stream || !stream.getTracks) return;
    stream.getTracks().forEach(function (track) {
      track.onended = function () {
        _handleRuntimeError('视频流已中断', true);
      };
    });
  }

  function _createDOM() {
    if (!document.getElementById('gesture-indicator')) {
      var indicator = document.createElement('div');
      indicator.id = 'gesture-indicator';
      document.body.appendChild(indicator);
    }

    if (!document.getElementById('gesture-camera')) {
      var camera = document.createElement('video');
      camera.id = 'gesture-camera';
      camera.autoplay = true;
      camera.playsInline = true;
      camera.muted = true;
      camera.classList.add('hidden');
      document.body.appendChild(camera);
    }

    if (!document.getElementById('gesture-toggle-btn')) {
      var btn = document.createElement('button');
      btn.id = 'gesture-toggle-btn';
      btn.innerHTML = '<i class="fas fa-hand-paper"></i>';
      btn.title = '手势控制：已关闭';
      btn.onclick = function () { MOD.toggle(); };
      document.body.appendChild(btn);

      _makeDraggable(document.getElementById('gesture-camera'), btn);
    }
  }

  function _makeDraggable(camera, btn) {
    if (!camera || camera._gestureDragBound) return;
    camera._gestureDragBound = true;

    var dragging = false;
    var startX;
    var startY;
    var camStartRight;
    var camStartBottom;

    camera.addEventListener('mousedown', function (e) {
      dragging = true;
      startX = e.clientX;
      startY = e.clientY;
      var cs = getComputedStyle(camera);
      camStartRight = parseInt(cs.right, 10) || 20;
      camStartBottom = parseInt(cs.bottom, 10) || 80;
      e.preventDefault();
    });

    document.addEventListener('mousemove', function (e) {
      if (!dragging) return;
      var dx = startX - e.clientX;
      var dy = startY - e.clientY;
      var newRight = _clamp(camStartRight + dx, 0, window.innerWidth - 160);
      var newBottom = _clamp(camStartBottom + dy, 0, window.innerHeight - 120);
      camera.style.right = newRight + 'px';
      camera.style.bottom = newBottom + 'px';
      if (btn) {
        btn.style.right = (newRight + 52) + 'px';
        btn.style.bottom = (newBottom + 140) + 'px';
      }
    });

    document.addEventListener('mouseup', function () {
      dragging = false;
    });
  }

  function _updateButton() {
    var btn = document.getElementById('gesture-toggle-btn');
    var cam = document.getElementById('gesture-camera');
    if (!btn) return;
    var icon = btn.querySelector('i');

    if (MOD.isEnabled()) {
      btn.classList.add('active');
      btn.removeAttribute('aria-disabled');
      if (icon) icon.className = 'fas fa-hand-paper';
      btn.title = _modelReady ? '手势控制：已开启' : '手势控制：启动中';
      if (cam) cam.classList.remove('hidden');
    } else {
      btn.classList.remove('active');
      if (icon) icon.className = 'fas fa-hand-peace';
      btn.title = '手势控制：已关闭';
      if (cam) cam.classList.add('hidden');
    }
  }

  function _ensurePreprocessCanvas() {
    if (!_processingCanvas) {
      _processingCanvas = document.createElement('canvas');
      _processingCanvas.width = PREPROCESS_SIZE;
      _processingCanvas.height = PREPROCESS_SIZE;
      _processingCtx = _processingCanvas.getContext('2d', { willReadFrequently: true });
    }
    return _processingCtx;
  }

  function _estimateBrightness(ctx) {
    var image = ctx.getImageData(0, 0, PREPROCESS_SIZE, PREPROCESS_SIZE).data;
    var step = 16;
    var total = 0;
    var count = 0;
    for (var i = 0; i < image.length; i += 4 * step) {
      total += (image[i] * 0.299) + (image[i + 1] * 0.587) + (image[i + 2] * 0.114);
      count++;
    }
    return count ? total / count : 128;
  }

  function _buildPreprocessedFrame() {
    var ctx = _ensurePreprocessCanvas();
    if (!ctx || !_video) return _video;

    var videoWidth = _video.videoWidth || 640;
    var videoHeight = _video.videoHeight || 480;
    if (!videoWidth || !videoHeight) return _video;

    var brightness = 1;
    var contrast = 1;
    if (_sceneLuma < 70) {
      brightness = 1.24;
      contrast = 1.16;
    } else if (_sceneLuma < 110) {
      brightness = 1.1;
      contrast = 1.08;
    } else if (_sceneLuma > 190) {
      brightness = 0.92;
      contrast = 1.1;
    } else if (_sceneLuma > 165) {
      brightness = 0.97;
      contrast = 1.05;
    }

    var scale = Math.min(PREPROCESS_SIZE / videoWidth, PREPROCESS_SIZE / videoHeight);
    var drawWidth = videoWidth * scale;
    var drawHeight = videoHeight * scale;
    var dx = (PREPROCESS_SIZE - drawWidth) / 2;
    var dy = (PREPROCESS_SIZE - drawHeight) / 2;

    ctx.save();
    ctx.clearRect(0, 0, PREPROCESS_SIZE, PREPROCESS_SIZE);
    ctx.fillStyle = '#000';
    ctx.fillRect(0, 0, PREPROCESS_SIZE, PREPROCESS_SIZE);
    ctx.filter = 'brightness(' + brightness + ') contrast(' + contrast + ')';
    ctx.drawImage(_video, dx, dy, drawWidth, drawHeight);
    ctx.restore();

    _sampleCounter++;
    if (_sampleCounter % 12 === 0) {
      try {
        _sceneLuma = _estimateBrightness(ctx);
      } catch (err) {
        console.warn('[gesture] 亮度估计失败:', err.message);
      }
    }

    return _processingCanvas;
  }

  function _onHandResults(results) {
    _frameInFlight = false;
    _lastResultsAt = Date.now();
    _sendErrorCount = 0;

    if (!_modelReady) {
      _modelReady = true;
      _restartCount = 0;
      if (_modelTimeout) {
        clearTimeout(_modelTimeout);
        _modelTimeout = null;
      }
      console.log('[gesture] MediaPipe 手势识别模型已就绪');
      _showIndicator('手势识别已就绪', 'success', 800);
      _updateButton();
    }

    if (!MOD.isEnabled()) return;

    var best = _pickBestGesture(results);
    _applyGestureCandidate(best.gesture, best.score || 0);
  }

  function _sendFrame() {
    if (!_handsInstance || !_video || _video.readyState < 2 || _frameInFlight) {
      return;
    }

    _frameInFlight = true;
    _frameSentAt = Date.now();

    _handsInstance.send({ image: _buildPreprocessedFrame() }).catch(function (err) {
      _frameInFlight = false;
      _sendErrorCount++;
      console.warn('[gesture] 推理失败:', err.message);
      if (_sendErrorCount >= 3) {
        _scheduleRestart('模型推理异常');
      }
    });
  }

  function _processFrame() {
    if (!MOD.isEnabled()) return;
    _lastLoopAt = 0;
    _resetGestureState();

    function loop(now) {
      if (!MOD.isEnabled()) return;
      _animationId = requestAnimationFrame(loop);

      if (_frameInFlight && Date.now() - _frameSentAt > RESULT_TIMEOUT_MS) {
        _frameInFlight = false;
        _scheduleRestart('手部检测超时');
        return;
      }

      if (!_lastLoopAt || now - _lastLoopAt >= PROCESS_INTERVAL_MS) {
        _lastLoopAt = now;
        _sendFrame();
      }
    }

    _animationId = requestAnimationFrame(loop);
  }

  var _packedAssetsData = null;
  var _packedAssetsReady = fetch(MODEL_BASE + 'hands_solution_packed_assets.data')
    .then(function (r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.arrayBuffer();
    })
    .then(function (data) {
      _packedAssetsData = data;
      console.log('[gesture] packed assets 预加载成功: ' + data.byteLength + ' bytes');
    })
    .catch(function (err) {
      console.warn('[gesture] packed assets 预加载失败，将回退到 XHR:', err.message);
      return Promise.resolve();
    });

  function _addPreloadedPackage(obj) {
    if (!obj) return;
    obj.getPreloadedPackage = function () {
      return _packedAssetsData;
    };
  }

  var _originalPackedAssets;
  if (window.createMediapipeSolutionsPackedAssets) {
    _originalPackedAssets = window.createMediapipeSolutionsPackedAssets;
    _addPreloadedPackage(_originalPackedAssets);
  }
  Object.defineProperty(window, 'createMediapipeSolutionsPackedAssets', {
    get: function () {
      return _originalPackedAssets;
    },
    set: function (val) {
      _originalPackedAssets = val;
      _addPreloadedPackage(val);
    },
    configurable: true,
    enumerable: true
  });

  function _loadHandsScript() {
    if (typeof Hands !== 'undefined') {
      return Promise.resolve();
    }
    if (_loadScriptPromise) {
      return _loadScriptPromise;
    }

    _loadScriptPromise = new Promise(function (resolve, reject) {
      var existing = document.querySelector('script[data-gesture-hands-script="1"]');
      if (existing) {
        existing.addEventListener('load', function () { resolve(); }, { once: true });
        existing.addEventListener('error', function () { reject(new Error('hands.js 加载失败')); }, { once: true });
        return;
      }

      var script = document.createElement('script');
      script.src = MODEL_BASE + 'hands.js';
      script.dataset.gestureHandsScript = '1';
      script.onload = function () { resolve(); };
      script.onerror = function () { reject(new Error('hands.js 加载失败')); };
      document.head.appendChild(script);
    }).catch(function (err) {
      _loadScriptPromise = null;
      throw err;
    });

    return _loadScriptPromise;
  }

  function _buildHandsInstance() {
    _handsInstance = new Hands({
      locateFile: function (file) {
        return MODEL_BASE + file;
      }
    });
    _handsInstance.setOptions({
      maxNumHands: 2,
      modelComplexity: 0,
      minDetectionConfidence: 0.65,
      minTrackingConfidence: 0.6
    });
    _handsInstance.onResults(_onHandResults);
    _modelReady = false;
    _lastResultsAt = 0;
    _sendErrorCount = 0;
    _modelTimeout = setTimeout(function () {
      if (!_modelReady) {
        _handleRuntimeError('模型加载超时，请检查本地资源', true);
      }
    }, MODEL_INIT_TIMEOUT_MS);
  }

  MOD.start = function () {
    if (_stream && _handsInstance) return;

    _createDOM();
    _updateButton();

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      _handleRuntimeError('当前浏览器不支持摄像头', true);
      return;
    }

    _loadHandsScript()
      .then(function () {
        return navigator.mediaDevices.getUserMedia({
          video: {
            width: { ideal: 640 },
            height: { ideal: 480 },
            facingMode: 'user'
          },
          audio: false
        });
      })
      .then(function (stream) {
        _stream = stream;
        _bindTrackLifecycle(stream);
        _video = document.getElementById('gesture-camera');
        if (!_video) {
          throw new Error('视频节点不存在');
        }
        _video.srcObject = stream;
        return Promise.all([
          _video.play(),
          _packedAssetsReady
        ]);
      })
      .then(function () {
        _buildHandsInstance();
        _updateButton();
        _showIndicator('手势识别启动中', 'warn', 900);
        _processFrame();
      })
      .catch(function (err) {
        console.warn('[gesture] 初始化失败:', err.message);
        MOD.stop({ silent: true, preserveEnabled: false });
        _markDisabled();
        if (/hands\.js/i.test(err.message || '')) {
          _showIndicator('手势库未安装', 'error', 2200);
          return;
        }
        if (/NotAllowedError/i.test(err.name || '') || /Permission/i.test(err.message || '')) {
          _showIndicator('摄像头权限被拒绝', 'error', 2200);
          return;
        }
        _showIndicator('手势识别启动失败', 'error', 2200);
      });
  };

  MOD.stop = function (options) {
    var opts = options || {};

    if (_animationId) {
      cancelAnimationFrame(_animationId);
      _animationId = null;
    }
    if (_modelTimeout) {
      clearTimeout(_modelTimeout);
      _modelTimeout = null;
    }
    if (_handsInstance) {
      _handsInstance.close();
      _handsInstance = null;
    }
    if (_stream) {
      _stream.getTracks().forEach(function (t) {
        t.onended = null;
        t.stop();
      });
      _stream = null;
    }
    if (_video) {
      _video.srcObject = null;
      _video = null;
    }

    _modelReady = false;
    _frameInFlight = false;
    _frameSentAt = 0;
    _lastResultsAt = 0;
    _lastLoopAt = 0;
    _sendErrorCount = 0;
    _sampleCounter = 0;
    _sceneLuma = 128;
    _resetGestureState();

    if (!opts.preserveEnabled) {
      _persistEnabled(false);
    }
    _updateButton();

    if (!opts.silent) {
      _showIndicator('手势识别已关闭', 'warn', 800);
    }
  };

  MOD.isEnabled = function () {
    try {
      return localStorage.getItem(STORAGE_KEY) === '1';
    } catch (e) {
      return false;
    }
  };

  MOD.getStatus = function () {
    return {
      enabled: MOD.isEnabled(),
      modelReady: _modelReady,
      frameInFlight: _frameInFlight,
      lastResultAgeMs: _lastResultsAt ? Date.now() - _lastResultsAt : null,
      restartCount: _restartCount,
      sceneLuma: _sceneLuma
    };
  };

  MOD.toggle = function () {
    var next = !MOD.isEnabled();
    _persistEnabled(next);
    if (next) {
      MOD.start();
    } else {
      MOD.stop({ preserveEnabled: false });
    }
    _updateButton();
  };

  MOD.init = function () {
    if (!document.querySelector('link[data-gesture-style="1"]')) {
      var link = document.createElement('link');
      link.rel = 'stylesheet';
      link.href = '/static/css/gesture.css';
      link.dataset.gestureStyle = '1';
      document.head.appendChild(link);
    }

    _createDOM();
    _updateButton();

    if (MOD.isEnabled()) {
      MOD.start();
    }
  };

  document.addEventListener('visibilitychange', function () {
    if (!MOD.isEnabled()) return;
    if (document.hidden) {
      MOD.stop({ silent: true, preserveEnabled: true });
    } else if (!_stream) {
      MOD.start();
    }
  });

  document.addEventListener('DOMContentLoaded', function () {
    if (document.body && (document.body.classList.contains('portal-shell') || document.body.classList.contains('admin-shell'))) {
      MOD.init();
    }
  });
})();

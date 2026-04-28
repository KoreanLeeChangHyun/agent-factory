/**
 * @module terminal/terminal-input
 * Split from terminal.js. Functions attach to Board._term (M) namespace.
 */
"use strict";

(function () {
  var esc = Board.util.esc;
  var M = (Board._term = Board._term || {});

  // ── Thinking Spinner ──

  M.thinkingEl = null;

  // Claude CLI 의 위트 있는 thinking verb pool 을 본떠 여러 단어를 로테이션한다.
  // 회전 간격은 7~14초 사이 랜덤 — 고정 주기보다 자연스럽고 산만함을 줄인다.
  var THINKING_VERBS = [
    "Thinking", "Pondering", "Noodling", "Channelling", "Tomfoolering",
    "Ruminating", "Contemplating", "Brewing", "Cogitating", "Puzzling",
    "Synthesizing", "Wrangling", "Simmering", "Musing", "Scheming",
    "Percolating", "Deliberating", "Unravelling",
  ];
  var THINKING_ROTATE_MIN_MS = 7000;
  var THINKING_ROTATE_MAX_MS = 14000;

  function _pickThinkingVerb(prev) {
    if (THINKING_VERBS.length <= 1) return THINKING_VERBS[0];
    var next;
    // 직전과 같은 단어는 피해 단조로움을 줄인다.
    do {
      next = THINKING_VERBS[Math.floor(Math.random() * THINKING_VERBS.length)];
    } while (next === prev);
    return next;
  }

  function _pickRotateDelay() {
    return THINKING_ROTATE_MIN_MS + Math.random() * (THINKING_ROTATE_MAX_MS - THINKING_ROTATE_MIN_MS);
  }

  M.startSpinner = function() {
    if (Board.debugLog) Board.debugLog('startSpinner', {
      thinkingEl: !!M.thinkingEl, outputDiv: !!M.outputDiv, termStatus: Board.state.termStatus,
    });
    if (M.thinkingEl) return;
    if (!M.outputDiv) return;

    M.thinkingEl = document.createElement("div");
    M.thinkingEl.className = "term-thinking";
    M.thinkingEl.id = "term-thinking-active";
    var dot = document.createElement("span");
    dot.className = "term-thinking-dot";
    var label = document.createElement("span");
    label.className = "term-thinking-label";
    M.thinkingEl.appendChild(dot);
    M.thinkingEl.appendChild(document.createTextNode(" "));
    M.thinkingEl.appendChild(label);

    var currentVerb = _pickThinkingVerb(null);
    label.textContent = currentVerb + "…";

    var el = M.thinkingEl;
    function _scheduleRotate() {
      el._rotator = setTimeout(function () {
        if (el !== M.thinkingEl) return;
        currentVerb = _pickThinkingVerb(currentVerb);
        label.textContent = currentVerb + "…";
        _scheduleRotate();
      }, _pickRotateDelay());
    }
    _scheduleRotate();

    // M.outputDiv 바로 뒤(input-card 바로 앞)에 삽입하여 하단 고정
    M.outputDiv.parentNode.insertBefore(M.thinkingEl, M.outputDiv.nextSibling);
  };

  M.stopSpinner = function() {
    if (Board.debugLog) Board.debugLog('stopSpinner', {
      thinkingEl: !!M.thinkingEl, termStatus: Board.state.termStatus,
    });
    if (M.thinkingEl) {
      if (M.thinkingEl._rotator) {
        clearTimeout(M.thinkingEl._rotator);
        M.thinkingEl._rotator = null;
      }
      if (M.thinkingEl.parentNode) {
        M.thinkingEl.parentNode.removeChild(M.thinkingEl);
      }
    }
    M.thinkingEl = null;
  };

  // ── Input Management ──

  // ── Image Attachment ──

  var ALLOWED_MIME = ["image/png", "image/jpeg", "image/gif", "image/webp"];

  var MAX_IMAGE_SIZE = 20 * 1024 * 1024; // 20MB

  M.renderImagePreview = function() {
    var container = document.getElementById("terminal-image-preview");
    if (!container) return;
    container.innerHTML = "";
    M.attachedImages.forEach(function (img, idx) {
      var thumb = document.createElement("div");
      thumb.className = "terminal-image-thumb";

      var imgEl = document.createElement("img");
      imgEl.src = "data:" + img.media_type + ";base64," + img.data;
      imgEl.alt = img.name || "image";

      var removeBtn = document.createElement("button");
      removeBtn.className = "terminal-image-remove";
      removeBtn.title = "제거";
      removeBtn.innerHTML = "\u00D7";
      removeBtn.addEventListener("click", function () { M.removeImage(idx); });

      thumb.appendChild(imgEl);
      thumb.appendChild(removeBtn);
      container.appendChild(thumb);
    });
  };

  M.attachImage = function(file) {
    if (!file) return;
    if (ALLOWED_MIME.indexOf(file.type) === -1) {
      M.appendErrorMessage("[첨부 오류] 지원하지 않는 형식입니다 (PNG/JPG/GIF/WebP 만 가능)");
      return;
    }
    if (file.size > MAX_IMAGE_SIZE) {
      M.appendErrorMessage("[첨부 오류] 파일 크기가 20MB를 초과합니다");
      return;
    }
    var reader = new FileReader();
    reader.onload = function (e) {
      var dataUrl = e.target.result;
      // data:image/png;base64,XXXX 에서 base64 부분만 추출
      var base64 = dataUrl.split(",")[1];
      M.attachedImages.push({ data: base64, media_type: file.type, name: file.name });
      M.renderImagePreview();
    };
    reader.readAsDataURL(file);
  };

  M.removeImage = function(index) {
    M.attachedImages.splice(index, 1);
    M.renderImagePreview();
  };

  M.clearImages = function() {
    M.attachedImages = [];
    M.renderImagePreview();
    var fileInput = document.getElementById("terminal-attach-input");
    if (fileInput) fileInput.value = "";
  };

  /**
   * 바이트 수를 사람이 읽기 쉬운 단위(B, KB, MB)로 변환하여 반환한다.
   */
  M.formatFileSize = function(bytes) {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  };

  /**
   * 비이미지 파일 프리뷰 카드를 terminal-image-preview 컨테이너에 렌더링한다.
   * 기존 이미지 썸네일(M.renderImagePreview)과 동일 컨테이너를 공유하여
   * 하나의 프리뷰 스트립으로 관리한다.
   */
  M.renderFilePreview = function() {
    var container = document.getElementById("terminal-image-preview");
    if (!container) return;

    // 기존 파일 카드만 제거하고 이미지 썸네일은 M.renderImagePreview()가 관리
    var existingCards = container.querySelectorAll(".terminal-file-card");
    existingCards.forEach(function (card) { card.parentNode.removeChild(card); });

    M.attachedFiles.forEach(function (info, idx) {
      var card = document.createElement("div");
      card.className = "terminal-file-card";
      card.setAttribute("data-file-idx", idx);

      // 확장자 라벨
      var ext = info.name.split(".").pop().toUpperCase().slice(0, 6) || "FILE";
      var extLabel = document.createElement("div");
      extLabel.className = "terminal-file-card-ext";
      extLabel.textContent = ext;

      // 파일명 (ellipsis)
      var nameLabel = document.createElement("div");
      nameLabel.className = "terminal-file-card-name";
      nameLabel.textContent = info.name;
      nameLabel.title = info.name;

      // 파일 크기
      var sizeLabel = document.createElement("div");
      sizeLabel.className = "terminal-file-card-size";
      sizeLabel.textContent = M.formatFileSize(info.size);

      // 제거 버튼
      var removeBtn = document.createElement("button");
      removeBtn.className = "terminal-image-remove";
      removeBtn.title = "제거";
      removeBtn.innerHTML = "\u00D7";
      removeBtn.addEventListener("click", (function (capturedIdx) {
        return function () { M.removeFile(capturedIdx); };
      })(idx));

      card.appendChild(extLabel);
      card.appendChild(nameLabel);
      card.appendChild(sizeLabel);
      card.appendChild(removeBtn);
      container.appendChild(card);
    });
  };

  M.removeFile = function(index) {
    var removed = M.attachedFiles.splice(index, 1);
    // textarea에서 파일명 제거
    var targetInput = document.getElementById("terminal-input");
    if (targetInput && removed.length > 0) {
      var name = removed[0].name;
      var re = new RegExp("(?:^|\\n)" + name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "(?=\\n|$)", "g");
      targetInput.value = targetInput.value.replace(re, "").replace(/^\n/, "").replace(/\n\n+/g, "\n");
      var evt = document.createEvent("Event");
      evt.initEvent("input", true, true);
      targetInput.dispatchEvent(evt);
    }
    M.renderFilePreview();
  };

  M.clearFiles = function() {
    M.attachedFiles = [];
    M.renderFilePreview();
  };

  /**
   * 문자열이 파일 경로 패턴인지 판별한다.
   * - Unix 절대 경로: /로 시작, // 제외 (프로토콜 상대 URL)
   * - Windows 절대 경로: C:\ 등 드라이브 문자
   * - 여러 줄 경로: 각 줄이 경로 패턴인 경우
   * - URL(http://, https://) 제외
   */
  M.isFilePath = function(text) {
    if (!text) return false;
    // URL 제외
    if (/^https?:\/\//i.test(text.trim())) return false;
    // 여러 줄인 경우 각 줄을 검사하여 모두 경로 패턴이면 true
    var lines = text.trim().split(/\r?\n/);
    var pathLine = /^\/[^\/\s]+\/|^[A-Za-z]:\\/;
    for (var i = 0; i < lines.length; i++) {
      var line = lines[i].trim();
      if (line && !pathLine.test(line)) return false;
    }
    return pathLine.test(lines[0].trim());
  };

  /**
   * textarea의 현재 커서 위치(selectionStart/End)에 텍스트를 삽입한다.
   */
  M.insertTextAtCursor = function(textarea, text) {
    var start = textarea.selectionStart;
    var end = textarea.selectionEnd;
    var before = textarea.value.substring(0, start);
    var after = textarea.value.substring(end);
    textarea.value = before + text + after;
    var pos = start + text.length;
    textarea.selectionStart = pos;
    textarea.selectionEnd = pos;
    textarea.focus();
    // input 이벤트를 발생시켜 자동 높이 조정 트리거
    var evt = document.createEvent("Event");
    evt.initEvent("input", true, true);
    textarea.dispatchEvent(evt);
  };

  /**
   * .terminal-input-card 내부에 파일명 뱃지를 잠시 표시한다.
   */
  M.showFileBadge = function(card, names) {
    // 기존 뱃지 제거
    var prev = card.querySelector(".terminal-file-badge");
    if (prev) prev.parentNode.removeChild(prev);

    var badge = document.createElement("div");
    badge.className = "terminal-file-badge";
    badge.textContent = names.join(", ");
    card.appendChild(badge);

    setTimeout(function () {
      if (badge.parentNode) badge.parentNode.removeChild(badge);
    }, 3000);
  };

  M.setInputLocked = function(locked) {
    M.inputLocked = locked;
    var input = document.getElementById("terminal-input");
    var sendBtn = document.getElementById("terminal-send-btn");
    // busy 상태에서도 입력창은 활성 유지 (큐 입력 허용). idle/busy 만 inputtable.
    // stopped/starting/archived/missing 은 입력 비활성.
    var inputtable = Board.util.TERM_STATUS_INPUTTABLE.has(Board.state.termStatus);
    var shouldDisable = !inputtable;
    if (input) {
      input.disabled = shouldDisable;
      if (!shouldDisable) {
        input.focus();
      }
    }
    if (sendBtn) {
      sendBtn.disabled = shouldDisable;
    }
    var attachBtn = document.getElementById("terminal-attach-btn");
    if (attachBtn) {
      attachBtn.disabled = shouldDisable;
    }
  };

  M.sendInput = function() {
    if (M.isWorkflowMode) return;
    var input = document.getElementById("terminal-input");
    if (!input) return;
    var text = input.value.trim();
    var hasImages = M.attachedImages.length > 0;
    if (!text && !hasImages) return;
    var inputtable = Board.util.TERM_STATUS_INPUTTABLE;
    if (!inputtable.has(Board.state.termStatus)) return;

    input.value = "";
    input.style.height = "auto";

    // Route slash commands (큐에 넣지 않고 즉시 처리) — 이미지 있으면 슬래시 커맨드 미적용
    // M.isFilePath() 체크: /home/... 등 파일 경로는 슬래시 커맨드로 라우팅하지 않음
    if (!hasImages && text.charAt(0) === "/" && !M.isFilePath(text)) {
      Board.slashCommands.handle(text, {
        isWorkflowMode: M.isWorkflowMode,
        appendSystemMessage: M.appendSystemMessage,
        appendHtmlBlock: M.appendHtmlBlock,
        appendErrorMessage: M.appendErrorMessage,
        clearOutput: M.clearOutput,
        postJson: Board.session.postJson
      });
      return;
    }

    // busy 상태(응답 대기 중)이면 enqueueInput 으로 라우팅 (이미지 첨부 포함).
    // 큐 entry 는 outputDiv 에 미리 echo 하지 않으며, 큐 stack 카드로만 노출된다.
    if (Board.state.termStatus === "busy") {
      var imagesSnapshot = hasImages
        ? M.attachedImages.map(function (img) { return { data: img.data, media_type: img.media_type, name: img.name }; })
        : null;
      M.enqueueInput(text, imagesSnapshot);
      if (hasImages) {
        M.clearImages();
        M.clearFiles();
      }
      return;
    }

    var div = document.createElement("div");
    div.className = "term-message term-user";
    if (text) div.textContent = text;
    if (hasImages) {
      var thumbRow = document.createElement("div");
      thumbRow.style.cssText = "display:flex;gap:4px;flex-wrap:wrap;margin-top:4px;";
      M.attachedImages.forEach(function (img) {
        var t = document.createElement("img");
        t.src = "data:" + img.media_type + ";base64," + img.data;
        t.style.cssText = "width:48px;height:48px;object-fit:cover;border-radius:6px;border:1px solid #3a3a3a;";
        thumbRow.appendChild(t);
      });
      div.appendChild(thumbRow);
    }
    M.appendToOutput(div);

    // 전송 payload 구성
    var payload = { text: text };
    if (hasImages) {
      payload.images = M.attachedImages.map(function (img) {
        return { data: img.data, media_type: img.media_type };
      });
    }
    M.clearImages();
    M.clearFiles();

    // Mark text as locally sent so the user_input SSE echo is skipped
    if (text && Board.session && Board.session._markSent) {
      Board.session._markSent(text);
    }

    // ESC 인터럽트 시 입력창 복원용으로 직전 송신 텍스트 저장.
    M._lastSentText = text || "";
    // 새 메시지를 보냈으므로 localStorage 의 ESC 복원 텍스트는 클리어.
    try { localStorage.removeItem("board.term.lastSentText"); } catch (e) {}

    M.setInputLocked(true);
    M.startSpinner();
    Board.state.setTermStatus("busy");
    M.updateControlBar();
    // 사용자가 엔터로 전송한 순간은 "최신 응답을 보고 싶다"는 명시적 액션.
    // isNearBottom 판정과 무관하게 사용자 메시지 + 스피너가 보이도록 하단 이동.
    if (M.outputDiv) M.outputDiv.scrollTop = M.outputDiv.scrollHeight;

    var ep = M.endpoints();
    Board.session.postJson(ep.input, ep.inputBody(payload)).catch(function (err) {
      M.stopSpinner();
      M.appendErrorMessage("[Error] " + err.message);
      M.setInputLocked(false);
      Board.state.setTermStatus("idle");
      M.updateControlBar();
    });
  };

  // drainQueue 는 구형 API (string push 방식). 1:1 모델에서는 commitQueue 로 위임한다.
  // session.js fallback 경로에서 호출될 수 있으므로 alias 로 보존.
  M.drainQueue = function() {
    if (M.isWorkflowMode) return;
    M.commitQueue();
  };

  M.interruptSession = function() {
    if (M.isWorkflowMode) return;
    if (Board.state.termStatus !== "busy") return;
    if (M._interruptInFlight) return;
    M._interruptInFlight = true;
    // [ESC 자동 resume 가드] ESC 직후 도착하는 process_exit 을 인식하기 위한 플래그.
    // exit_code 가 SDK graceful shutdown 으로 인해 130이 아닐 가능성을 커버한다.
    // 5초 후 자동 클리어 (사용자가 ESC 후 다른 동작을 한 시점은 이 윈도우 밖).
    M._recentInterrupt = true;
    if (M._recentInterruptTimer) clearTimeout(M._recentInterruptTimer);
    M._recentInterruptTimer = setTimeout(function () {
      M._recentInterrupt = false;
      M._recentInterruptTimer = null;
    }, 5000);
    M.updateControlBar();

    Board.session.postJson("/terminal/interrupt").then(function () {
      M.stopSpinner();
      if (M.textBuffer) {
        if (Board.WfTicketRenderer && Board.WfTicketRenderer.detect(M.textBuffer)) {
          Board.WfTicketRenderer.render(M.textBuffer);
        } else {
          var html = M.renderMarkdownToHtml(M.textBuffer);
          M.appendHtmlBlock(html, "term-message term-assistant");
        }
      }
      M.textBuffer = "";
      // 결과가 도착하지 못한 빈 tool 박스 제거 — toolBoxMap 의 모든 항목 검사.
      // 결과가 이미 들어간 박스는 removeEmptyToolBox 가 비어있지 않다고 판단해 보존.
      Object.keys(M.toolBoxMap).forEach(function (tuid) {
        M.removeEmptyToolBox(tuid);
      });
      M.toolBoxMap = {};
      M.currentToolBox = null;
      M.toolInputBuffer = "";
      M.currentToolName = null;
      // 큐에 push 되어 대기 중이던 메시지를 정리한다 — 사용자 "중지" 의도는
      // 큐도 포함. 미처리하면 idle 전환 시 advanceTurn 이 자동 전송해버린다.
      // 1:1 모델: inputQueue 는 단순 평면 배열이므로 length = 0 으로 전체 정리.
      // DOM echo 를 미리 하지 않으므로 outputDiv 에서 별도 DOM 정리 불필요.
      if (M.inputQueue && M.inputQueue.length > 0) {
        M.inputQueue.length = 0;
      }
      // 큐 stack 카드도 모두 제거 (DOM 정리).
      var queueStack = document.getElementById("terminal-input-queue");
      if (queueStack) {
        while (queueStack.firstChild) queueStack.removeChild(queueStack.firstChild);
        queueStack.setAttribute("hidden", "");
      }
      // [ESC 복원] 직전 보낸 사용자 메시지를 입력창에 자동 복원하여
      // 사용자가 수정하거나 그대로 다시 보낼 수 있게 한다.
      // 현재 입력창에 사용자가 이미 다른 텍스트를 타이핑 중인 경우는 보존(덮어쓰기 X).
      // 또한 localStorage 에도 저장하여 새로고침 후에도 유지한다.
      if (M._lastSentText) {
        var inputEl = document.getElementById("terminal-input");
        if (inputEl && !inputEl.value) {
          inputEl.value = M._lastSentText;
          inputEl.style.height = "auto";
          inputEl.style.height = inputEl.scrollHeight + "px";
        }
        try { localStorage.setItem("board.term.lastSentText", M._lastSentText); } catch (e) {}
        M._lastSentText = "";
      }
      M.updateControlBar();
      // 상태 변경 및 입력 잠금 해제는 result SSE 이벤트 핸들러에 위임한다.
      // SIGINT 후 Claude CLI는 반드시 result 이벤트를 발행하므로 여기서 직접 변경하지 않는다.
      // (직접 변경 시 서버가 아직 running 상태일 때 클라이언트가 idle로 전환되어 409 발생)
      // _interruptInFlight 는 _onResult 에서 끈다.
    }).catch(function (err) {
      M.appendErrorMessage("[Error] Failed to interrupt: " + err.message);
      M._interruptInFlight = false;
      M.updateControlBar();
    });
  };

  // ── Queue Model ──

  /**
   * 입력 텍스트를 큐에 추가한다 (1:1 turn 모델).
   *
   * - busy 중 추가 입력을 평면 큐에 push 한다.
   * - 큐 entry 는 메시지 흐름(outputDiv)에 미리 echo 하지 않는다.
   * - hint 카운트 갱신만 수행(updateControlBar 호출).
   * - idle commit 타이머 / turn-id 생성 / nextTurn 필드 일체 없음.
   *
   * @param {string} text - 추가할 텍스트
   */
  /**
   * 큐 stack 에 entry 카드를 추가한다.
   * 컨테이너가 hidden 이면 해제. entry 클릭 핸들러로 × 삭제 연결.
   * 이미지 첨부 entry: 텍스트 없으면 "[이미지 N장]" 라벨, 있으면 텍스트 + 끝에 "[+N장]" 표기.
   */
  function _renderQueueCard(entry) {
    var container = document.getElementById("terminal-input-queue");
    if (!container) return;

    var imageCount = entry.images ? entry.images.length : 0;
    var imageLabel = imageCount > 0 ? "[이미지 " + imageCount + "장]" : "";
    var displayText = entry.text || "";
    if (displayText && imageCount > 0) {
      displayText = displayText + " " + imageLabel;
    } else if (!displayText && imageCount > 0) {
      displayText = imageLabel;
    }

    var item = document.createElement("div");
    item.className = "terminal-queue-item";
    item.setAttribute("data-entry-id", entry.id);
    item.title = displayText; // 호버 시 전체 텍스트 노출 (한 줄 ellipsis 보완)

    var textSpan = document.createElement("span");
    textSpan.className = "terminal-queue-text";
    textSpan.textContent = displayText;

    var removeBtn = document.createElement("button");
    removeBtn.className = "terminal-queue-remove";
    removeBtn.type = "button";
    removeBtn.title = "큐에서 삭제";
    removeBtn.innerHTML = "&times;";
    (function (eid) {
      removeBtn.addEventListener("click", function (ev) {
        ev.stopPropagation();
        if (typeof M.removePendingEntry === "function") M.removePendingEntry(eid);
      });
    })(entry.id);

    item.appendChild(textSpan);
    item.appendChild(removeBtn);
    container.appendChild(item);

    if (container.hasAttribute("hidden")) container.removeAttribute("hidden");
  }

  /**
   * 큐 stack 에서 특정 entry 카드를 제거한다. 비면 컨테이너 hidden.
   */
  function _removeQueueCard(entryId) {
    var container = document.getElementById("terminal-input-queue");
    if (!container) return;
    var item = container.querySelector('[data-entry-id="' + entryId + '"]');
    if (item && item.parentNode) item.parentNode.removeChild(item);
    if (!container.children.length) container.setAttribute("hidden", "");
  }

  M.enqueueInput = function(text, images) {
    text = text || "";
    images = images || null;
    var hasImages = images && images.length > 0;
    if (!text && !hasImages) return;

    var entry = {
      id: "entry-" + Date.now() + "-" + Math.floor(Math.random() * 0x10000).toString(16),
      text: text,
      images: hasImages ? images : null,
      ts: Date.now(),
      status: "pending"
    };

    M.inputQueue.push(entry);

    // 큐 stack 에 카드 추가 (입력란 위 오른쪽 정렬 영역).
    _renderQueueCard(entry);

    // hint 영역 카운트도 갱신한다.
    M.updateControlBar();
  };

  /**
   * 큐 첫 entry 1개를 dequeue → outputDiv 에 echo → send 한다.
   *
   * 호출 조건:
   * (a) idle 상태에서 신규 Enter (terminal.js keydown 핸들러)
   * (b) busy → idle 전환 시 advanceTurn 이 잔여 큐 처리
   *
   * busy 중 호출 시 무시 (advanceTurn 경로로 처리됨).
   */
  M.commitQueue = function() {
    // busy 중이면 commit 무시 — advanceTurn 이 결과 도착 후 처리한다
    if (Board.state.termStatus === "busy") return;

    // 큐가 비면 nothing to do
    if (M.inputQueue.length === 0) return;

    // 첫 entry 1개만 dequeue (1 turn = 1 메시지)
    var entry = M.inputQueue.shift();

    // 큐 stack 에서 해당 카드 제거 (dequeue → 처리 시작 시각 신호)
    _removeQueueCard(entry.id);

    // 메시지 흐름에 echo (term-message term-user — 텍스트 + 이미지 thumbnail)
    var div = document.createElement("div");
    div.className = "term-message term-user";
    if (entry.text) div.textContent = entry.text;
    if (entry.images && entry.images.length > 0) {
      var thumbRow = document.createElement("div");
      thumbRow.style.cssText = "display:flex;gap:4px;flex-wrap:wrap;margin-top:4px;";
      entry.images.forEach(function (img) {
        var t = document.createElement("img");
        t.src = "data:" + img.media_type + ";base64," + img.data;
        t.style.cssText = "width:48px;height:48px;object-fit:cover;border-radius:6px;border:1px solid #3a3a3a;";
        thumbRow.appendChild(t);
      });
      div.appendChild(thumbRow);
    }
    if (M.appendToOutput) M.appendToOutput(div);

    // sent 마킹으로 SSE user_input echo 중복 방지 (텍스트만 — 이미지 echo 는 무관)
    if (entry.text && Board.session && Board.session._markSent) {
      Board.session._markSent(entry.text);
    }

    // ESC 인터럽트 시 입력창 복원용으로 직전 송신 텍스트 저장.
    M._lastSentText = entry.text || "";
    // 새 메시지를 보냈으므로 localStorage 의 ESC 복원 텍스트는 클리어.
    try { localStorage.removeItem("board.term.lastSentText"); } catch (e) {}

    M.startSpinner();
    Board.state.setTermStatus("busy");
    M.setInputLocked(true);
    if (M.outputDiv) M.outputDiv.scrollTop = M.outputDiv.scrollHeight;
    M.updateControlBar();

    // payload 구성 — 텍스트 + 이미지 (있으면)
    var payload = { text: entry.text || "" };
    if (entry.images && entry.images.length > 0) {
      payload.images = entry.images.map(function (img) {
        return { data: img.data, media_type: img.media_type };
      });
    }

    var ep = M.endpoints();
    Board.session.postJson(ep.input, ep.inputBody(payload)).catch(function (err) {
      M.stopSpinner();
      M.appendErrorMessage("[Error] " + err.message);
      M.setInputLocked(false);
      Board.state.setTermStatus("idle");
      M.updateControlBar();
    });
  };

  /**
   * 큐에서 pending entry 를 제거한다 (hint 패널 × 버튼 클릭).
   *
   * - inputQueue 에서만 제거한다.
   * - outputDiv DOM 에 미리 echo 되지 않으므로 DOM 조작 불필요.
   * - hint 패널 rerender 는 updateControlBar 에 위임한다.
   *
   * @param {string} entryId - 제거할 entry 의 id
   */
  M.removePendingEntry = function(entryId) {
    M.inputQueue = M.inputQueue.filter(function (e) { return e.id !== entryId; });
    // 큐 stack 에서 카드 제거 (× 버튼 클릭 시각 반영)
    _removeQueueCard(entryId);
    // hint 패널 rerender
    M.updateControlBar();
  };

  /**
   * turn 을 진행한다. result SSE 도착 시 session.js _onResult 가 호출한다.
   *
   * 1:1 turn 모델:
   * - 잔여 큐 entry 가 있으면 commitQueue() 로 즉시 다음 turn 처리
   * - 없으면 idle 정리(spinner 중지 / 잠금 해제)
   *
   * commitQueue 호출 전에 spinner 중지 + idle 상태 전환을 수행한다.
   * commitQueue 내부에서 다시 busy 로 전환한다.
   */
  M.advanceTurn = function() {
    M.stopSpinner();
    M.setInputLocked(false);
    Board.state.setTermStatus("idle");

    if (M.inputQueue.length > 0) {
      // 잔여 큐 entry 가 있으면 즉시 다음 entry 전송
      M.commitQueue();
    } else {
      // 큐 소진 — idle 정리
      M.updateControlBar();
    }
  };

})();

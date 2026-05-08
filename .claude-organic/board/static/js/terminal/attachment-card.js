/**
 * @module terminal/attachment-card
 * 첨부 티켓 카드 DOM 생성 헬퍼 — 단일 진실 공급원.
 *
 * 입력 측(.terminal-image-preview 프리뷰)과 메시지 렌더 측(.term-message-attachments)
 * 모두 Board._term.attachmentCard.create(att) 를 통해 동일한 DOM 구조와 룩앤필을 공유한다.
 *
 * att 객체 구조: {number, command, title, prompt?, report?, result?, fetched_at?, subtitle?}
 */
"use strict";

(function () {
  var M = (Board._term = Board._term || {});

  /**
   * command 코드를 카드 배지 텍스트로 매핑한다.
   * implement → IMP / research → RSC / review → REV / 기타 → TKT
   *
   * @param {string|undefined} command
   * @returns {string}
   */
  function _ticketCmdLabel(command) {
    if (!command) return "TKT";
    var c = String(command).toLowerCase();
    if (c === "implement") return "IMP";
    if (c === "research") return "RSC";
    if (c === "review") return "REV";
    return "TKT";
  }

  /**
   * workdir 경로의 `runs/YYYYMMDD-HHMMSS/...` 패턴에서 타임스탬프를 추출한다.
   * 실패 시 null.
   *
   * @param {string|undefined} workdir
   * @returns {string|null}
   */
  function _extractTicketDate(workdir) {
    if (!workdir) return null;
    var m = String(workdir).match(/runs\/(\d{8})-(\d{6})/);
    if (!m) return null;
    var ymd = m[1]; // YYYYMMDD
    var hms = m[2]; // HHMMSS
    var year = parseInt(ymd.slice(0, 4), 10);
    var month = parseInt(ymd.slice(4, 6), 10);
    var day = parseInt(ymd.slice(6, 8), 10);
    var hour = parseInt(hms.slice(0, 2), 10);
    var minute = parseInt(hms.slice(2, 4), 10);
    if (!year || !month || !day) return null;
    var ampm = hour < 12 ? "오전" : "오후";
    var hour12 = hour % 12;
    if (hour12 === 0) hour12 = 12;
    return year + "년 " + month + "월 " + day + "일 / " + ampm + " " + hour12 + "시 " + minute + "분";
  }

  /**
   * att 객체로부터 subtitle 문자열을 계산한다.
   *
   * subtitle 우선순위:
   * 1. att.subtitle 명시 값 (외부에서 직접 전달 시)
   * 2. att.result.workdir 에서 날짜 추출
   * 3. att.report 줄 수
   * 4. "no report"
   *
   * @param {object} att
   * @returns {string}
   */
  function _resolveSubtitle(att) {
    if (att.subtitle) return att.subtitle;
    var workdir = att.result && att.result.workdir;
    if (workdir) {
      var dateStr = _extractTicketDate(workdir);
      if (dateStr) return dateStr;
    }
    if (att.report) {
      var lineCount = String(att.report).split(/\r?\n/).length;
      return "report " + lineCount + "줄";
    }
    return "no report";
  }

  /**
   * 첨부 티켓 카드 DOM 엘리먼트를 생성하여 반환한다.
   *
   * 생성된 카드는 `.terminal-ticket-card` 클래스를 사용한다.
   * remove 버튼은 포함하지 않는다 — 입력 측 프리뷰에서는 M.renderTicketPreview 가
   * 별도로 remove 버튼을 붙이며, 메시지 렌더 측은 remove 버튼이 없어야 한다.
   *
   * @param {object} att - {number, command, title, prompt?, report?, result?, subtitle?}
   * @returns {HTMLElement} .terminal-ticket-card div
   */
  function create(att) {
    att = att || {};

    var card = document.createElement("div");
    card.className = "terminal-ticket-card";
    if (att.number) {
      card.setAttribute("data-ticket-number", att.number);
    }

    // Command badge (RSC / IMP / REV / TKT)
    var cmdLabel = _ticketCmdLabel(att.command);
    var cmdEl = document.createElement("div");
    cmdEl.className = "terminal-ticket-card-cmd";
    cmdEl.textContent = cmdLabel;

    // Body: title + subtitle
    var bodyEl = document.createElement("div");
    bodyEl.className = "terminal-ticket-card-body";

    var titleEl = document.createElement("div");
    titleEl.className = "terminal-ticket-card-title";
    var numStr = att.number || "T-???";
    var titleText = (att.title || "").trim();
    titleEl.textContent = titleText ? (numStr + " " + titleText) : numStr;
    titleEl.title = titleEl.textContent;

    var subtitleEl = document.createElement("div");
    // layout-and-message.css 의 실제 정의 클래스명 사용 (.terminal-ticket-card-sub)
    subtitleEl.className = "terminal-ticket-card-sub";
    var subtitle = _resolveSubtitle(att);
    subtitleEl.textContent = subtitle;
    subtitleEl.title = subtitle;

    bodyEl.appendChild(titleEl);
    bodyEl.appendChild(subtitleEl);

    card.appendChild(cmdEl);
    card.appendChild(bodyEl);

    return card;
  }

  // ── 모듈 노출 ──
  M.attachmentCard = {
    create: create,
    // 내부 헬퍼도 테스트 편의상 노출
    _ticketCmdLabel: _ticketCmdLabel,
    _extractTicketDate: _extractTicketDate,
    _resolveSubtitle: _resolveSubtitle
  };

})();

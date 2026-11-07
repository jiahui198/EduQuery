/* =========================================================
   知问 EduQuery · 前端逻辑
   纯原生 JS，无构建步骤。接口全部来自 /api/v1
   ========================================================= */
(function () {
  "use strict";

  /* ---------- 配置 ---------- */
  const API_BASE =
    location.protocol === "file:" ? "http://127.0.0.1:8000/api/v1" : "/api/v1";

  const TOKEN_KEY = { student: "eduquery.student.token", admin: "eduquery.admin.token" };

  const STATUS_LABEL = {
    ready: "已就绪",
    processing: "处理中",
    pending: "排队中",
    failed: "失败",
  };

  const SUGGESTIONS = [
    "图书馆的开馆时间是几点？",
    "国家奖学金的申请条件是什么？",
    "转专业需要走哪些流程？",
    "毕业设计的学分要求是多少？",
  ];

  /* ---------- 状态 ---------- */
  const state = {
    token: localStorage.getItem(TOKEN_KEY.student) || "",
    adminToken: localStorage.getItem(TOKEN_KEY.admin) || "",
    user: null,
    admin: null,
    conversations: [],
    currentConvId: null,
    streaming: false,
    abort: null,
    docPage: 1,
    docSize: 10,
    docTotal: 0,
    docStatus: "",
    docCategory: "",
  };

  /* ---------- DOM 小工具 ---------- */
  const $ = (id) => document.getElementById(id);
  const el = (sel, root) => (root || document).querySelector(sel);
  const els = (sel, root) => Array.prototype.slice.call((root || document).querySelectorAll(sel));

  const ESC_MAP = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
  const esc = (v) => String(v == null ? "" : v).replace(/[&<>"']/g, (c) => ESC_MAP[c]);

  function safeUrl(u) {
    if (!u) return "";
    const s = String(u).trim();
    return /^https?:\/\//i.test(s) ? esc(s) : "";
  }

  function toast(message, kind) {
    const host = $("toast-host");
    if (!host) return;
    const node = document.createElement("div");
    node.className = "toast" + (kind ? " is-" + kind : "");
    node.textContent = message;
    host.appendChild(node);
    setTimeout(() => {
      node.style.transition = "opacity .25s ease, transform .25s ease";
      node.style.opacity = "0";
      node.style.transform = "translateY(-8px)";
      setTimeout(() => node.remove(), 260);
    }, 3200);
  }

  /* ---------- 时间格式 ---------- */
  function parseTime(raw) {
    if (!raw) return null;
    const normalized = String(raw).includes("T") ? raw : String(raw).replace(" ", "T");
    const d = new Date(normalized);
    return isNaN(d.getTime()) ? null : d;
  }
  function pad(n) {
    return n < 10 ? "0" + n : String(n);
  }
  function fmtTime(raw) {
    const d = parseTime(raw);
    if (!d) return "";
    return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
  }
  function dayKey(raw) {
    const d = parseTime(raw);
    if (!d) return "更早";
    const now = new Date();
    const startOf = (x) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
    const diff = Math.round((startOf(now) - startOf(d)) / 86400000);
    if (diff <= 0) return "今天";
    if (diff === 1) return "昨天";
    if (diff <= 7) return "最近 7 天";
    return "更早";
  }

  /* ---------- HTTP ---------- */
  async function request(path, opts) {
    opts = opts || {};
    const headers = {};
    const token = opts.token !== undefined ? opts.token : state.token;
    if (token) headers.Authorization = "Bearer " + token;

    let payload;
    if (opts.form) {
      payload = opts.form;
    } else if (opts.body !== undefined) {
      headers["Content-Type"] = "application/json";
      payload = JSON.stringify(opts.body);
    }

    const res = await fetch(API_BASE + path, {
      method: opts.method || "GET",
      headers: headers,
      body: payload,
      signal: opts.signal,
    });

    const raw = await res.text();
    let data = null;
    if (raw) {
      try {
        data = JSON.parse(raw);
      } catch (e) {
        data = raw;
      }
    }

    if (!res.ok) {
      const err = new Error((data && data.message) || "请求失败（HTTP " + res.status + "）");
      err.status = res.status;
      err.code = data && data.code;
      throw err;
    }
    return data;
  }

  /* ---------- 视图切换 ---------- */
  function showView(name) {
    $("view-auth").hidden = name !== "auth";
    $("view-chat").hidden = name !== "chat";
    $("view-admin").hidden = name !== "admin";
  }

  /* ---------- 健康检查 ---------- */
  async function checkHealth() {
    const dot = $("health-dot");
    const text = $("health-text");
    try {
      const data = await request("/health", { token: "" });
      if (dot) dot.className = "health-dot is-ok";
      if (text) text.textContent = "后端服务正常 · " + (data && data.env ? data.env : "dev");
      setConnChip(true);
    } catch (e) {
      if (dot) dot.className = "health-dot is-bad";
      if (text) text.textContent = "连不上后端服务（请确认 uvicorn 已启动）";
      setConnChip(false);
    }
  }

  function setConnChip(ok) {
    const chip = $("conn-chip");
    if (!chip) return;
    chip.className = "chip" + (ok ? "" : " is-bad");
    chip.innerHTML =
      '<span class="health-dot ' + (ok ? "is-ok" : "is-bad") + '"></span>' + (ok ? "已连接" : "未连接");
  }

  /* =========================================================
     认证
     ========================================================= */
  function switchAuthTab(name) {
    els(".tab").forEach((t) => t.classList.toggle("is-active", t.dataset.tab === name));
    els(".auth-form").forEach((f) => {
      f.hidden = f.dataset.panel !== name;
    });
  }

  async function studentLogin(payload) {
    const data = await request("/auth/login", { method: "POST", body: payload, token: "" });
    state.token = data.access_token;
    localStorage.setItem(TOKEN_KEY.student, state.token);
    await loadStudentMe();
    await enterChat();
  }

  async function loadStudentMe() {
    state.user = await request("/auth/me");
  }

  async function enterChat() {
    const u = state.user || {};
    const name = u.nickname || u.student_no || "同学";
    $("user-name").textContent = name;
    $("user-sub").textContent = [u.student_no, u.major].filter(Boolean).join(" · ") || "学生";
    $("user-avatar").textContent = String(name).slice(0, 1);
    showView("chat");
    resetConversationView();
    await loadConversations();
  }

  function logoutStudent() {
    state.token = "";
    state.user = null;
    state.conversations = [];
    state.currentConvId = null;
    localStorage.removeItem(TOKEN_KEY.student);
    showView("auth");
    switchAuthTab("student-login");
  }

  /* =========================================================
     会话
     ========================================================= */
  function resetConversationView() {
    state.currentConvId = null;
    $("conv-title").textContent = "新的对话";
    $("conv-meta").textContent = "提问后答案会标注参考来源";
    $("btn-del-conv").hidden = true;
    els(".conv-row").forEach((r) => r.classList.remove("is-active"));
    renderEmptyState();
    const q = $("question");
    if (q) {
      q.value = "";
      autoGrow(q);
      q.focus();
    }
  }

  async function loadConversations() {
    try {
      const rows = await request("/conversations?limit=50&offset=0");
      state.conversations = rows || [];
      renderConversationList();
    } catch (e) {
      if (e.status === 401) return logoutStudent();
      toast(e.message, "err");
    }
  }

  function renderConversationList() {
    const host = $("conv-list");
    host.innerHTML = "";
    if (!state.conversations.length) {
      host.innerHTML = '<p class="conv-group" style="text-transform:none;letter-spacing:0">还没有历史对话</p>';
      return;
    }

    let lastGroup = "";
    state.conversations.forEach((c) => {
      const group = dayKey(c.updated_at || c.created_at);
      if (group !== lastGroup) {
        lastGroup = group;
        const g = document.createElement("div");
        g.className = "conv-group";
        g.textContent = group;
        host.appendChild(g);
      }

      const row = document.createElement("div");
      row.className = "conv-row" + (c.id === state.currentConvId ? " is-active" : "");
      row.dataset.id = String(c.id);

      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "conv";
      btn.innerHTML =
        '<div class="conv-title">' +
        esc(c.title || "未命名对话") +
        '</div><div class="conv-time">' +
        esc(fmtTime(c.updated_at || c.created_at)) +
        "</div>";
      btn.addEventListener("click", () => openConversation(c.id));

      const del = document.createElement("button");
      del.type = "button";
      del.className = "conv-del";
      del.title = "删除会话";
      del.setAttribute("aria-label", "删除会话 " + (c.title || ""));
      del.textContent = "×";
      del.addEventListener("click", (ev) => {
        ev.stopPropagation();
        removeConversation(c.id);
      });

      row.appendChild(btn);
      row.appendChild(del);
      host.appendChild(row);
    });
  }

  function highlightConversation(id) {
    els(".conv-row").forEach((r) => r.classList.toggle("is-active", Number(r.dataset.id) === Number(id)));
  }

  async function openConversation(id) {
    if (state.streaming) {
      toast("正在生成回答，请稍候再切换", "warn");
      return;
    }
    try {
      const detail = await request("/conversations/" + id);
      state.currentConvId = detail.id;
      $("conv-title").textContent = detail.title || "未命名对话";
      $("conv-meta").textContent =
        "创建于 " + fmtTime(detail.created_at) + " · " + (detail.messages || []).length + " 条消息";
      $("btn-del-conv").hidden = false;
      highlightConversation(detail.id);
      renderMessages(detail.messages || []);
    } catch (e) {
      if (e.status === 401) return logoutStudent();
      toast(e.message, "err");
    }
  }

  async function removeConversation(id) {
    if (!confirm("删除这个会话？会话里的消息会一起删掉，且不能恢复。")) return;
    try {
      await request("/conversations/" + id, { method: "DELETE" });
      if (Number(state.currentConvId) === Number(id)) resetConversationView();
      await loadConversations();
      toast("会话已删除", "ok");
    } catch (e) {
      toast(e.message, "err");
    }
  }

  /* =========================================================
     消息渲染
     ========================================================= */
  function renderEmptyState() {
    const host = $("messages");
    host.innerHTML =
      '<div class="empty-state">' +
      '<div class="empty-mark">问</div>' +
      "<h2>今天想问点什么？</h2>" +
      "<p>答案只取自校内文档，每条结论都会标注出处。</p>" +
      '<div class="suggestions">' +
      SUGGESTIONS.map((s) => '<button type="button" class="suggestion">' + esc(s) + "</button>").join("") +
      "</div></div>";
    els(".suggestion", host).forEach((b) => {
      b.addEventListener("click", () => {
        const q = $("question");
        q.value = b.textContent;
        autoGrow(q);
        q.focus();
      });
    });
  }

  function richText(text) {
    const safe = esc(text);
    return safe
      .split(/\n{2,}/)
      .map((par) => par.trim())
      .filter(Boolean)
      .map((par) => {
        const withCite = par.replace(/\[(\d{1,2})\]/g, function (m, n) {
          return '<sup class="cite" data-idx="' + n + '">' + n + "</sup>";
        });
        return "<p>" + withCite.replace(/\n/g, "<br>") + "</p>";
      })
      .join("");
  }

  function sourcesHTML(sources) {
    if (!sources || !sources.length) return "";
    const items = sources
      .map((s) => {
        const url = safeUrl(s.source_url);
        const title = url ? '<a href="' + url + '" target="_blank" rel="noopener">' + esc(s.title) + "</a>" : esc(s.title);
        const score = typeof s.score === "number" ? s.score.toFixed(3) : esc(s.score);
        return (
          '<li class="source" data-idx="' + esc(s.index) + '">' +
          '<span class="source-idx">' + esc(s.index) + "</span>" +
          '<div class="source-main">' +
          '<div class="source-title">' + title + "</div>" +
          '<div class="source-meta">相关度 ' + score + "</div>" +
          "</div></li>"
        );
      })
      .join("");
    return (
      '<div class="sources"><div class="sources-title">参考来源 ' + sources.length + "</div>" +
      '<ol class="source-list">' + items + "</ol></div>"
    );
  }

  function messageHTML(m) {
    if (m.role === "user") {
      return '<div class="msg user"><div class="msg-body"><div class="bubble">' + esc(m.content) + "</div></div></div>";
    }
    return (
      '<div class="msg assistant"><div class="avatar">知</div><div class="msg-body">' +
      '<div class="msg-text">' + richText(m.content || "") + "</div>" +
      sourcesHTML(m.citations) +
      "</div></div>"
    );
  }

  function renderMessages(list) {
    const host = $("messages");
    if (!list.length) return renderEmptyState();
    host.innerHTML = list.map(messageHTML).join("");
    bindCitations(host);
    scrollToBottom(true);
  }

  function bindCitations(root) {
    els(".cite", root).forEach((node) => {
      node.addEventListener("click", () => {
        const target = el('.source[data-idx="' + node.dataset.idx + '"]', node.closest(".msg"));
        if (!target) return;
        target.classList.add("is-flash");
        target.scrollIntoView({ block: "nearest", behavior: "smooth" });
        setTimeout(() => target.classList.remove("is-flash"), 1200);
      });
    });
  }

  function appendNode(html) {
    const host = $("messages");
    const empty = el(".empty-state", host);
    if (empty) empty.remove();
    const wrap = document.createElement("div");
    wrap.innerHTML = html;
    const node = wrap.firstElementChild;
    host.appendChild(node);
    scrollToBottom(true);
    return node;
  }

  function scrollToBottom(force) {
    const host = $("messages");
    if (!host) return;
    const nearBottom = host.scrollHeight - host.scrollTop - host.clientHeight < 160;
    if (force || nearBottom) host.scrollTop = host.scrollHeight;
  }

  /* =========================================================
     提问 / 流式回答
     ========================================================= */
  async function ask(question) {
    if (!question || !question.trim()) return;
    if (state.streaming) return;

    const text = question.trim().slice(0, 1000);
    appendNode('<div class="msg user"><div class="msg-body"><div class="bubble">' + esc(text) + "</div></div></div>");

    const box = appendNode(
      '<div class="msg assistant"><div class="avatar">知</div><div class="msg-body">' +
        '<div class="msg-text"><span class="pending-text">正在检索知识库…</span></div>' +
        "</div></div>"
    );
    const textEl = el(".msg-text", box);

    setStreaming(true);
    state.abort = new AbortController();

    let answer = "";
    let sources = [];
    let failed = false;

    try {
      const res = await fetch(API_BASE + "/chat/ask/stream", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: "Bearer " + state.token,
        },
        body: JSON.stringify({
          question: text,
          conversation_id: state.currentConvId,
        }),
        signal: state.abort.signal,
      });

      if (!res.ok) {
        const raw = await res.text();
        let msg = "请求失败（HTTP " + res.status + "）";
        try {
          const d = JSON.parse(raw);
          msg = d.message || msg;
        } catch (e) {}
        if (res.status === 401) {
          logoutStudent();
        }
        throw new Error(msg);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";

      while (true) {
        const chunk = await reader.read();
        if (chunk.done) break;
        buffer += decoder.decode(chunk.value, { stream: true });

        let cut;
        while ((cut = buffer.indexOf("\n\n")) >= 0) {
          const block = buffer.slice(0, cut);
          buffer = buffer.slice(cut + 2);
          if (!block.trim()) continue;

          const parsed = parseEvent(block);
          if (!parsed) continue;

          if (parsed.event === "meta") {
            if (parsed.data && parsed.data.conversation_id) {
              state.currentConvId = parsed.data.conversation_id;
              $("btn-del-conv").hidden = false;
              highlightConversation(state.currentConvId);
            }
          } else if (parsed.event === "sources") {
            sources = (parsed.data && parsed.data.sources) || [];
            const holder = el(".sources", box);
            if (holder) holder.remove();
            if (sources.length) {
              el(".msg-body", box).insertAdjacentHTML("beforeend", sourcesHTML(sources));
              bindCitations(box);
            }
          } else if (parsed.event === "answer") {
            answer += (parsed.data && parsed.data.text) || "";
            paintAnswer(textEl, answer, true);
            scrollToBottom();
          } else if (parsed.event === "error") {
            failed = true;
            showError(box, (parsed.data && parsed.data.message) || "AI 服务暂时不可用");
          } else if (parsed.event === "done") {
            /* 结束标记，循环外统一收尾 */
          }
        }
      }
    } catch (e) {
      if (e.name === "AbortError") {
        failed = true;
        showError(box, "已停止生成");
      } else {
        failed = true;
        showError(box, e.message || "网络异常，请重试");
      }
    } finally {
      setStreaming(false);
      state.abort = null;

      if (!failed) {
        if (!answer) {
          textEl.innerHTML = '<span class="pending-text">没有返回内容</span>';
        } else {
          paintAnswer(textEl, answer, false);
        }
      } else if (answer) {
        paintAnswer(textEl, answer, false);
      } else {
        textEl.innerHTML = "";
      }

      if (!failed && sources.length) {
        toast("回答完成，含 " + sources.length + " 条引用来源", "ok");
      }
      await refreshAfterAsk();
    }
  }

  function parseEvent(block) {
    let event = "message";
    let data = null;
    block.split(/\r?\n/).forEach((line) => {
      if (line.startsWith("event:")) {
        event = line.slice(6).trim();
      } else if (line.startsWith("data:")) {
        const raw = line.slice(5).trim();
        try {
          data = JSON.parse(raw);
        } catch (e) {
          data = raw;
        }
      }
    });
    return { event: event, data: data };
  }

  function paintAnswer(target, text, streaming) {
    target.innerHTML = richText(text) + (streaming ? '<span class="caret"></span>' : "");
    bindCitations(target.closest(".msg"));
  }

  function showError(box, message) {
    const body = el(".msg-body", box);
    if (!body) return;
    const old = el(".msg-error", body);
    if (old) old.remove();
    body.insertAdjacentHTML(
      "beforeend",
      '<div class="msg-error">⚠ ' + esc(message) + "</div>"
    );
  }

  async function refreshAfterAsk() {
    await loadConversations();
    if (state.currentConvId) {
      const current = state.conversations.find((c) => Number(c.id) === Number(state.currentConvId));
      if (current) {
        $("conv-title").textContent = current.title || "新的对话";
        $("conv-meta").textContent = "更新于 " + fmtTime(current.updated_at);
        highlightConversation(current.id);
      }
    }
  }

  function setStreaming(on) {
    state.streaming = on;
    $("btn-send").disabled = on;
    $("btn-send").textContent = on ? "生成中…" : "发送";
    $("btn-stop").hidden = !on;
    $("question").disabled = on;
    const people = els(".suggestion");
    people.forEach((b) => (b.disabled = on));
  }

  function autoGrow(ta) {
    ta.style.height = "auto";
    ta.style.height = Math.min(ta.scrollHeight, 180) + "px";
  }

  /* =========================================================
     管理端
     ========================================================= */
  async function enterAdmin() {
    showView("admin");
    $("admin-gate").hidden = true;
    $("admin-console").hidden = true;

    if (!state.adminToken) {
      $("admin-gate").hidden = false;
      return;
    }
    try {
      state.admin = await request("/auth/admin/me", { token: state.adminToken });
      openConsole();
    } catch (e) {
      state.adminToken = "";
      localStorage.removeItem(TOKEN_KEY.admin);
      $("admin-gate").hidden = false;
    }
  }

  function openConsole() {
    $("admin-gate").hidden = true;
    $("admin-console").hidden = false;
    $("admin-who").textContent = state.admin ? state.admin.username : "管理员";
    loadAdminStats();
    loadDocs();
  }

  async function loadAdminStats() {
    const fetchTotal = (status) =>
      request("/admin/docs?page=1&size=1" + (status ? "&status=" + status : ""), {
        token: state.adminToken,
      })
        .then((d) => (d && typeof d.total === "number" ? d.total : 0))
        .catch(() => null);

    const [total, ready, processing, failed] = await Promise.all([
      fetchTotal(""),
      fetchTotal("ready"),
      fetchTotal("processing"),
      fetchTotal("failed"),
    ]);
    const set = (id, v) => ($(id).textContent = v === null ? "—" : String(v));
    set("stat-total", total);
    set("stat-ready", ready);
    set("stat-processing", processing);
    set("stat-failed", failed);
  }

  async function loadDocs() {
    const qs = new URLSearchParams();
    qs.set("page", String(state.docPage));
    qs.set("size", String(state.docSize));
    if (state.docStatus) qs.set("status", state.docStatus);
    if (state.docCategory) qs.set("category", state.docCategory);

    const tbody = $("doc-tbody");
    tbody.innerHTML = '<tr><td colspan="7" class="empty-row">加载中…</td></tr>';

    try {
      const data = await request("/admin/docs?" + qs.toString(), { token: state.adminToken });
      state.docTotal = data.total || 0;
      renderDocs(data.items || []);
    } catch (e) {
      if (e.status === 401 || e.status === 403) {
        state.adminToken = "";
        localStorage.removeItem(TOKEN_KEY.admin);
        $("admin-console").hidden = true;
        $("admin-gate").hidden = false;
        toast("管理员登录已失效，请重新登录", "warn");
        return;
      }
      tbody.innerHTML = "";
      toast(e.message, "err");
    }
  }

  function renderDocs(items) {
    const tbody = $("doc-tbody");
    const empty = $("docs-empty");

    if (!items.length) {
      tbody.innerHTML = "";
      empty.hidden = false;
    } else {
      empty.hidden = true;
      tbody.innerHTML = items
        .map((d) => {
          const status = STATUS_LABEL[d.status] || d.status || "未知";
          const source =
            d.source_type === "url" && d.source_url
              ? '<span class="tag-mono">' + esc(d.source_url) + "</span>"
              : d.file_path
              ? '<span class="tag-mono">' + esc(String(d.file_path).split(/[\\/]/).pop()) + "</span>"
              : '<span class="tag-mono">—</span>';
          const err = d.status === "failed" && d.error_msg ? '<div class="doc-err">' + esc(d.error_msg) + "</div>" : "";
          return (
            "<tr>" +
            '<td><div class="doc-title" title="' + esc(d.title) + '">' + esc(d.title) + "</div>" + err + "</td>" +
            "<td>" + (d.category ? '<span class="tag">' + esc(d.category) + "</span>" : '<span class="tag-mono">—</span>') + "</td>" +
            "<td>" + source + "</td>" +
            '<td><span class="badge ' + esc(d.status) + '">' + esc(status) + "</span></td>" +
            '<td class="num">' + esc(d.chunk_count) + "</td>" +
            "<td>" + esc(fmtTime(d.updated_at || d.created_at)) + "</td>" +
            '<td class="num"><button class="btn btn-danger btn-sm" data-del="' + esc(d.id) + '">删除</button></td>' +
            "</tr>"
          );
        })
        .join("");

      els("[data-del]", tbody).forEach((btn) => {
        btn.addEventListener("click", () => removeDoc(Number(btn.dataset.del)));
      });
    }

    const pages = Math.max(1, Math.ceil(state.docTotal / state.docSize));
    $("docs-summary").textContent = "共 " + state.docTotal + " 篇文档";
    $("pager-info").textContent =
      "第 " + state.docPage + " / " + pages + " 页 · 每页 " + state.docSize + " 篇";
    $("btn-prev").disabled = state.docPage <= 1;
    $("btn-next").disabled = state.docPage >= pages;
  }

  async function removeDoc(id) {
    if (!confirm("删除这篇文档？切片和向量会一起删掉。")) return;
    try {
      await request("/admin/docs/" + id, { method: "DELETE", token: state.adminToken });
      toast("文档已删除", "ok");
      if (state.docPage > 1 && state.docTotal - 1 <= (state.docPage - 1) * state.docSize) {
        state.docPage -= 1;
      }
      await Promise.all([loadDocs(), loadAdminStats()]);
    } catch (e) {
      toast(e.message, "err");
    }
  }

  function setResult(node, html, kind) {
    node.hidden = false;
    node.className = "result" + (kind ? " is-" + kind : "");
    node.innerHTML = html;
  }

  /* =========================================================
     事件绑定
     ========================================================= */
  function bindEvents() {
    /* 认证 tab */
    els(".tab").forEach((tab) => tab.addEventListener("click", () => switchAuthTab(tab.dataset.tab)));
    els("[data-goto-tab]").forEach((a) =>
      a.addEventListener("click", (e) => {
        e.preventDefault();
        switchAuthTab(a.dataset.gotoTab);
      })
    );

    /* 学生登录 */
    $("form-student-login").addEventListener("submit", async (e) => {
      e.preventDefault();
      const f = e.target;
      const btn = el('button[type="submit"]', f);
      btn.disabled = true;
      try {
        await studentLogin({
          student_no: f.student_no.value.trim(),
          password: f.password.value,
        });
        toast("欢迎回来", "ok");
      } catch (err) {
        toast(err.message, "err");
      } finally {
        btn.disabled = false;
      }
    });

    /* 学生注册 */
    $("form-student-register").addEventListener("submit", async (e) => {
      e.preventDefault();
      const f = e.target;
      const btn = el('button[type="submit"]', f);
      const payload = {
        student_no: f.student_no.value.trim(),
        password: f.password.value,
        nickname: f.nickname.value.trim() || null,
        major: f.major.value.trim() || null,
      };
      if (payload.student_no.length < 4) return toast("学号至少 4 位", "warn");
      if (payload.password.length < 6) return toast("密码至少 6 位", "warn");
      btn.disabled = true;
      try {
        await request("/auth/register", { method: "POST", body: payload, token: "" });
        await studentLogin({ student_no: payload.student_no, password: payload.password });
        toast("注册成功，已自动登录", "ok");
      } catch (err) {
        toast(err.message, "err");
      } finally {
        btn.disabled = false;
      }
    });

    /* 管理员登录（首页） */
    $("form-admin-login").addEventListener("submit", async (e) => {
      e.preventDefault();
      const f = e.target;
      const btn = el('button[type="submit"]', f);
      btn.disabled = true;
      try {
        const data = await request("/auth/admin/login", {
          method: "POST",
          body: { username: f.username.value.trim(), password: f.password.value },
          token: "",
        });
        state.adminToken = data.access_token;
        localStorage.setItem(TOKEN_KEY.admin, state.adminToken);
        state.admin = await request("/auth/admin/me", { token: state.adminToken });
        showView("admin");
        openConsole();
        toast("已进入管理后台", "ok");
      } catch (err) {
        toast(err.message, "err");
      } finally {
        btn.disabled = false;
      }
    });

    /* 管理员登录（闸门） */
    $("form-admin-gate").addEventListener("submit", async (e) => {
      e.preventDefault();
      const f = e.target;
      const btn = el('button[type="submit"]', f);
      btn.disabled = true;
      try {
        const data = await request("/auth/admin/login", {
          method: "POST",
          body: { username: f.username.value.trim(), password: f.password.value },
          token: "",
        });
        state.adminToken = data.access_token;
        localStorage.setItem(TOKEN_KEY.admin, state.adminToken);
        state.admin = await request("/auth/admin/me", { token: state.adminToken });
        openConsole();
        toast("已进入管理后台", "ok");
      } catch (err) {
        toast(err.message, "err");
      } finally {
        btn.disabled = false;
      }
    });

    /* 学生端侧栏 */
    $("btn-new-conv").addEventListener("click", () => resetConversationView());
    $("btn-logout").addEventListener("click", logoutStudent);
    $("btn-admin-entry").addEventListener("click", enterAdmin);

    $("btn-del-conv").addEventListener("click", () => {
      if (state.currentConvId) removeConversation(state.currentConvId);
    });

    /* 提问 */
    $("composer").addEventListener("submit", (e) => {
      e.preventDefault();
      const q = $("question");
      const value = q.value;
      if (!value.trim() || state.streaming) return;
      q.value = "";
      autoGrow(q);
      ask(value);
    });

    const qa = $("question");
    qa.setAttribute("maxlength", "1000");
    qa.addEventListener("input", () => autoGrow(qa));
    qa.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
        e.preventDefault();
        $("composer").dispatchEvent(new Event("submit", { cancelable: true }));
      }
    });

    $("btn-stop").addEventListener("click", () => {
      if (state.abort) state.abort.abort();
    });

    /* 管理端 */
    $("btn-to-chat").addEventListener("click", () => {
      if (state.token) showView("chat");
      else {
        showView("auth");
        switchAuthTab("student-login");
      }
    });

    $("btn-admin-logout").addEventListener("click", () => {
      state.adminToken = "";
      state.admin = null;
      localStorage.removeItem(TOKEN_KEY.admin);
      $("admin-console").hidden = true;
      $("admin-gate").hidden = false;
    });

    /* 上传 */
    const fileInput = $("file-input");
    const dropzone = $("dropzone");
    let pickedFile = null;

    function setPickedFile(file) {
      pickedFile = file || null;
      dropzone.classList.toggle("has-file", !!pickedFile);
      $("dropzone-text").textContent = pickedFile
        ? pickedFile.name + " · " + (pickedFile.size / 1024 / 1024).toFixed(2) + " MB"
        : "点击选择文件，或拖拽到这里";
    }

    // label 本身就会触发内部 input，这里不要再手动 click，否则会弹两次文件框
    fileInput.addEventListener("change", () => setPickedFile(fileInput.files[0]));
    ["dragenter", "dragover"].forEach((ev) =>
      dropzone.addEventListener(ev, (e) => {
        e.preventDefault();
        dropzone.classList.add("is-drag");
      })
    );
    ["dragleave", "drop"].forEach((ev) =>
      dropzone.addEventListener(ev, (e) => {
        e.preventDefault();
        dropzone.classList.remove("is-drag");
      })
    );
    dropzone.addEventListener("drop", (e) => {
      const file = e.dataTransfer && e.dataTransfer.files[0];
      if (file) setPickedFile(file);
    });

    $("form-upload").addEventListener("submit", async (e) => {
      e.preventDefault();
      const f = e.target;
      const box = $("upload-result");
      if (!pickedFile) return toast("先选一个文件", "warn");

      const fd = new FormData();
      fd.append("file", pickedFile);
      if (f.title.value.trim()) fd.append("title", f.title.value.trim());
      if (f.category.value.trim()) fd.append("category", f.category.value.trim());

      const btn = el('button[type="submit"]', f);
      btn.disabled = true;
      setResult(box, "上传并解析中，请稍候…", "");
      try {
        const r = await request("/admin/docs/upload", {
          method: "POST",
          form: fd,
          token: state.adminToken,
        });
        setResult(
          box,
          "入库成功：<b>" + esc(r.title || "文档") + "</b><br>文档 ID " + esc(r.doc_id) +
            " · 生成 " + esc(r.chunks) + " 个切片",
          "ok"
        );
        f.reset();
        setPickedFile(null);
        await Promise.all([loadDocs(), loadAdminStats()]);
      } catch (err) {
        setResult(box, esc(err.message), "err");
      } finally {
        btn.disabled = false;
      }
    });

    /* 网页入库 */
    $("form-url").addEventListener("submit", async (e) => {
      e.preventDefault();
      const f = e.target;
      const box = $("url-result");
      const btn = el('button[type="submit"]', f);
      btn.disabled = true;
      setResult(box, "抓取正文并切分入库中…", "");
      try {
        const r = await request("/admin/docs/url", {
          method: "POST",
          body: {
            url: f.url.value.trim(),
            category: f.category.value.trim() || null,
            force: f.force.checked,
          },
          token: state.adminToken,
        });
        setResult(
          box,
          (r.skipped ? "该网页已入库，已跳过。<br>" : "入库成功：<br>") +
            "文档 ID " + esc(r.doc_id) + " · 生成 " + esc(r.chunks) + " 个切片" +
            (r.title ? "<br>标题：" + esc(r.title) : ""),
          r.skipped ? "" : "ok"
        );
        f.reset();
        await Promise.all([loadDocs(), loadAdminStats()]);
      } catch (err) {
        setResult(box, esc(err.message), "err");
      } finally {
        btn.disabled = false;
      }
    });

    /* 栏目批量抓取 */
    $("form-crawl").addEventListener("submit", async (e) => {
      e.preventDefault();
      const f = e.target;
      const box = $("crawl-result");
      const btn = el('button[type="submit"]', f);
      btn.disabled = true;
      setResult(box, "正在发现栏目下的文章链接…", "");
      try {
        const r = await request("/admin/docs/crawl", {
          method: "POST",
          body: {
            list_url: f.list_url.value.trim(),
            limit: Number(f.limit.value) || 20,
            category: f.category.value.trim() || null,
            force: f.force.checked,
          },
          token: state.adminToken,
        });
        const urls = (r.urls || [])
          .slice(0, 5)
          .map((u) => "<li>" + esc(u) + "</li>")
          .join("");
        setResult(
          box,
          "已受理：" + esc(r.message) +
            "<br>发现 " + esc(r.discovered) + " 篇文章，后台逐篇入库中，可点「刷新」看进度。" +
            (urls ? "<ul>" + urls + (r.discovered > 5 ? "<li>…</li>" : "") + "</ul>" : ""),
          "ok"
        );
        f.reset();
        await loadAdminStats();
      } catch (err) {
        setResult(box, esc(err.message), "err");
      } finally {
        btn.disabled = false;
      }
    });

    /* 文档筛选 / 分页 */
    $("filter-status").addEventListener("change", (e) => {
      state.docStatus = e.target.value;
      state.docPage = 1;
      loadDocs();
    });

    let catTimer = null;
    $("filter-category").addEventListener("input", (e) => {
      clearTimeout(catTimer);
      catTimer = setTimeout(() => {
        state.docCategory = e.target.value.trim();
        state.docPage = 1;
        loadDocs();
      }, 320);
    });

    $("btn-refresh-docs").addEventListener("click", () => {
      loadDocs();
      loadAdminStats();
    });
    $("btn-prev").addEventListener("click", () => {
      if (state.docPage > 1) {
        state.docPage -= 1;
        loadDocs();
      }
    });
    $("btn-next").addEventListener("click", () => {
      const pages = Math.max(1, Math.ceil(state.docTotal / state.docSize));
      if (state.docPage < pages) {
        state.docPage += 1;
        loadDocs();
      }
    });
  }

  /* =========================================================
     启动
     ========================================================= */
  async function boot() {
    bindEvents();
    checkHealth();

    if (state.token) {
      try {
        await loadStudentMe();
        await enterChat();
        return;
      } catch (e) {
        state.token = "";
        localStorage.removeItem(TOKEN_KEY.student);
      }
    }

    if (state.adminToken) {
      try {
        state.admin = await request("/auth/admin/me", { token: state.adminToken });
        showView("admin");
        openConsole();
        return;
      } catch (e) {
        state.adminToken = "";
        localStorage.removeItem(TOKEN_KEY.admin);
      }
    }

    showView("auth");
    switchAuthTab("student-login");
  }

  document.addEventListener("DOMContentLoaded", boot);
})();

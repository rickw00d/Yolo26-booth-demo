// YOLO26 展示前端:輪詢統計、切換模式與語言、VLM 串流問答、小遊戲、效能對比
const $ = (id) => document.getElementById(id);
const post = (url, body) => fetch(url, {
  method: "POST", headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body || {}),
});

// ---------- 中英文字典 ----------
const I18N = {
  "zh-TW": {
    platform: "運算平台", multiPill: "2 個模型同時運行", privacyPill: "🛡 人臉已模糊",
    sec: "秒", gameTitle: "把這些東西拿到鏡頭前!", gameOver: "挑戰結束!", pts: "分",
    playAgain: "按 G 再玩一次", idleBig: "走近一點,讓 AI 認識你 👋",
    idleSub: "即時辨識 80 種物品 · 人體姿態 · 用中文跟 AI 對話", camWarn: "攝影機連線中…",
    latency: "推論延遲 ms", gpuUtil: "GPU 使用率", gpuMem: "GPU 記憶體", uniMem: "統一記憶體",
    faceBlur: "人臉模糊", on: "開啟", off: "關閉", faces: "張臉",
    uniquePeople: "累計辨識人次", uniqueTotal: "累計辨識物件", noObjects: "畫面中尚未偵測到物件",
    tabAsk: "AI 問答", tabVocab: "自由辨識", tabGame: "物品挑戰", tabBench: "效能對比",
    q1btn: "描述畫面", q2btn: "有幾個人?", q3btn: "我拿的是什麼?", q4btn: "幽默介紹我",
    q1: "請描述你現在看到的畫面", q2: "畫面裡有幾個人?他們在做什麼?",
    q3: "我手上拿的是什麼?可以用來做什麼?", q4: "用一句幽默的話介紹畫面中的人",
    askPh: "用中文問 AI 任何關於畫面的問題…", askBtn: "問",
    answerHint: "本機視覺語言模型會看著畫面回答你。",
    vlmModel: "視覺模型", vlmMissing: "(尚未下載!)", ollamaDown: "⚠ 無法連線 Ollama,AI 問答暫停",
    vocabHint: "輸入任何想找的東西(中文也可以),不用重新訓練模型,AI 立刻找給你看。",
    vocabPh: "例如:紅色杯子、眼鏡、識別證、耳機", vocabBtn: "找", vocabBusy: "AI 正在理解你的描述…",
    playerPh: "你的暱稱(選填)", gameStart: "開始挑戰", board: "🏆 今日排行榜",
    boardEmpty: "還沒有人挑戰,成為第一名吧!", guest: "來賓",
    resDetail: (r) => `${r.player}:找到 ${r.found}/${r.total} 個,用時 ${r.time} 秒`,
    benchHint: "同一張畫面、同一個模型,分別交給 CPU 與 GPU 運算。",
    benchStart: "開始比較", benchRunning: "測試中…", benchFail: "測試失敗",
    speedup: (x) => `GPU 快 ${x} 倍`,
    modes: { detect: "物件偵測", segment: "實例分割", pose: "人體姿態",
             multi: "多模型同時運行", openvocab: "自由辨識(開放詞彙)" },
    status: { starting: "啟動中", running: "運行中", loading: "載入模型", error: "錯誤" },
    temp: "溫度", camera: "攝影機", uptime: "已運行",
  },
  "zh-CN": {
    platform: "运算平台", multiPill: "2 个模型同时运行", privacyPill: "🛡 人脸已模糊",
    sec: "秒", gameTitle: "把这些东西拿到镜头前!", gameOver: "挑战结束!", pts: "分",
    playAgain: "按 G 再玩一次", idleBig: "走近一点,让 AI 认识你 👋",
    idleSub: "实时识别 80 种物品 · 人体姿态 · 用中文跟 AI 对话", camWarn: "摄像头连接中…",
    latency: "推理延迟 ms", gpuUtil: "GPU 使用率", gpuMem: "显存", uniMem: "统一内存",
    faceBlur: "人脸模糊", on: "开启", off: "关闭", faces: "张脸",
    uniquePeople: "累计识别人次", uniqueTotal: "累计识别物体", noObjects: "画面中尚未检测到物体",
    tabAsk: "AI 问答", tabVocab: "自由识别", tabGame: "物品挑战", tabBench: "性能对比",
    q1btn: "描述画面", q2btn: "有几个人?", q3btn: "我拿的是什么?", q4btn: "幽默介绍我",
    q1: "请描述你现在看到的画面", q2: "画面里有几个人?他们在做什么?",
    q3: "我手上拿的是什么?可以用来做什么?", q4: "用一句幽默的话介绍画面中的人",
    askPh: "用中文问 AI 任何关于画面的问题…", askBtn: "问",
    answerHint: "本机视觉语言模型会看着画面回答你。",
    vlmModel: "视觉模型", vlmMissing: "(尚未下载!)", ollamaDown: "⚠ 无法连接 Ollama,AI 问答暂停",
    vocabHint: "输入任何想找的东西(中文也可以),不用重新训练模型,AI 立刻找给你看。",
    vocabPh: "例如:红色杯子、眼镜、工作证、耳机", vocabBtn: "找", vocabBusy: "AI 正在理解你的描述…",
    playerPh: "你的昵称(选填)", gameStart: "开始挑战", board: "🏆 今日排行榜",
    boardEmpty: "还没有人挑战,成为第一名吧!", guest: "来宾",
    resDetail: (r) => `${r.player}:找到 ${r.found}/${r.total} 个,用时 ${r.time} 秒`,
    benchHint: "同一张画面、同一个模型,分别交给 CPU 与 GPU 运算。",
    benchStart: "开始比较", benchRunning: "测试中…", benchFail: "测试失败",
    speedup: (x) => `GPU 快 ${x} 倍`,
    modes: { detect: "目标检测", segment: "实例分割", pose: "人体姿态",
             multi: "多模型同时运行", openvocab: "自由识别(开放词汇)" },
    status: { starting: "启动中", running: "运行中", loading: "加载模型", error: "错误" },
    temp: "温度", camera: "摄像头", uptime: "已运行",
  },
  en: {
    platform: "Running on", multiPill: "2 models running together", privacyPill: "🛡 Faces blurred",
    sec: "s", gameTitle: "Show these items to the camera!", gameOver: "Time's up!", pts: "pts",
    playAgain: "Press G to play again", idleBig: "Step closer and meet the AI 👋",
    idleSub: "80 object classes · Human pose · Talk to the AI", camWarn: "Connecting camera…",
    latency: "Inference ms", gpuUtil: "GPU load", gpuMem: "GPU memory", uniMem: "Unified memory",
    faceBlur: "Face blur", on: "On", off: "Off", faces: "faces",
    uniquePeople: "People seen", uniqueTotal: "Objects seen", noObjects: "No objects detected yet",
    tabAsk: "Ask AI", tabVocab: "Find anything", tabGame: "Challenge", tabBench: "CPU vs GPU",
    q1btn: "Describe the scene", q2btn: "How many people?", q3btn: "What am I holding?", q4btn: "Roast me (nicely)",
    q1: "Describe what you see right now.", q2: "How many people are in the picture and what are they doing?",
    q3: "What am I holding and what is it used for?", q4: "Introduce the people in the picture with one funny line.",
    askPh: "Ask the AI anything about the scene…", askBtn: "Ask",
    answerHint: "An on-device vision-language model looks at the camera and answers you.",
    vlmModel: "Vision model", vlmMissing: " (not downloaded!)", ollamaDown: "⚠ Ollama not reachable — Ask AI paused",
    vocabHint: "Type anything you want to find. No retraining — the AI finds it instantly.",
    vocabPh: "e.g. red cup, glasses, badge, headphones", vocabBtn: "Find", vocabBusy: "The AI is reading your request…",
    playerPh: "Your nickname (optional)", gameStart: "Start", board: "🏆 Today's leaderboard",
    boardEmpty: "No one has played yet — be the first!", guest: "Guest",
    resDetail: (r) => `${r.player}: found ${r.found}/${r.total} in ${r.time}s`,
    benchHint: "Same frame, same model — once on the CPU, once on the GPU.",
    benchStart: "Run comparison", benchRunning: "Running…", benchFail: "Benchmark failed",
    speedup: (x) => `GPU is ${x}× faster`,
    modes: { detect: "Object detection", segment: "Segmentation", pose: "Human pose",
             multi: "Multi-model", openvocab: "Open vocabulary" },
    status: { starting: "Starting", running: "Running", loading: "Loading model", error: "Error" },
    temp: "Temp", camera: "Camera", uptime: "Uptime",
  },
};

const LANGS = ["zh-TW", "zh-CN", "en"];
const HTML_LANG = { "zh-TW": "zh-Hant-TW", "zh-CN": "zh-Hans-CN", en: "en" };
const TITLE_KEY = { "zh-TW": "", "zh-CN": "_zh_cn", en: "_en" };
let lang = "zh-TW";
let uiCfg = {};
let modes = [];
let idleSeconds = 15;
let currentMode = "";
let lastResultKey = null;
let typing = false;
let faceBlur = true;
let ollamaInfo = null;
let lastData = null;
const t = (k) => I18N[lang][k] ?? k;

// ---------- 語言 ----------
function applyLang(newLang) {
  lang = newLang;
  document.documentElement.lang = HTML_LANG[lang];
  document.querySelectorAll("[data-i18n]").forEach((el) => { el.textContent = t(el.dataset.i18n); });
  document.querySelectorAll("[data-i18n-ph]").forEach((el) => { el.placeholder = t(el.dataset.i18nPh); });
  document.querySelectorAll("#langBtn span").forEach((s) => s.classList.toggle("on", s.dataset.l === lang));
  const title = uiCfg[`title${TITLE_KEY[lang]}`] || uiCfg.title || "YOLO26";
  $("title").textContent = title;
  document.title = title;
  $("subtitle").textContent = uiCfg[`subtitle${TITLE_KEY[lang]}`] || uiCfg.subtitle || "";
  document.querySelectorAll(".modes button").forEach((b, i) => {
    b.innerHTML = `<kbd>${i + 1}</kbd>${t("modes")[b.dataset.mode]}`;
  });
  renderVlmInfo();
  vocabKey = "";
  lastResultKey = null;
  if (lastData) render(lastData);
}

function setLang(newLang) {
  applyLang(newLang);
  post("/api/lang", { lang: newLang });   // 伺服器端:影像標籤與 AI 回答語言
}

function renderVlmInfo() {
  const o = ollamaInfo;
  if (!o) return;
  $("vlmInfo").textContent = o.ok
    ? `${t("vlmModel")}: ${o.vlm_model}${o.vlm ? "" : t("vlmMissing")}`
    : t("ollamaDown");
}

// ---------- 初始化 ----------
async function init() {
  const cfg = await (await fetch("/api/config")).json();
  uiCfg = cfg.ui || {};
  modes = cfg.modes || [];
  idleSeconds = uiCfg.idle_seconds ?? 15;
  $("deviceLabel").textContent = uiCfg.device_label || "";
  const box = $("modes");
  modes.forEach((m) => {
    const b = document.createElement("button");
    b.dataset.mode = m;
    b.onclick = () => setMode(m);
    box.appendChild(b);
  });
  const stats = await (await fetch("/api/stats")).json();
  applyLang(LANGS.includes(stats.lang) ? stats.lang : "zh-TW");
  fetch("/api/health").then((r) => r.json()).then((h) => { ollamaInfo = h.ollama; renderVlmInfo(); });
  poll();
}

function setMode(mode) { post("/api/mode", { mode }); }

// ---------- 統計輪詢 ----------
async function poll() {
  try {
    const d = await (await fetch("/api/stats")).json();
    if (d.lang && d.lang !== lang) applyLang(d.lang);   // 其他畫面切換語言時同步
    lastData = d;
    render(d);
  } catch (e) { /* 伺服器重啟中 */ }
  setTimeout(poll, 250);
}

function fmt(v, digits = 0) { return v == null ? "—" : Number(v).toFixed(digits); }

function statusText(s) {
  if (!s) return "";
  const [code, ...rest] = s.split(":");
  const arg = rest.join(":");
  const st = t("status");
  if (code === "loading") return `${st.loading}: ${t("modes")[arg] || t("faceBlur")}`;
  if (code === "error") return `${st.error}: ${arg}`;
  return st[code] || s;
}

function render(d) {
  const s = d.stats || {}, sys = d.system || {};
  $("fps").textContent = fmt(s.fps);
  $("latency").textContent = fmt(s.infer_ms, 1);
  $("gpuUtil").textContent = sys.gpu_util == null ? "—" : `${fmt(sys.gpu_util)}%`;
  if (sys.gpu_mem_used != null && sys.gpu_mem_total) {
    $("mem").textContent = `${(sys.gpu_mem_used / 1024).toFixed(1)}G`;
    $("memLabel").textContent = `${t("gpuMem")} / ${(sys.gpu_mem_total / 1024).toFixed(0)}G`;
  } else {  // GB10 統一記憶體:顯示系統記憶體
    $("mem").textContent = `${fmt(sys.ram_used_gb, 1)}G`;
    $("memLabel").textContent = `${t("uniMem")} / ${fmt(sys.ram_total_gb)}G`;
  }
  if (s.mode && s.mode !== currentMode) {
    currentMode = s.mode;
    document.querySelectorAll(".modes button").forEach(
      (b) => b.classList.toggle("active", b.dataset.mode === s.mode));
  }
  $("modeName").textContent = s.mode ? t("modes")[s.mode] : statusText(sys.status);
  $("multiPill").classList.toggle("hidden", (s.models_running || 1) < 2);
  faceBlur = !!s.face_blur;
  $("privacyPill").classList.toggle("hidden", !faceBlur);
  $("privacyBtn").classList.toggle("on", faceBlur);
  $("privacyState").textContent = faceBlur ? `${t("on")} (${s.faces ?? 0} ${t("faces")})` : t("off");
  $("uniquePeople").textContent = s.unique_people ?? 0;
  $("uniqueTotal").textContent = s.unique_total ?? 0;
  const counts = Object.entries(s.counts || {}).sort((a, b) => b[1] - a[1]);
  $("counts").innerHTML = counts.length
    ? counts.map(([k, v]) => `<span>${k}<b>${v}</b></span>`).join("")
    : `<span class="dim">${t("noObjects")}</span>`;

  $("camWarn").classList.toggle("hidden", sys.camera_ok !== false);
  const g = d.game || {};
  $("idleOverlay").classList.toggle("hidden", g.active || (sys.idle_s ?? 0) < idleSeconds);
  renderGame(g);
  renderBench(d.benchmark || {});
  renderVocab(d.vocab || []);

  const up = sys.uptime_s || 0;
  $("sysLine").textContent =
    `${sys.gpu_name || sys.device} · ${sys.half ? "FP16" : "FP32"} · CPU ${fmt(sys.cpu)}% · ` +
    `${t("temp")} ${fmt(sys.gpu_temp)}°C · ${t("camera")} #${sys.camera_index} ${(sys.camera_size || []).join("×")} · ` +
    `${t("uptime")} ${Math.floor(up / 3600)}h${Math.floor(up / 60) % 60}m · ${statusText(sys.status)}`;
}

// ---------- 遊戲 ----------
const targetName = (x) => ({ "zh-TW": x.zh, "zh-CN": x.zh_cn, en: x.name })[lang];
const playerName = (p) => p || t("guest");

function renderGame(g) {
  $("gameOverlay").classList.toggle("hidden", !g.active);
  if (g.active) {
    $("gameRemain").textContent = Math.ceil(g.remain);
    $("gameRemain").parentElement.classList.toggle("hurry", g.remain <= 5);
    $("gameTargets").innerHTML = g.targets
      .map((x) => `<li class="${x.found ? "found" : ""}">${targetName(x)}${x.found ? ` <small>${x.at}s</small>` : ""}</li>`)
      .join("");
  }
  const r = g.result;
  const key = r ? `${r.player}-${r.score}-${r.time}` : null;
  if (r && key !== lastResultKey && !g.active) {
    const fresh = lastResultKey !== null || Date.now() - pageStart > 3000;
    lastResultKey = key;
    $("resScore").textContent = r.score;
    $("resDetail").textContent = t("resDetail")({ ...r, player: playerName(r.player) });
    if (fresh) {
      $("resultOverlay").classList.remove("hidden");
      setTimeout(() => $("resultOverlay").classList.add("hidden"), 6000);
    }
  }
  if (g.active) $("resultOverlay").classList.add("hidden");
  $("board").innerHTML = (g.board || [])
    .map((b) => `<li>${playerName(b.player)} <span class="dim small">${b.found}/${b.total} · ${b.time}s</span><b>${b.score}</b></li>`)
    .join("") || `<li class="dim">${t("boardEmpty")}</li>`;
}
const pageStart = Date.now();

function startGame() {
  post("/api/game/start", { player: $("playerInput").value });
  $("playerInput").value = "";
  $("playerInput").blur();
}

// ---------- 效能對比 ----------
function renderBench(b) {
  $("benchBtn").disabled = !!b.running;
  $("benchBtn").textContent = b.running ? t("benchRunning") : t("benchStart");
  const r = b.result;
  if (!r) return;
  if (r.error) { $("speedup").textContent = t("benchFail"); return; }
  const max = Math.max(r.cpu_ms || 0, r.gpu_ms || 0) || 1;
  $("cpuMs").textContent = `${r.cpu_ms} ms`;
  $("cpuBar").style.width = `${(r.cpu_ms / max) * 100}%`;
  if (r.gpu_ms != null) {
    $("gpuMs").textContent = `${r.gpu_ms} ms`;
    $("gpuBar").style.width = `${Math.max(2, (r.gpu_ms / max) * 100)}%`;
    $("speedup").textContent = t("speedup")(r.speedup);
  }
}

// ---------- 開放詞彙 ----------
let vocabKey = "";
function renderVocab(v) {
  const k = lang + v.map((x) => x.en).join("|");
  if (k === vocabKey) return;
  vocabKey = k;
  $("vocabList").innerHTML = v.map((x) => (lang !== "en"
    ? `<span>${x.zh} <span class="dim small">${x.en}</span></span>`
    : `<span>${x.en}</span>`)).join("");
}

async function submitVocab(e) {
  e.preventDefault();
  const text = $("vocabInput").value.trim();
  if (!text) return;
  $("vocabList").innerHTML = `<span class="dim">${t("vocabBusy")}</span>`;
  vocabKey = "";
  await post("/api/vocab", { text });
  $("vocabInput").blur();
}

// ---------- VLM 問答(串流) ----------
async function ask(question) {
  if (typing) return;
  typing = true;
  const out = $("answer");
  out.removeAttribute("data-i18n");   // 有回答後不再被語言切換覆蓋
  out.className = "answer live thinking";
  out.textContent = "";
  try {
    const res = await post("/api/ask", { question });
    const reader = res.body.getReader();
    const dec = new TextDecoder();
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      out.textContent += dec.decode(value, { stream: true });
    }
  } catch (e) {
    out.textContent += `\n[Error] ${e}`;
  }
  out.classList.remove("thinking");
  typing = false;
}

// ---------- 事件 ----------
const togglePrivacy = () => post("/api/privacy", { face_blur: !faceBlur });
document.querySelectorAll(".tabs button").forEach((b) => {
  b.onclick = () => {
    document.querySelectorAll(".tabs button").forEach((x) => x.classList.toggle("active", x === b));
    document.querySelectorAll(".tab-body").forEach((x) => x.classList.toggle("hidden", x.id !== `tab-${b.dataset.tab}`));
  };
});
document.querySelectorAll(".quick button").forEach((b) => (b.onclick = () => ask(t(b.dataset.q))));
$("askForm").onsubmit = (e) => {
  e.preventDefault();
  const q = $("askInput").value.trim();
  if (q) { ask(q); $("askInput").value = ""; $("askInput").blur(); }
};
$("vocabForm").onsubmit = submitVocab;
$("gameForm").onsubmit = (e) => { e.preventDefault(); startGame(); };
$("benchBtn").onclick = () => post("/api/benchmark");
$("privacyBtn").onclick = togglePrivacy;
const nextLang = () => LANGS[(LANGS.indexOf(lang) + 1) % LANGS.length];
document.querySelectorAll("#langBtn span").forEach((s) => {
  s.onclick = (e) => { e.stopPropagation(); setLang(s.dataset.l); };
});

// 操作員快捷鍵(輸入框中不觸發)
const MODE_KEYS = ["detect", "segment", "pose", "multi", "openvocab"];
document.addEventListener("keydown", (e) => {
  if (e.target.tagName === "INPUT") return;
  const k = e.key.toLowerCase();
  if (k >= "1" && k <= "5") setMode(MODE_KEYS[Number(k) - 1]);
  else if (k === "g") startGame();
  else if (k === "b") post("/api/benchmark");
  else if (k === "d") ask(t("q1"));
  else if (k === "h") document.body.classList.toggle("kiosk");
  else if (k === "p") togglePrivacy();
  else if (k === "l") setLang(nextLang());   // 繁 → 简 → EN 循環
  else if (k === "s") window.open("/api/snapshot");
  else if (k === "f") {
    if (document.fullscreenElement) document.exitFullscreen();
    else document.documentElement.requestFullscreen();
  }
});

// 串流中斷時自動重連
$("video").onerror = () => setTimeout(() => { $("video").src = `/stream?t=${Date.now()}`; }, 1000);

init();

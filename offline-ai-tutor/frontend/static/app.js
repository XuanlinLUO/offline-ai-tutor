"use strict";
const $ = (id) => document.getElementById(id);
const state = {ready:false, busy:false, visionBusy:false, demo:false, history:[], answer:"", controller:null};
const question = $("question");
function notice(message) { $("notice").textContent = message || ""; $("notice").hidden = !message; }
function sync() {
  $("ask").disabled = !state.ready || state.busy || state.visionBusy || !question.value.trim();
  $("capture").disabled = state.busy || state.visionBusy || state.demo;
  $("upload").disabled = state.busy || state.visionBusy || state.demo;
  $("example").disabled = state.busy || state.visionBusy;
  question.disabled = state.busy || state.visionBusy;
  $("followup-send").disabled = state.busy || !state.ready;
  $("char-count").textContent = `${question.value.length} / 12000`;
  $("copy").disabled = !state.answer;
}
function resetAnswer() {
  state.history = []; state.answer = "";
  $("answer").textContent = ""; $("answer").hidden = true;
  $("answer-empty").hidden = false; $("followup-area").hidden = true;
  $("generation-status").textContent = "准备好后，我们就开始。";
  $("followup").value = "";
}
function setQuestion(text) { question.value = text; resetAnswer(); sync(); }
async function health() {
  try {
    const res = await fetch("/api/health", {signal:AbortSignal.timeout(5000)});
    if (!res.ok) throw new Error("本地服务不可用");
    const info = await res.json();
    state.ready = Boolean(info.model.ready); state.demo = Boolean(info.demo);
    $("status").textContent = info.model.message;
    $("status-dot").classList.toggle("ready", state.ready);
    $("demo-banner").hidden = !state.demo;
    $("model-label").textContent = state.demo ? "DEMO / 固定界面示例" : `本机模型：${info.model.model || "尚未配置"}`;
  } catch (_) {
    state.ready = false; $("status").textContent = "本地服务未连接";
    $("status-dot").classList.remove("ready");
  }
  sync();
}
async function post(path, data, signal) {
  const res = await fetch(path, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(data), signal});
  if (!res.ok) {
    let message = `请求失败（${res.status}）`;
    try {message = (await res.json()).error || message;} catch (_) { /* keep fallback */ }
    throw new Error(message);
  }
  return res;
}
async function vision(image) {
  state.visionBusy = true; notice(""); sync();
  $("vision-metrics").textContent = "正在识别题目，首次使用还需要加载本地 OCR 模型，请稍候…";
  try {
    const res = await post(image ? "/api/ocr" : "/api/capture", image ? {image} : {});
    const data = await res.json(); setQuestion(data.text || "");
    if (data.preview) {$("preview").src = data.preview; $("preview").hidden = false; $("preview-empty").hidden = true;}
    const m = data.metrics;
    $("vision-metrics").textContent = `本次图片处理 ${m.total_seconds} 秒 · OCR ${m.ocr_seconds} 秒（可能含首次加载）。请核对识别结果。`;
    if (!data.text) notice("没有识别到文字，请重新拍照或手动输入题目。");
  } catch (error) {
    $("vision-metrics").textContent = ""; notice(error.message);
  } finally {state.visionBusy = false; sync();}
}
async function generate(text, followup=false) {
  text = text.trim(); if (!text || state.busy || !state.ready) return;
  if (!followup) state.history = [];
  if (state.history.length >= 12) {notice("已达到当前对话长度，请点击“新题目”继续。"); return;}
  const history = state.history.slice();
  state.busy = true; state.answer = ""; state.controller = new AbortController();
  $("answer").textContent = ""; $("answer").hidden = false; $("answer-empty").hidden = true;
  $("stop").hidden = false; $("followup-area").hidden = true;
  $("generation-status").textContent = "正在理解题目，请稍候…";
  notice(""); sync();
  let completed = false, errored = false, buffer = "";
  const decoder = new TextDecoder();
  function event(block) {
    const lines = block.split(/\r?\n/).filter((line) => line.startsWith("data:"));
    if (!lines.length) return;
    const data = JSON.parse(lines.map((line) => line.slice(5).trimStart()).join("\n"));
    if (data.type === "token") {
      state.answer += data.content; $("answer").textContent = state.answer;
      $("answer").scrollTop = $("answer").scrollHeight;
      $("generation-status").textContent = state.demo ? "固定示例演示中…" : "正在逐步生成讲解…";
    } else if (data.type === "done") {
      completed = true;
      const m = data.metrics || {};
      if (m.simulation) $("generation-status").textContent = "固定示例已结束 · 未调用 AI 模型";
      else {
        const parts = ["本次解答已完成"];
        if (m.first_output_seconds != null) parts.push(`模型首字 ${m.first_output_seconds} 秒`);
        if (m.generation_seconds != null) parts.push(`生成 ${m.generation_seconds} 秒`);
        if (m.tokens_per_second != null) parts.push(`${m.tokens_per_second} tok/s`);
        if (m.finish_reason === "length") parts.push("达到输出上限，可继续追问");
        $("generation-status").textContent = parts.join(" · ");
      }
    } else if (data.type === "error") {errored = true; throw new Error(data.message);}
  }
  try {
    const res = await post("/api/ask", {text, history}, state.controller.signal);
    if (!res.body) throw new Error("当前浏览器不支持流式响应");
    const reader = res.body.getReader();
    try {
      while (true) {
        const {value, done} = await reader.read();
        buffer += done ? decoder.decode() : decoder.decode(value, {stream:true});
        let match;
        while ((match = /\r?\n\r?\n/.exec(buffer))) {
          event(buffer.slice(0, match.index)); buffer = buffer.slice(match.index + match[0].length);
        }
        if (done) break;
      }
      if (buffer.trim()) event(buffer);
    } finally {await reader.cancel().catch(() => {}); reader.releaseLock();}
    if (!completed) throw new Error("连接提前结束，解答可能不完整，请重试。");
    state.history = [...history, {role:"user", content:text}, {role:"assistant", content:state.answer}];
    $("followup-area").hidden = false; $("followup").value = "";
  } catch (error) {
    if (error.name === "AbortError") $("generation-status").textContent = "已停止接收，当前解答可能不完整。";
    else {errored = true; notice(error.message); $("generation-status").textContent = "本次解答未完成。";}
  } finally {
    state.busy = false; state.controller = null; $("stop").hidden = true;
    if (errored) $("followup-area").hidden = true;
    sync();
  }
}
question.addEventListener("input", () => {resetAnswer(); sync();});
$("ask").addEventListener("click", () => generate(question.value));
$("example").addEventListener("click", () => {setQuestion("解方程：2x + 6 = 14。请解释每一步的依据。"); notice("");});
$("capture").addEventListener("click", () => vision(null));
$("upload").addEventListener("click", () => $("file").click());
$("file").addEventListener("change", async (e) => {
  const file = e.target.files[0]; e.target.value = "";
  if (!file) return;
  if (file.size > 5*1024*1024 || !["image/png","image/jpeg"].includes(file.type)) {notice("请选择小于 5 MiB 的 PNG 或 JPEG 图片。"); return;}
  const reader = new FileReader();
  reader.onload = () => vision(reader.result);
  reader.onerror = () => notice("图片读取失败，请重新选择。");
  reader.readAsDataURL(file);
});
$("stop").addEventListener("click", () => state.controller?.abort());
$("new-question").addEventListener("click", () => {
  if (state.busy || state.visionBusy) {notice("请先停止当前解答，或等待图片识别结束。"); return;}
  setQuestion(""); $("preview").hidden = true; $("preview").removeAttribute("src");
  $("preview-empty").hidden = false; $("vision-metrics").textContent = ""; notice(""); question.focus();
});
$("followup-send").addEventListener("click", () => generate($("followup").value, true));
$("followup").addEventListener("keydown", (e) => {if (e.key === "Enter" && !e.isComposing) generate($("followup").value, true);});
$("copy").addEventListener("click", async () => {
  try {await navigator.clipboard.writeText(state.answer); $("copy").textContent = "已复制"; setTimeout(() => $("copy").textContent = "复制解答", 1400);}
  catch (_) {notice("浏览器不允许自动复制，请选中解答文字后复制。");}
});
health(); setInterval(health, 30000);

const $ = (id) => document.getElementById(id);
const messages = $("messages");

function escapeHtml(text) {
  return text.replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[c]);
}

// WhatsApp formatting: *bold* and _italic_ (applied after escaping).
function formatWhatsApp(text) {
  return escapeHtml(text)
    .replace(/\*([^*\n]+)\*/g, "<strong>$1</strong>")
    .replace(/(^|[\s(])_([^_\n]+)_/g, "$1<em>$2</em>");
}

function addMessage(kind, text) {
  const bubble = document.createElement("div");
  bubble.className = `msg ${kind}`;
  bubble.innerHTML = kind === "theirs" ? formatWhatsApp(text) : escapeHtml(text);
  messages.append(bubble);
  messages.scrollTop = messages.scrollHeight;
  return bubble;
}

async function postJson(url, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok && response.status !== 204) {
    const detail = await response.json().catch(() => ({}));
    // validation errors (422) come as a list; others, like the rate limit (429), as text
    const message = Array.isArray(detail.detail) ? detail.detail[0]?.msg : detail.detail;
    throw new Error(message || `Erro ${response.status}`);
  }
  return response.status === 204 ? null : response.json();
}

$("composer").addEventListener("submit", async (event) => {
  event.preventDefault();
  const text = $("text").value.trim();
  const phone = $("phone").value.trim();
  if (!text) return;
  if (!phone) { addMessage("status", "Informe um número de WhatsApp para simular o cliente."); return; }

  addMessage("mine", text);
  $("text").value = "";
  $("send").disabled = true;
  const typing = addMessage("status", "digitando…");
  try {
    const data = await postJson("/chat", {
      phone, text, customer_name: $("name").value.trim() || null,
      message_id: crypto.randomUUID(),
    });
    typing.remove();
    addMessage("theirs", data.reply);
  } catch (error) {
    typing.remove();
    addMessage("status", error.message);
  } finally {
    $("send").disabled = false;
    $("text").focus();
  }
});

$("reset").addEventListener("click", async () => {
  const phone = $("phone").value.trim();
  messages.replaceChildren();
  if (phone) {
    try { await postJson("/chat/reset", { phone }); } catch (error) { addMessage("status", error.message); }
  }
  addMessage("status", "Nova conversa iniciada.");
});

// O serviço de inscrição do fato do dia por e-mail (inscricao.vaidarcrise.com.br), um Worker do Cloudflare.
//
// O site é estático e não guarda nada: o formulário das páginas manda o endereço para cá, este serviço manda o e-mail
// de confirmação pelo Resend e, quando a pessoa toca no botão do e-mail, põe o endereço na lista do Resend. Só entra
// na lista quem confirma (a prova do consentimento que a LGPD pede). O link de confirmação leva o endereço e o prazo
// assinados com uma chave secreta, então o serviço não precisa de banco de dados. Sair da lista é com o Resend, pelo
// link no fim de todo e-mail; src/newsletter.py --limpa apaga quem saiu.
//
// Os textos que a leitora vê aqui (o e-mail de confirmação) seguem o PERSONA.md, como os do site. As páginas para
// onde o serviço manda a pessoa ficam no site (templates/inscricao.html).
//
// Segredos e valores (publicados por inscricao/publica.py): RESEND_API_KEY, SEGREDO (assina o link), SEGMENTO (id do
// segmento no Resend), REMETENTE, RESPONDER, e TURNSTILE_SECRET quando a barreira contra robôs estiver ligada.
// LIMITE é o limite de pedidos por endereço de internet (binding de rate limit do Workers).

const SITE = "https://vaidarcrise.com.br";
const VALIDADE = 2 * 24 * 3600; // o link de confirmação vale dois dias

export default {
  async fetch(req, env) {
    const url = new URL(req.url);
    try {
      if (url.pathname === "/saude") {
        return Response.json({ ok: Boolean(env.RESEND_API_KEY && env.SEGREDO && env.SEGMENTO && env.REMETENTE) });
      }
      if (url.pathname === "/inscrever" && req.method === "POST") return await inscrever(req, env);
      if (url.pathname === "/confirmar") return await confirmar(url, env);
      if (url.pathname === "/" || url.pathname === "/inscrever") return volta("/inscricao/");
      return new Response("Página não encontrada.", { status: 404 });
    } catch (e) {
      console.log("erro:", e && e.stack || e);
      return volta("/inscricao/erro/");
    }
  },
};

function volta(caminho) {
  return Response.redirect(SITE + caminho, 303);
}

// ------------------------------------------------------------------ inscrição
async function inscrever(req, env) {
  const form = await req.formData();
  // Campo escondido que só robô preenche: finge que deu certo e não manda nada.
  if ((form.get("site") || "").toString().trim()) return volta("/inscricao/confira/");
  const email = (form.get("email") || "").toString().trim().toLowerCase();
  if (!valido(email)) return volta("/inscricao/?invalido=1");
  const ip = req.headers.get("cf-connecting-ip") || "";
  if (env.LIMITE) {
    const { success } = await env.LIMITE.limit({ key: ip || email });
    if (!success) return volta("/inscricao/confira/");
  }
  if (env.TURNSTILE_SECRET) {
    const ok = await turnstile(env.TURNSTILE_SECRET, (form.get("cf-turnstile-response") || "").toString(), ip);
    if (!ok) return volta("/inscricao/?robo=1");
  }
  const token = await assina({ e: email, x: Math.floor(Date.now() / 1000) + VALIDADE }, env.SEGREDO);
  const link = new URL(req.url).origin + "/confirmar?t=" + token;
  const r = await resend(env, "POST", "/emails", {
    from: env.REMETENTE,
    to: [email],
    reply_to: env.RESPONDER,
    subject: "Confirme a inscrição no Vai dar crise?",
    html: emailConfirmacao(link),
    text: textoConfirmacao(link),
  });
  if (!r.ok) {
    console.log("resend /emails:", r.status, await r.text());
    return volta("/inscricao/erro/");
  }
  return volta("/inscricao/confira/");
}

function valido(email) {
  return email.length <= 254 && /^[^\s@<>"',;]+@[^\s@<>"',;]+\.[a-z]{2,}$/.test(email);
}

async function turnstile(secret, resposta, ip) {
  if (!resposta) return false;
  const corpo = new FormData();
  corpo.append("secret", secret);
  corpo.append("response", resposta);
  if (ip) corpo.append("remoteip", ip);
  const r = await fetch("https://challenges.cloudflare.com/turnstile/v0/siteverify", { method: "POST", body: corpo });
  return r.ok && (await r.json()).success === true;
}

// ------------------------------------------------------------------ confirmação
async function confirmar(url, env) {
  const dados = await confere(url.searchParams.get("t") || "", env.SEGREDO);
  if (!dados || dados.x < Math.floor(Date.now() / 1000)) return volta("/inscricao/vencido/");
  const email = dados.e;
  let r = await resend(env, "POST", "/contacts", { email, unsubscribed: false, segments: [{ id: env.SEGMENTO }] });
  if (!r.ok) {
    // Já é contato (saiu e voltou, ou tocou duas vezes no botão): volta para a lista e para o segmento.
    const achado = await resend(env, "GET", "/contacts/" + encodeURIComponent(email));
    if (!achado.ok) {
      console.log("resend /contacts:", r.status, await r.text());
      return volta("/inscricao/erro/");
    }
    const c = await achado.json();
    await resend(env, "PATCH", "/contacts/" + c.id, { unsubscribed: false });
    r = await resend(env, "POST", "/contacts/" + c.id + "/segments/" + env.SEGMENTO);
    if (!r.ok && r.status !== 409 && r.status !== 422) {
      console.log("resend segmento:", r.status, await r.text());
      return volta("/inscricao/erro/");
    }
  }
  return volta("/inscricao/pronto/");
}

// ------------------------------------------------------------------ o link assinado
const b64 = (bytes) => btoa(String.fromCharCode(...new Uint8Array(bytes))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
const deB64 = (s) => Uint8Array.from(atob(s.replace(/-/g, "+").replace(/_/g, "/")), (c) => c.charCodeAt(0));

async function chave(segredo) {
  return crypto.subtle.importKey("raw", new TextEncoder().encode(segredo), { name: "HMAC", hash: "SHA-256" }, false, ["sign", "verify"]);
}

async function assina(dados, segredo) {
  const corpo = b64(new TextEncoder().encode(JSON.stringify(dados)));
  const sig = await crypto.subtle.sign("HMAC", await chave(segredo), new TextEncoder().encode(corpo));
  return corpo + "." + b64(sig);
}

async function confere(token, segredo) {
  const [corpo, sig] = token.split(".");
  if (!corpo || !sig) return null;
  try {
    const ok = await crypto.subtle.verify("HMAC", await chave(segredo), deB64(sig), new TextEncoder().encode(corpo));
    return ok ? JSON.parse(new TextDecoder().decode(deB64(corpo))) : null;
  } catch {
    return null;
  }
}

// ------------------------------------------------------------------ Resend
async function resend(env, metodo, caminho, corpo) {
  for (let i = 0; i < 3; i++) {
    const r = await fetch("https://api.resend.com" + caminho, {
      method: metodo,
      headers: { Authorization: "Bearer " + env.RESEND_API_KEY, "Content-Type": "application/json", "User-Agent": "vaidarcrise-inscricao" },
      body: corpo ? JSON.stringify(corpo) : undefined,
    });
    if (r.status !== 429 && r.status < 500) return r;
    await new Promise((ok) => setTimeout(ok, 1000 * (i + 1)));
  }
  return new Response("Resend sem resposta", { status: 503 });
}

// ------------------------------------------------------------------ o e-mail de confirmação
// O mesmo desenho do e-mail do fato do dia (templates/email.html): estilo dentro de cada elemento e tabelas.
const SERIFA = "'Charis SIL',Charter,'Bitstream Charter','Iowan Old Style',Georgia,serif";
const SISTEMA = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif";

function emailConfirmacao(link) {
  return `<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light"><title>Confirme a inscrição</title></head>
<body style="margin:0;padding:0;background:#ffffff">
<div style="display:none;max-height:0;overflow:hidden;opacity:0">Toque no botão para começar a receber o fato do dia.</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#ffffff"><tr><td align="center" style="padding:0 16px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width:560px">
<tr><td style="padding:24px 0 16px;border-bottom:1px solid #e4e6e8">
  <a href="${SITE}/" style="text-decoration:none;color:#1e1f21"><img src="${SITE}/email/marca.png" width="26" height="26" alt="" style="vertical-align:middle;border:0;margin:0 8px 0 0"><span style="font:700 26px/1.1 ${SERIFA};color:#1e1f21;vertical-align:middle">Vai dar crise?</span></a>
</td></tr>
<tr><td style="padding:26px 0 8px">
  <h1 style="margin:0 0 14px;font:700 26px/1.2 ${SERIFA};color:#1e1f21">Confirme a inscrição</h1>
  <p style="margin:0 0 16px;font:18px/1.6 ${SERIFA};color:#1e1f21">Alguém pediu para receber o fato do dia do Vai dar crise? neste endereço. Se foi você, toque no botão abaixo, e o próximo e-mail chega amanhã de manhã.</p>
  <table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:6px 0 20px"><tr><td style="background:#1e1f21;border-radius:10px">
    <a href="${link}" style="display:inline-block;padding:14px 20px;font:700 16px/1.2 ${SISTEMA};color:#ffffff;text-decoration:none">Confirmar a inscrição</a>
  </td></tr></table>
  <p style="margin:0 0 16px;font:15px/1.5 ${SISTEMA};color:#62666b">Se não foi você, ignore este e-mail, porque o endereço só entra na lista depois do toque no botão. O link vale por dois dias.</p>
</td></tr>
<tr><td style="padding:16px 0 32px;border-top:1px solid #e4e6e8">
  <p style="margin:0;font:14px/1.5 ${SISTEMA};color:#62666b"><a href="${SITE}/privacidade/" style="color:#62666b">Privacidade</a> | <a href="${SITE}/" style="color:#62666b">vaidarcrise.com.br</a></p>
</td></tr>
</table></td></tr></table></body></html>`;
}

function textoConfirmacao(link) {
  return `Confirme a inscrição no Vai dar crise?

Alguém pediu para receber o fato do dia do Vai dar crise? neste endereço. Se foi você, abra o link abaixo, e o próximo e-mail chega amanhã de manhã.

${link}

Se não foi você, ignore este e-mail, porque o endereço só entra na lista depois que o link é aberto. O link vale por dois dias.

Privacidade: ${SITE}/privacidade/`;
}

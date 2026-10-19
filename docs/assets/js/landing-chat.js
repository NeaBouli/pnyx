
// EKA-62: every chat string reaches the DOM via textContent on created nodes;
// no HTML string sink is used here. 429 has its own bilingual state and a retry.
var CHAT_TEXT={
  el:{empty:"Δεν μπόρεσα να απαντήσω.",error:"Ο βοηθός δεν μπόρεσε να απαντήσει. Δοκιμάστε ξανά σε λίγο.",offline:"Σφάλμα σύνδεσης.",rate:"Πάρα πολλές ερωτήσεις σε σύντομο χρόνο (όριο: 5 ανά λεπτό). Περιμένετε ένα λεπτό και δοκιμάστε ξανά.",retry:"Δοκιμάστε ξανά",sources:"Πηγές:",loading:"Αναζήτηση απάντησης…"},
  en:{empty:"I couldn't answer that.",error:"The assistant could not answer. Please try again shortly.",offline:"Connection error.",rate:"Too many questions in a short time (limit: 5 per minute). Please wait a minute and try again.",retry:"Try again",sources:"Sources:",loading:"Looking for an answer…"}
};
var CHAT_STYLE={
  user:"background:#f1f5f9;border-radius:0.75rem;padding:0.6rem 0.8rem;margin-bottom:0.5rem;text-align:right;color:#334155",
  bot:"background:#eff6ff;border-radius:0.75rem;padding:0.6rem 0.8rem;margin-bottom:0.5rem;color:#1e40af;font-size:0.8rem",
  loading:"color:#94a3b8;font-size:0.8rem;padding:0.3rem 0.8rem",
  error:"background:#fef2f2;border-radius:0.75rem;padding:0.6rem 0.8rem;margin-bottom:0.5rem;color:#991b1b;font-size:0.8rem",
  "rate-limited":"background:#fffbeb;border:1px solid #fcd34d;border-radius:0.75rem;padding:0.6rem 0.8rem;margin-bottom:0.5rem;color:#92400e;font-size:0.8rem"
};
var chatBusy=false;
function chatLang(){return (typeof currentLang!=="undefined"&&currentLang==="en")?"en":"el"}
function chatNode(kind,text){
  var d=document.createElement("div");
  d.className="chat-msg";
  d.setAttribute("data-chat-kind",kind);
  d.style.cssText=CHAT_STYLE[kind]+";white-space:pre-wrap;overflow-wrap:anywhere";
  d.textContent=text;
  return d;
}
function chatAppend(node){
  var msgs=document.getElementById("chatMessages");
  msgs.appendChild(node);
  msgs.scrollTop=msgs.scrollHeight;
  return node;
}
function chatSources(list,lang){
  if(!Array.isArray(list)||!list.length)return null;
  var box=document.createElement("div");
  box.setAttribute("data-chat-sources","");
  box.style.cssText="margin-top:0.4rem;font-size:0.7rem;color:#475569";
  var head=document.createElement("div");
  head.textContent=CHAT_TEXT[lang].sources;
  box.appendChild(head);
  var ul=document.createElement("ul");
  ul.style.cssText="margin:0;padding-left:1rem";
  list.forEach(function(s){
    if(!s||typeof s!=="object")return;
    var title=typeof s.title==="string"?s.title:"";
    var label=s.type==="parliament_bill"&&typeof s.bill_id==="string"?s.bill_id+(title?" — "+title:""):title;
    if(!label)return;
    var li=document.createElement("li");
    li.textContent=label;
    ul.appendChild(li);
  });
  if(!ul.children.length)return null;
  box.appendChild(ul);
  return box;
}
function chatFailure(kind,text,q,lang){
  var n=chatNode(kind,"⚠️ "+text);
  n.setAttribute("role",kind==="rate-limited"?"alert":"status");
  var b=document.createElement("button");
  b.textContent=CHAT_TEXT[lang].retry;
  b.setAttribute("data-chat-retry","");
  b.style.cssText="display:block;margin-top:0.4rem;padding:0.25rem 0.6rem;background:white;border:1px solid currentColor;border-radius:0.4rem;color:inherit;font-weight:700;font-size:0.75rem;cursor:pointer";
  b.onclick=function(){if(chatBusy)return;n.remove();askChat(q,lang)};
  n.appendChild(b);
  chatAppend(n);
}
function toggleChat(){
  var p=document.getElementById("chatPanel");
  var open=p.style.display==="none";
  p.style.display=open?"flex":"none";
  document.getElementById("chatToggle").setAttribute("aria-expanded",open?"true":"false");
  if(open){
    var inp=document.getElementById("chatInput");
    inp.placeholder=inp.getAttribute("data-"+chatLang()+"-placeholder")||"...";
    inp.focus();
  }else{
    document.getElementById("chatToggle").focus();
  }
}
document.getElementById("chatPanel").onkeydown=function(e){
  if(e.key==="Escape")toggleChat();
};
function sendChat(){
  if(chatBusy)return;
  var inp=document.getElementById("chatInput");
  var q=inp.value.trim();
  if(!q)return;
  inp.value="";
  var lang=chatLang();
  chatAppend(chatNode("user",q));
  askChat(q,lang);
}
function askChat(q,lang){
  chatBusy=true;
  var msgs=document.getElementById("chatMessages");
  msgs.setAttribute("aria-busy","true");
  var loading=chatAppend(chatNode("loading","⏳ "+CHAT_TEXT[lang].loading));
  var done=function(){loading.remove();chatBusy=false;msgs.removeAttribute("aria-busy")};
  fetch("https://api.ekklesia.gr/api/v1/agent/ask",{
    method:"POST",headers:{"Content-Type":"application/json"},
    body:JSON.stringify({question:q,lang:lang})
  }).then(function(r){
    if(r.status===429)return {state:"rate-limited"};
    if(!r.ok)return {state:"error"};
    return r.json().then(function(d){return {state:"ok",data:d}},function(){return {state:"error"}});
  }).then(function(res){
    done();
    if(res.state!=="ok"){
      chatFailure(res.state,CHAT_TEXT[lang][res.state==="rate-limited"?"rate":"error"],q,lang);
      return;
    }
    var d=res.data||{};
    var n=chatNode("bot",typeof d.answer==="string"&&d.answer?d.answer:CHAT_TEXT[lang].empty);
    var src=chatSources(d.sources,lang);
    if(src)n.appendChild(src);
    chatAppend(n);
  }).catch(function(){
    done();
    chatFailure("error",CHAT_TEXT[lang].offline,q,lang);
  });
}

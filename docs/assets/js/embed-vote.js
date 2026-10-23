
var API='https://api.ekklesia.gr';
var params=new URLSearchParams(window.location.search);
var billId=params.get('bill_id')||params.get('bill')||'';
var lang=params.get('lang')||'el';
var el=lang==='el';

// Auth state from QR session
var authState={
  authenticated:false,
  session_id:null,
  nullifier_hash:null,
  public_key_hex:null
};

// Listen for QR auth messages from iframe
window.addEventListener('message',function(evt){
  var qrFrame = document.getElementById('qr-frame');
  if(evt.origin !== window.location.origin || !qrFrame || evt.source !== qrFrame.contentWindow) return;
  if(!evt.data||evt.data.type!=='ekklesia-qr-auth')return;
  if(evt.data.status==='authenticated'){
    authState.authenticated=true;
    authState.session_id=evt.data.session_id||null;
    authState.nullifier_hash=evt.data.nullifier_hash||null;
    authState.public_key_hex=evt.data.public_key_hex||null;
    onAuthenticated();
  }
});

function onAuthenticated(){
  // Hide QR iframe, show auth success + enable vote buttons
  var qrFrame=document.getElementById('qr-frame');
  if(qrFrame)qrFrame.style.display='none';
  var authBar=document.getElementById('auth-bar');
  if(authBar){authBar.className='auth-bar success';authBar.textContent=el?'✅ Ταυτοποίηση επιτυχής — ψηφίστε παρακάτω':'✅ Authenticated — vote below';}
  // Enable vote buttons
  var btns=document.querySelectorAll('.vote-btn');
  btns.forEach(function(b){b.disabled=false;});
}

async function castVote(choice){
  if(!authState.authenticated||!authState.session_id){
    alert(el?'Πρέπει πρώτα να σκανάρετε το QR code.':'Please scan the QR code first.');
    return;
  }
  // Disable buttons during submission
  var btns=document.querySelectorAll('.vote-btn');
  btns.forEach(function(b){b.disabled=true;});
  var authBar=document.getElementById('auth-bar');
  if(authBar){authBar.className='auth-bar voting';authBar.textContent=el?'⏳ Υποβολή ψήφου...':'⏳ Submitting vote...';}

  try{
    var r=await fetch(API+'/api/v1/polis/qr-vote',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({session_id:authState.session_id,bill_id:billId,vote:choice})
    });
    var d=await r.json();
    if(r.ok&&d.success){
      showVoteDone(choice);
      // Notify parent if embedded
      if(window.parent!==window && document.referrer){
        var parentUrl = new URL(document.referrer);
        if (parentUrl.protocol === 'https:' || parentUrl.protocol === 'http:') {
          window.parent.postMessage({type:'ekklesia-vote-done',bill_id:billId,vote:choice},parentUrl.origin);
        }
      }
    }else{
      alert((d.detail||d.message||'Error')+(el?' — Δοκιμάστε ξανά.':' — Try again.'));
      btns.forEach(function(b){b.disabled=false;});
      if(authBar){authBar.className='auth-bar success';authBar.textContent=el?'✅ Ταυτοποίηση επιτυχής — ψηφίστε παρακάτω':'✅ Authenticated — vote below';}
    }
  }catch(e){
    alert(el?'Σφάλμα δικτύου. Δοκιμάστε ξανά.':'Network error. Try again.');
    btns.forEach(function(b){b.disabled=false;});
    if(authBar){authBar.className='auth-bar success';authBar.textContent=el?'✅ Ταυτοποίηση επιτυχής':'✅ Authenticated';}
  }
}

function showVoteDone(choice){
  var area = document.getElementById('vote-area');
  if (!area) return;
  var labels={YES:el?'ΝΑΙ':'YES',NO:el?'ΟΧΙ':'NO',ABSTAIN:el?'ΑΠΟΧΗ':'ABSTAIN'};
  var icons={YES:'👍',NO:'👎',ABSTAIN:'⏸️'};
  area.replaceChildren();
  var done = EmbedUI.node(area, 'div', 'vote-done');
  EmbedUI.node(done, 'div', 'icon', icons[choice] || '');
  EmbedUI.node(done, 'div', 'msg', (el?'Ψήφος: ':'Vote: ') + (labels[choice] || ''));
  EmbedUI.node(done, 'div', '', el?'Ψήφος καταγράφηκε (χωρίς όνομα)':'Vote recorded (no name)');
  // Refresh results
  loadResults();
}

var currentBill=null;

async function load(){
  if(!document.getElementById('widget') || !document.getElementById('loader')) return;
  if(!billId){document.getElementById('loader').className='error';document.getElementById('loader').textContent=el?'Λείπει bill_id':'Missing bill_id';return}
  try{
    var r=await fetch(API+'/api/v1/bills/'+encodeURIComponent(billId));
    if(!r.ok)throw new Error(r.status);
    currentBill=await r.json();
    var vr=await fetch(API+'/api/v1/vote/'+encodeURIComponent(billId)+'/results').then(function(x){return x.json()}).catch(function(){return{}});
    render(currentBill,vr);
  }catch(e){document.getElementById('loader').className='error';document.getElementById('loader').textContent=(el?'Νομοσχέδιο δεν βρέθηκε: ':'Bill not found: ')+billId}
}

async function loadResults(){
  try{
    var vr=await fetch(API+'/api/v1/vote/'+encodeURIComponent(billId)+'/results').then(function(x){return x.json()}).catch(function(){return{}});
    var resultsEl=document.getElementById('results-area');
    if(resultsEl && vr) EmbedUI.results(resultsEl, vr, el);
  }catch(e){}
}

function render(b,vr){
  var widget = document.getElementById('widget');
  if (!widget) return;
  widget.replaceChildren();
  var st = b.status || 'ANNOUNCED';
  var sc = {ACTIVE:'status-active', ANNOUNCED:'status-announced', PARLIAMENT_VOTED:'status-voted', OPEN_END:'status-open', WINDOW_24H:'status-active'};
  var sl = {ACTIVE:el?'Ανοιχτή':'Active', ANNOUNCED:el?'Ανακοινώθηκε':'Announced', PARLIAMENT_VOTED:el?'Ψηφίστηκε':'Voted', OPEN_END:el?'Αρχείο':'Archive', WINDOW_24H:el?'24ω':'24h'};
  EmbedUI.node(widget, 'span', 'status ' + (sc[st] || 'status-announced'), sl[st] || st);
  EmbedUI.node(widget, 'div', 'title', b.title_el || b.title_en || billId);
  var parliamentContent = EmbedUI.parliamentAttribution(widget, b, el);
  if (b.pill_el) {
    if (parliamentContent) EmbedUI.node(widget, 'div', 'pill', el ? 'Σύνοψη — ekklesia' : 'Summary — ekklesia');
    EmbedUI.node(widget, 'div', 'pill', b.pill_el);
  }
  if (st === 'ACTIVE' || st === 'WINDOW_24H') {
    EmbedUI.node(widget, 'div', 'auth-bar', el?'🔐 Σκανάρετε το QR code με την εφαρμογή ekklesia.gr για ταυτοποίηση':'🔐 Scan the QR code with the ekklesia.gr app to authenticate').id = 'auth-bar';
    var qr = EmbedUI.node(widget, 'iframe', 'qr-frame');
    qr.id = 'qr-frame';
    qr.src = 'qr-login.html?purpose=vote&bill_id=' + encodeURIComponent(billId);
    var area = EmbedUI.node(widget, 'div'); area.id = 'vote-area';
    var buttons = EmbedUI.node(area, 'div', 'btns');
    [['YES','yes',el?'ΝΑΙ':'YES'],['NO','no',el?'ΟΧΙ':'NO'],['ABSTAIN','abstain',el?'ΑΠΟΧΗ':'ABSTAIN']].forEach(function(item) {
      var button = EmbedUI.node(buttons, 'button', 'btn btn-' + item[1] + ' vote-btn', item[2]);
      button.disabled = true;
      button.setAttribute('data-csp-click', 'embed-vote');
      button.dataset.choice = item[0];
    });
  }
  var results = EmbedUI.node(widget, 'div'); results.id = 'results-area';
  EmbedUI.results(results, vr, el);
  EmbedUI.attribution(widget, el, 'https://ekklesia.gr/el/bills/' + encodeURIComponent(billId), el?'Λεπτομέρειες':'Details');
}
load();
setInterval(loadResults,60000);

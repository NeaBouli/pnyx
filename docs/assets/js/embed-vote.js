
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
      if(window.parent!==window){
        window.parent.postMessage({type:'ekklesia-vote-done',bill_id:billId,vote:choice},'*');
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
  var labels={YES:el?'ΝΑΙ':'YES',NO:el?'ΟΧΙ':'NO',ABSTAIN:el?'ΑΠΟΧΗ':'ABSTAIN'};
  var icons={YES:'👍',NO:'👎',ABSTAIN:'⏸️'};
  document.getElementById('vote-area').innerHTML='<div class="vote-done"><div class="icon">'+icons[choice]+'</div><div class="msg">'+(el?'Ψήφος: ':'Vote: ')+labels[choice]+'</div><div style="font-size:12px;color:#64748b;margin-top:6px">'+(el?'Ψήφος καταγράφηκε (χωρίς όνομα)':'Vote recorded (no name)')+'</div></div>';
  // Refresh results
  loadResults();
}

var currentBill=null;

async function load(){
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
    if(resultsEl&&vr){
      var yes=vr.yes_count,no=vr.no_count,abstain=vr.abstain_count,total=vr.total_votes;
  var hasShares=yes!=null&&no!=null&&abstain!=null&&total!=null;
      var yesPct=hasShares ? vr.yes_percent : null;
      var noPct=hasShares ? vr.no_percent : null;
      var h='';
      if(hasShares&&total>0){
        h+='<div class="bar-wrap"><div class="bar-yes" style="width:'+Math.max(yesPct,5)+'%">'+yesPct+'%</div><div class="bar-no" style="width:'+Math.max(noPct,5)+'%">'+noPct+'%</div></div>';
        h+='<div class="stats">'+total+' '+(el?'ψήφοι':'votes')+'</div>';
      }
      if(!hasShares)h='<div class="stats">—</div><div class="stats">'+(total==null?'—':total)+' '+(el?'ψήφοι':'votes')+'</div>';
      resultsEl.innerHTML=h;
    }
  }catch(e){}
}

function render(b,vr){
  var yes=vr.yes_count,no=vr.no_count,abstain=vr.abstain_count,total=vr.total_votes;
  var hasShares=yes!=null&&no!=null&&abstain!=null&&total!=null;
  var yesPct=hasShares ? vr.yes_percent : null;
  var noPct=hasShares ? vr.no_percent : null;
  var st=b.status||'ANNOUNCED';
  var sc={'ACTIVE':'status-active','ANNOUNCED':'status-announced','PARLIAMENT_VOTED':'status-voted','OPEN_END':'status-open','WINDOW_24H':'status-active'};
  var sl={'ACTIVE':el?'Ανοιχτή':'Active','ANNOUNCED':el?'Ανακοινώθηκε':'Announced','PARLIAMENT_VOTED':el?'Ψηφίστηκε':'Voted','OPEN_END':el?'Αρχείο':'Archive','WINDOW_24H':el?'24ω':'24h'};
  var votable=st==='ACTIVE'||st==='WINDOW_24H';
  var h='<span class="status '+(sc[st]||'status-announced')+'">'+(sl[st]||st)+'</span>';
  h+='<div class="title">'+(b.title_el||b.title_en||billId)+'</div>';
  if(b.pill_el)h+='<div class="pill">'+b.pill_el+'</div>';

  if(votable){
    // Auth bar + QR iframe + vote buttons
    h+='<div id="auth-bar" class="auth-bar">'+(el?'🔐 Σκανάρετε το QR code με την εφαρμογή ekklesia.gr για ταυτοποίηση':'🔐 Scan the QR code with the ekklesia.gr app to authenticate')+'</div>';
    h+='<iframe id="qr-frame" class="qr-frame" src="qr-login.html?purpose=vote&bill_id='+encodeURIComponent(billId)+'"></iframe>';
    h+='<div id="vote-area"><div class="btns">';
    h+='<button class="btn btn-yes vote-btn" disabled data-csp-click="embed-vote" data-choice="YES">'+(el?'ΝΑΙ':'YES')+'</button>';
    h+='<button class="btn btn-no vote-btn" disabled data-csp-click="embed-vote" data-choice="NO">'+(el?'ΟΧΙ':'NO')+'</button>';
    h+='<button class="btn btn-abstain vote-btn" disabled data-csp-click="embed-vote" data-choice="ABSTAIN">'+(el?'ΑΠΟΧΗ':'ABSTAIN')+'</button>';
    h+='</div></div>';
  }

  h+='<div id="results-area">';
  if(hasShares&&total>0){
    h+='<div class="bar-wrap"><div class="bar-yes" style="width:'+Math.max(yesPct,5)+'%">'+yesPct+'%</div><div class="bar-no" style="width:'+Math.max(noPct,5)+'%">'+noPct+'%</div></div>';
    h+='<div class="stats">'+total+' '+(el?'ψήφοι':'votes')+'</div>';
  }else if(!hasShares){
    h+='<div class="stats">—</div><div class="stats">'+(total==null?"—":total)+' '+(el?'ψήφοι':'votes')+'</div>';
  }else{
    h+='<div class="stats">'+(el?'Δεν υπάρχουν ψήφοι ακόμα':'No votes yet')+'</div>';
  }
  h+='</div>';

  h+='<div class="attr">'+(el?'Πηγή':'Source')+': <a href="https://ekklesia.gr" target="_blank">ekklesia.gr</a> · <a href="https://ekklesia.gr/el/bills/'+encodeURIComponent(billId)+'" target="_blank">'+(el?'Λεπτομέρειες':'Details')+'</a></div>';
  document.getElementById('widget').innerHTML=h;
}
load();
setInterval(loadResults,60000);

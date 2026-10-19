
var API=window.API_BASE||'https://api.ekklesia.gr';
var token=window.REP_TOKEN||localStorage.getItem('rep_token')||'';
var adaNumber=localStorage.getItem('rep_ada')||'';

function esc(s){return String(s==null?'':s).replace(/[&<>"']/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]})}
function num(v,d){var n=Number(v);return isFinite(n)?n:(d||0)}

document.getElementById('billsList').addEventListener('click',function(e){
  var card=e.target.closest('.bill-card[data-billid]');
  if(card)loadResults(card.getAttribute('data-billid'));
});

if(token)showBillsScreen();

async function doLogin(){
  var ada=document.getElementById('adaInput').value.trim();
  var invite=document.getElementById('inviteInput').value.trim();
  if(!ada){showError('Εισάγετε αριθμό ΑΔΑ');return}
  if(!invite){showError('Εισάγετε κωδικό πρόσκλησης');return}
  document.getElementById('loginBtn').textContent='Επαλήθευση...';
  document.getElementById('loginBtn').disabled=true;
  try{
    var r=await fetch(API+'/api/v1/rep/verify',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({ada_number:ada,invite_code:invite})});
    var d=await r.json();
    if(!r.ok){showError(d.detail||'Σφάλμα επαλήθευσης');return}
    token=d.token;adaNumber=ada;
    localStorage.setItem('rep_token',token);if(window.postToNative)window.postToNative('SAVE_TOKEN',token);
    localStorage.setItem('rep_ada',ada);
    localStorage.setItem('rep_role',d.role||'');
    localStorage.setItem('rep_region',d.region||'');
    localStorage.setItem('rep_municipality',d.municipality||'');
    localStorage.setItem('rep_org_label',d.org_label||'');
    showBillsScreen();
  }catch(e){showError('Σφάλμα δικτύου')}
  finally{document.getElementById('loginBtn').textContent='Επαλήθευση';document.getElementById('loginBtn').disabled=false}
}

function showError(msg){var e=document.getElementById('loginError');e.textContent=msg;e.style.display='block';setTimeout(function(){e.style.display='none'},5000)}

async function showBillsScreen(){
  document.getElementById('loginScreen').style.display='none';
  document.getElementById('billsScreen').style.display='block';
  document.getElementById('navBar').style.display='flex';
  document.getElementById('repBadge').style.display='inline';
  var repRole=localStorage.getItem('rep_role')||'';
  var repRegion=localStorage.getItem('rep_region')||'';
  var repMuni=localStorage.getItem('rep_municipality')||'';
  var repOrg=localStorage.getItem('rep_org_label')||'';
  var roleInfo=repRole;
  if(repRegion)roleInfo+=' · '+repRegion;
  if(repMuni)roleInfo+=' · '+repMuni;
  document.getElementById('repBadge').textContent=roleInfo||'Επαληθευμένος';
  loadBills();
}

async function loadBills(){
  try{
    var r=await fetch(API+'/api/v1/rep/bills',{headers:{'Authorization':'Bearer '+token}});
    if(r.status===401){doLogout();return}
    var bills=await r.json();
    var html='';    if(!bills.length)html='<p style="color:var(--gray);text-align:center">Δεν υπάρχουν διαθέσιμες ψηφοφορίες</p>';
    bills.forEach(function(b){
      var sc={'WINDOW_24H':'status-window','PARLIAMENT_VOTED':'status-voted','OPEN_END':'status-open'};
      var sl={'WINDOW_24H':'24ω Παράθυρο','PARLIAMENT_VOTED':'Ψηφίστηκε','OPEN_END':'Αρχείο'};
      html+='<div class="bill-card" data-billid="'+esc(b.id)+'">';
      html+='<span class="status '+(sc[b.status]||'')+'">'+(sl[b.status]||esc(b.status))+'</span>';
      html+='<h3>'+esc(b.title_el)+'</h3>';
      var srcBadge=b.source==='DIAVGEIA'?' <span style="font-size:9px;background:#e0f2fe;color:#0369a1;padding:1px 5px;border-radius:4px;font-weight:700">ΔΙΑΥΓΕΙΑ</span>':'';
      html+='<div class="meta">'+esc(b.id)+' · '+esc(b.governance_level||'NATIONAL')+srcBadge+'</div>';
      if(num(b.consensus_count)>0)html+='<div class="meta" style="color:#a855f7">⚖️ Συναίνεση: '+(num(b.consensus_score)>0?'+':'')+num(b.consensus_score).toFixed(1)+' ('+num(b.consensus_count)+' ψήφοι)</div>';
      html+='</div>';
    });
    document.getElementById('billsList').innerHTML=html;
  }catch(e){document.getElementById('billsList').innerHTML='<p style="color:var(--red)">Σφάλμα φόρτωσης</p>'}
}

async function loadResults(billId){
  document.getElementById('billsList').innerHTML='<div class="loading">Φόρτωση αποτελεσμάτων...</div>';
  try{
    var r=await fetch(API+'/api/v1/rep/results/'+encodeURIComponent(billId),{headers:{'Authorization':'Bearer '+token}});
    var d=await r.json();
    var yesPct=num(d.yes_pct),noPct=num(d.no_pct);
    var html='<button class="btn btn-outline" data-csp-click="load-bills" style="margin-bottom:16px">← Πίσω</button>';
    html+='<div class="bill-card"><h3>'+esc(d.title_el)+'</h3>';
    if(num(d.total)>0){
      var yesLabel=yesPct>=5?yesPct+'%':'';
      var noLabel=noPct>=5?noPct+'%':'';
      html+='<div class="bar-wrap"><div class="bar-yes" style="width:'+Math.max(yesPct,3)+'%">'+yesLabel+'</div><div class="bar-no" style="width:'+Math.max(noPct,3)+'%">'+noLabel+'</div></div>';
      html+='<div class="votes-label">'+num(d.total)+' ψήφοι πολιτών</div>';
    }else{
      html+='<div class="empty-state">Δεν υπάρχουν ψήφοι πολιτών ακόμα</div>';
    }
    if(d.party_votes){html+='<div style="margin-top:12px;font-size:12px;color:var(--gray)"><strong>Κόμματα:</strong> ';for(var p in d.party_votes)html+=esc(p)+':'+num(d.party_votes[p])+' ';html+='</div>'}
    if(num(d.consensus_count)>0)html+='<div style="margin-top:8px;font-size:12px;color:#a855f7">⚖️ Συναίνεση: '+(num(d.consensus_score)>0?'+':'')+num(d.consensus_score).toFixed(1)+' ('+num(d.consensus_count)+')</div>';
    html+='</div>';
    document.getElementById('billsList').innerHTML=html;
  }catch(e){document.getElementById('billsList').innerHTML='<p style="color:var(--red)">Σφάλμα</p>'}
}

function showBills(){
  document.getElementById('billsScreen').style.display='block';
  document.getElementById('evalScreen').style.display='none';
  document.getElementById('navBills').classList.add('active');
  document.getElementById('navEval').classList.remove('active');
  loadBills();
}
function showEval(){
  document.getElementById('billsScreen').style.display='none';
  document.getElementById('evalScreen').style.display='block';
  document.getElementById('navBills').classList.remove('active');
  document.getElementById('navEval').classList.add('active');
  loadEvalScreen();
}
async function loadEvalScreen(){
  var el=document.getElementById('evalContent');
  el.innerHTML='<div class="loading">Φόρτωση...</div>';
  try{
    // Check if evaluation is enabled via my-scores (returns data if token is valid)
    var r=await fetch(API+'/api/v1/rep/my-scores',{headers:{'Authorization':'Bearer '+token}});
    if(r.status===401){doLogout();return}
    var d=await r.json();
    var html='';
    // Check enable status
    var sr=await fetch(API+'/api/v1/politicians/'+encodeURIComponent(adaNumber)+'/questions');
    var enabled=sr.ok;
    if(!enabled){
      html+='<div class="eval-consent">';
      html+='<p style="color:#e2e8f0;font-size:14px;margin-bottom:16px">Ενεργοποιήστε την αξιολόγηση για να μπορούν οι επαληθευμένοι πολίτες να σας αξιολογήσουν.</p>';
      html+='<label><input type="checkbox" id="evalConsent"> Συμφωνώ να αξιολογηθώ από επαληθευμένους πολίτες</label>';
      html+='<button class="btn btn-gold" data-csp-click="enable-evaluation" id="evalEnableBtn">Ενεργοποίηση Αξιολόγησης</button>';
      html+='</div>';
    }else{
      html+='<div class="eval-status">✓ Αξιολόγηση ενεργή</div>';
      if(d.total_evaluations>0||d.scores_hidden){
        if(d.scores_hidden){
          html+='<div style="text-align:center;margin-bottom:16px;font-size:13px;color:var(--gray)">Οι βαθμολογίες εμφανίζονται από '+num(d.minimum_group_size)+' αξιολογητές.</div>';
        }
        html+='<div style="text-align:center;margin-bottom:16px;font-size:13px;color:var(--gray)">Συνολικός μέσος όρος: <strong style="color:var(--gold);font-size:18px">'+(d.total_avg!==null&&d.total_avg!==undefined?(num(d.total_avg)>0?'+':'')+num(d.total_avg):'—')+'</strong></div>';
        d.questions.forEach(function(q){
          html+='<div class="score-card">';
          html+='<div class="score-row">';
          html+='<div class="score-main">';
          html+='<div class="cat">'+esc(q.category)+'</div>';
          html+='<div class="q">'+esc(q.question_el)+'</div>';
          html+='<div class="cnt">'+(q.vote_count_hidden?'Λιγότερες από '+num(d.minimum_group_size)+' αξιολογήσεις':num(q.vote_count)+' Αξιολογήσεις')+'</div>';
          html+='</div>';
          html+='<div class="val">'+(q.avg_score!==null&&q.avg_score!==undefined?(num(q.avg_score)>0?'+':'')+num(q.avg_score):'—')+'</div>';
          html+='</div>';
          html+='</div>';
        });
      }else{
        html+='<p style="color:var(--gray);text-align:center;font-size:14px;margin-top:16px">Δεν υπάρχουν Αξιολογήσεις ακόμα.</p>';
      }
    }
    el.innerHTML=html;
  }catch(e){el.innerHTML='<p style="color:var(--red)">Σφάλμα φόρτωσης</p>'}
}
async function enableEvaluation(){
  var cb=document.getElementById('evalConsent');
  if(!cb||!cb.checked){alert('Πρέπει να συμφωνήσετε πρώτα.');return}
  var btn=document.getElementById('evalEnableBtn');
  btn.textContent='Ενεργοποίηση...';btn.disabled=true;
  try{
    var r=await fetch(API+'/api/v1/rep/enable-evaluation',{method:'POST',headers:{'Authorization':'Bearer '+token,'Content-Type':'application/json'}});
    if(!r.ok){var d=await r.json();alert(d.detail||'Σφάλμα');return}
    loadEvalScreen();
  }catch(e){alert('Σφάλμα δικτύου')}
  finally{btn.textContent='Ενεργοποίηση Αξιολόγησης';btn.disabled=false}
}
function confirmLogout(){document.getElementById('logoutModal').style.display='flex'}
function closeLogoutModal(){document.getElementById('logoutModal').style.display='none'}
function doLogout(){token='';adaNumber='';localStorage.removeItem('rep_token');localStorage.removeItem('rep_ada');if(window.postToNative)window.postToNative('LOGOUT','');location.reload()}

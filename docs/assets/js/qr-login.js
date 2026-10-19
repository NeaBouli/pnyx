
var API='https://api.ekklesia.gr';
var sessionId=null;
var pollTimer=null;
var countdownTimer=null;
var ttl=300;
var remaining=0;

function getParams(){
  var p=new URLSearchParams(window.location.search);
  return{purpose:p.get('purpose')||'ticket',bill_id:p.get('bill_id')||null};
}

function show(id){document.getElementById(id).classList.remove('hidden')}
function hide(id){document.getElementById(id).classList.add('hidden')}

async function startSession(){
  // Reset UI
  hide('status-success');hide('status-expired');hide('btn-refresh');
  show('status-pending');
  document.getElementById('qr-container').innerHTML='';
  document.getElementById('timer').textContent='';

  var params=getParams();
  var url=API+'/api/v1/polis/qr-session?purpose='+params.purpose;
  if(params.bill_id)url+='&bill_id='+encodeURIComponent(params.bill_id);

  try{
    var r=await fetch(url);
    var d=await r.json();
    if(!r.ok){
      hide('status-pending');
      // API detail is remote data: render as text, never as HTML.
      var errP=document.createElement('p');
      errP.style.cssText='color:#dc2626;font-size:0.85rem';
      errP.textContent=(typeof d.detail==='string'&&d.detail)?d.detail:('API Error '+r.status);
      document.getElementById('qr-container').replaceChildren(errP);
      show('btn-refresh');
      return;
    }
    sessionId=d.session_id;
    ttl=d.ttl||300;
    remaining=ttl;

    // Render QR
    new QRCode(document.getElementById('qr-container'),{
      text:d.qr_data,
      width:200,height:200,
      colorDark:'#0f172a',colorLight:'#ffffff',
      correctLevel:QRCode.CorrectLevel.M
    });

    // Start polling
    if(pollTimer)clearInterval(pollTimer);
    pollTimer=setInterval(pollSession,2000);

    // Start countdown
    if(countdownTimer)clearInterval(countdownTimer);
    countdownTimer=setInterval(updateCountdown,1000);
    updateCountdown();
  }catch(e){
    document.getElementById('qr-container').innerHTML='<p style="color:#dc2626">Σφάλμα φόρτωσης</p>';
  }
}

async function pollSession(){
  if(!sessionId)return;
  try{
    var r=await fetch(API+'/api/v1/polis/qr-session/'+sessionId);
    var d=await r.json();

    if(d.status==='authenticated'){
      clearInterval(pollTimer);clearInterval(countdownTimer);
      hide('status-pending');hide('status-expired');hide('btn-refresh');
      show('status-success');
      document.getElementById('timer').textContent='';

      // Callback to parent (iframe embed)
      if(window.parent!==window){
        window.parent.postMessage({type:'ekklesia-qr-auth',status:'authenticated',
          session_id:sessionId,
          nullifier_hash:d.nullifier_hash,public_key_hex:d.public_key_hex,
          purpose:d.purpose,bill_id:d.bill_id},'*');
      }
    }else if(d.status==='expired'){
      onExpired();
    }
  }catch(e){}
}

function updateCountdown(){
  remaining--;
  if(remaining<=0){onExpired();return}
  var m=Math.floor(remaining/60);
  var s=remaining%60;
  document.getElementById('timer').textContent=m+':'+(s<10?'0':'')+s+' απομένουν';
}

function onExpired(){
  clearInterval(pollTimer);clearInterval(countdownTimer);
  hide('status-pending');show('status-expired');show('btn-refresh');
  document.getElementById('timer').textContent='';
  document.getElementById('qr-container').style.opacity='0.3';
}

// Auto-start
startSession();

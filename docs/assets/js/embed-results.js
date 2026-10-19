
var API='https://api.ekklesia.gr';
var params=new URLSearchParams(window.location.search);
var billId=params.get('bill_id')||params.get('bill')||'';
var lang=params.get('lang')||'el';
var el=lang==='el';

async function load(){
  if(!billId){document.getElementById('loader').className='error';document.getElementById('loader').textContent=el?'Λείπει bill_id':'Missing bill_id';return}
  try{
    var r=await fetch(API+'/api/v1/bills/'+billId);
    if(!r.ok)throw new Error(r.status);
    var b=await r.json();
    var vr=await fetch(API+'/api/v1/vote/'+billId+'/results').then(function(x){return x.json()}).catch(function(){return{}});
    render(b,vr);
  }catch(e){document.getElementById('loader').className='error';document.getElementById('loader').textContent=(el?'Νομοσχέδιο δεν βρέθηκε: ':'Bill not found: ')+billId}
}

function render(b,vr){
  var yes=vr.yes_count,no=vr.no_count,abstain=vr.abstain_count,total=vr.total_votes;
  var hasShares=yes!=null&&no!=null&&abstain!=null&&total!=null;
  var yesPct=hasShares ? vr.yes_percent : null;
  var noPct=hasShares ? vr.no_percent : null;
  var absPct=hasShares ? vr.abstain_percent : null;

  var h='<div class="title">'+(b.title_el||b.title_en||billId)+'</div>';

  // Vote bars
  if(hasShares){
  h+='<div class="row"><div class="label" style="color:#22c55e">'+(el?'ΝΑΙ':'YES')+'</div><div class="bar-bg"><div class="bar bar-yes" style="width:'+Math.max(yesPct,2)+'%">'+yes+'</div></div><div class="pct" style="color:#22c55e">'+yesPct+'%</div></div>';
  h+='<div class="row"><div class="label" style="color:#ef4444">'+(el?'ΟΧΙ':'NO')+'</div><div class="bar-bg"><div class="bar bar-no" style="width:'+Math.max(noPct,2)+'%">'+no+'</div></div><div class="pct" style="color:#ef4444">'+noPct+'%</div></div>';
  if(abstain>0)h+='<div class="row"><div class="label" style="color:#94a3b8">'+(el?'ΑΠΟΧΗ':'ABS')+'</div><div class="bar-bg"><div class="bar bar-abs" style="width:'+Math.max(absPct,2)+'%">'+abstain+'</div></div><div class="pct" style="color:#94a3b8">'+absPct+'%</div></div>';

  }else{h+='<div class="total">—</div>';}
  h+='<div class="total">'+(total==null?"—":total)+' '+(el?'ψήφοι πολιτών':'citizen votes')+'</div>';

  // Parliament result
  var pv=b.party_votes_parliament;
  if(pv&&Object.keys(pv).length>0){
    var parlYes=0,parlNo=0;
    for(var p in pv){if(pv[p]==='ΝΑΙ'||pv[p]==='YES')parlYes++;if(pv[p]==='ΟΧΙ'||pv[p]==='NO')parlNo++}
    var parlResult=parlYes>=parlNo?(el?'ΕΓΚΡΙΘΗΚΕ':'APPROVED'):(el?'ΑΠΟΡΡΙΦΘΗΚΕ':'REJECTED');
    var parlColor=parlYes>=parlNo?'#22c55e':'#ef4444';
    h+='<div class="parl"><div class="parl-title">'+(el?'Αποτέλεσμα Βουλής':'Parliament Result')+'</div><div class="parl-result" style="color:'+parlColor+'">'+parlResult+' ('+parlYes+'/'+parlNo+')</div></div>';

    // Divergence
    if(hasShares&&total>0){
      var citizenYesPct=yesPct;
      var parlYesPct=Math.round(parlYes/(parlYes+parlNo)*100);
      var divergence=Math.abs(citizenYesPct-parlYesPct);
      h+='<div class="div-wrap"><div class="div-title">'+(el?'Δείκτης Απόκλισης':'Divergence Score')+'</div><div class="div-bar"><div class="div-fill" style="width:'+divergence+'%"></div></div><div class="div-label">'+divergence+'%</div></div>';
    }
  }

  if(total===0)h+='<div style="text-align:center;color:#94a3b8;font-size:13px;margin:16px 0">'+(el?'Δεν υπάρχουν ψήφοι ακόμα':'No votes yet')+'</div>';

  h+='<div class="attr">'+(el?'Πηγή':'Source')+': <a href="https://ekklesia.gr" target="_blank">ekklesia.gr</a> · <a href="https://ekklesia.gr/el/results" target="_blank">'+(el?'Όλα τα αποτελέσματα':'All results')+'</a></div>';
  document.getElementById('widget').innerHTML=h;
}
load();
setInterval(load,60000);


var API='https://api.ekklesia.gr';
var params=new URLSearchParams(window.location.search);
var billId=params.get('bill_id')||params.get('bill')||'';
var lang=params.get('lang')||'el';
var el=lang==='el';

async function load(){
  if(!document.getElementById('widget') || !document.getElementById('loader')) return;
  if(!billId){document.getElementById('loader').className='error';document.getElementById('loader').textContent=el?'Λείπει bill_id':'Missing bill_id';return}
  try{
    var r=await fetch(API+'/api/v1/bills/'+encodeURIComponent(billId));
    if(!r.ok)throw new Error(r.status);
    var b=await r.json();
    var vr=await fetch(API+'/api/v1/vote/'+encodeURIComponent(billId)+'/results').then(function(x){return x.json()}).catch(function(){return{}});
    render(b,vr);
  }catch(e){document.getElementById('loader').className='error';document.getElementById('loader').textContent=(el?'Νομοσχέδιο δεν βρέθηκε: ':'Bill not found: ')+billId}
}

function render(b,vr){
  var widget = document.getElementById('widget');
  if (!widget) return;
  widget.replaceChildren();
  var v = EmbedUI.votes(vr);
  EmbedUI.node(widget, 'div', 'title', b.title_el || b.title_en || billId);
  if (v.hasShares) {
    [[el?'ΝΑΙ':'YES', 'yes', v.yes, v.yesPct, '#22c55e'],
     [el?'ΟΧΙ':'NO', 'no', v.no, v.noPct, '#ef4444'],
     [el?'ΑΠΟΧΗ':'ABS', 'abs', v.abstain, v.absPct, '#94a3b8']].forEach(function(item) {
      if (item[1] === 'abs' && item[2] === 0) return;
      var row = EmbedUI.node(widget, 'div', 'row');
      EmbedUI.node(row, 'div', 'label', item[0]).style.color = item[4];
      var bg = EmbedUI.node(row, 'div', 'bar-bg');
      EmbedUI.width(EmbedUI.node(bg, 'div', 'bar bar-' + item[1], item[2]), item[3], 2);
      EmbedUI.node(row, 'div', 'pct', item[3] + '%').style.color = item[4];
    });
  } else EmbedUI.node(widget, 'div', 'total', '—');
  EmbedUI.node(widget, 'div', 'total', (v.total == null ? '—' : v.total) + (el?' ψήφοι πολιτών':' citizen votes'));
  var pv = b.party_votes_parliament;
  if (pv && typeof pv === 'object' && Object.keys(pv).length) {
    var parlYes = 0, parlNo = 0;
    Object.keys(pv).forEach(function(p) {
      if (pv[p] === 'ΝΑΙ' || pv[p] === 'YES') parlYes++;
      if (pv[p] === 'ΟΧΙ' || pv[p] === 'NO') parlNo++;
    });
    var parl = EmbedUI.node(widget, 'div', 'parl');
    EmbedUI.node(parl, 'div', 'parl-title', el?'Αποτέλεσμα Βουλής':'Parliament Result');
    var label = parlYes >= parlNo ? (el?'ΕΓΚΡΙΘΗΚΕ':'APPROVED') : (el?'ΑΠΟΡΡΙΦΘΗΚΕ':'REJECTED');
    EmbedUI.node(parl, 'div', 'parl-result', label + ' (' + parlYes + '/' + parlNo + ')').style.color = parlYes >= parlNo ? '#22c55e' : '#ef4444';
    if (v.hasShares && v.total > 0 && parlYes + parlNo > 0) {
      var divergence = Math.abs(v.yesPct - Math.round(parlYes / (parlYes + parlNo) * 100));
      var div = EmbedUI.node(widget, 'div', 'div-wrap');
      EmbedUI.node(div, 'div', 'div-title', el?'Δείκτης Απόκλισης':'Divergence Score');
      EmbedUI.width(EmbedUI.node(EmbedUI.node(div, 'div', 'div-bar'), 'div', 'div-fill'), divergence);
      EmbedUI.node(div, 'div', 'div-label', divergence + '%');
    }
  }
  if (v.total === 0) EmbedUI.node(widget, 'div', 'total', el?'Δεν υπάρχουν ψήφοι ακόμα':'No votes yet');
  EmbedUI.attribution(widget, el, 'https://ekklesia.gr/el/results', el?'Όλα τα αποτελέσματα':'All results');
}
load();
setInterval(load,60000);


var html = "";
DEMO_BILLS.forEach(function(b) {
  var s = DEMO_STATUS[b.status] || DEMO_STATUS.ACTIVE;
  var actions = b.status === "ANNOUNCED" ? '<button class="btn btn-blue" style="font-size:11px;padding:4px 10px" data-csp-click="demo-activate">→ ACTIVE</button>' : '';
  html += '<div class="bill-row"><span class="status-dot" style="background:' + s.color + '"></span><span class="title">' + b.id + ' — ' + b.title_el.substring(0,40) + '</span><span style="font-size:11px;font-weight:700;color:' + s.color + '">' + s.el + '</span>' + actions + '</div>';
});
document.getElementById("adminBills").innerHTML = html;

function createBill() {
  var title = document.getElementById("newTitle").value;
  if (!title) { alert("Τίτλος απαιτείται"); return; }
  alert("Demo: Ψηφοφορία '" + title + "' θα δημιουργηθεί.\n\nΣε πραγματική node:\n→ POST /api/v1/admin/bills\n→ Αυτόματο Forum topic\n→ Telegram ειδοποίηση\n→ Status: ANNOUNCED");
  document.getElementById("newTitle").value = "";
  document.getElementById("newDesc").value = "";
}

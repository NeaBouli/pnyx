// CSP-safe listeners for literal and generated docs controls. No eval or string handlers.
(function () {
  "use strict";
  var actions = {
    "action-026b9b59be": function (event) { navigator.clipboard.writeText(document.getElementById('embed-single').innerText) },
    "action-8b034e181d": function (event) { document.getElementById('pwaModal').style.display='none' },
    "action-9c7de49086": function (event) { navigator.clipboard.writeText(document.getElementById('embed-all').innerText) },
    "action-b11ca2513e": function (event) { document.getElementById('phaseBModal').style.display='none' },
    "chat-enter": function (event) { if(event.key==='Enter')sendChat() },
    "close-legal-modal": function (event) { closeLegalModal() },
    "close-logout-modal": function (event) { closeLogoutModal() },
    "close-mobile-detail": function (event) { closeMobileDetail() },
    "close-ngo-modal": function (event) { closeNgoModal() },
    "close-share-popup": function (event) { closeSharePopup() },
    "close-ticket-modal": function (event) { closeTicketModal() },
    "confirm-logout": function (event) { confirmLogout() },
    "copy-mirror-command": function (event) { navigator.clipboard.writeText('curl -fsSL https://ekklesia.gr/mirror-setup.sh | sudo bash') },
    "copy-share-link": function (event) { copyShareLink() },
    "create-bill": function (event) { createBill() },
    "detail-backdrop": function (event) { if(event.target===this)closeMobileDetail() },
    "do-login": function (event) { doLogin() },
    "do-logout": function (event) { doLogout() },
    "filter-by-cat-this": function (event) { filterByCat(this,'') },
    "filter-by-status-this": function (event) { filterByStatus(this,'') },
    "filter-by-status-this-status-claimed": function (event) { filterByStatus(this,'status:claimed') },
    "filter-by-status-this-status-open": function (event) { filterByStatus(this,'status:open') },
    "filter-by-status-this-status-pending": function (event) { filterByStatus(this,'status:pending') },
    "filter-by-status-this-status-resolved": function (event) { filterByStatus(this,'status:resolved') },
    "hide-backdrop": function (event) { if(event.target===this)this.style.display='none' },
    "legal-backdrop": function (event) { if(event.target===this)closeLegalModal() },
    "load-more-tickets": function (event) { loadMoreTickets() },
    "open-legal-modal-delete-link": function (event) { openLegalModal('delete');return false },
    "open-legal-modal-privacy-link": function (event) { openLegalModal('privacy');return false },
    "open-new-ticket-modal": function (event) { return requestNewTicket(event) },
    "open-ngo-modal": function (event) { openNgoModal() },
    "open-ngo-modal-link": function (event) { openNgoModal();return false; },
    "open-qrlogin": function (event) { openQRLogin() },
    "open-share-popup-link": function (event) { openSharePopup();return false; },
    "retry-auth": function (event) { retryAuth() },
    "scroll-finance": function (event) { document.getElementById('finance').scrollIntoView({behavior:'smooth'});return false; },
    "send-chat": function (event) { sendChat() },
    "show-bills": function (event) { showBills() },
    "show-eval": function (event) { showEval() },
    "sort-by-this-newest": function (event) { sortBy(this,'newest') },
    "sort-by-this-oldest": function (event) { sortBy(this,'oldest') },
    "sort-by-this-votes": function (event) { sortBy(this,'votes') },
    "start-session": function (event) { startSession() },
    "style-013d9e1cb7": function (event) { this.style.borderColor='#3b82f6';this.style.opacity='1' },
    "style-4d3ef53da6": function (event) { this.style.borderColor='#22c55e' },
    "style-6859f3b26b": function (event) { this.style.background='#2563eb' },
    "style-6d4f2e8a0d": function (event) { this.style.borderColor='#3b82f6' },
    "style-702518e1a0": function (event) { this.style.background='#1d4ed8' },
    "style-7145038575": function (event) { this.style.borderColor='#334155';this.style.opacity='0.8' },
    "style-80ec2adaee": function (event) { this.style.background='transparent' },
    "style-902225600f": function (event) { this.style.transform='none' },
    "style-ab0b586fec": function (event) { this.style.transform='translateY(-2px)' },
    "style-b248670bf6": function (event) { this.style.opacity='1' },
    "style-baa92d39b2": function (event) { this.style.background='#eff6ff' },
    "style-bc80a8e99e": function (event) { this.style.borderColor='#2563eb';this.style.transform='translateY(-2px)' },
    "style-c7711d8057": function (event) { this.style.transform='scale(1)' },
    "style-d0bd26b364": function (event) { this.style.opacity='0.85' },
    "style-eecca39034": function (event) { this.style.borderColor='#22c55e';this.style.transform='none' },
    "style-fa19897072": function (event) { this.style.transform='scale(1.1)' },
    "submit-newsletter-event": function (event) { submitNewsletter(event) },
    "submit-ngo-form-event": function (event) { submitNgoForm(event) },
    "submit-ticket-form-event": function (event) { submitTicketForm(event) },
    "switch-hlr-tab-fallback": function (event) { switchHlrTab('fallback') },
    "switch-hlr-tab-primary": function (event) { switchHlrTab('primary') },
    "toggle-chat": function (event) { toggleChat() },
    "toggle-language": function (event) { toggleLang() },
    "toggle-parent": function (event) { this.parentElement.classList.toggle('open') },
    "toggle-polis-language": function (event) { setPolisLang(polisLang==='el'?'en':'el');if (document.getElementById('langBtn')) document.getElementById('langBtn').textContent=polisLang==='el'?'EN':'ΕΛ' },
    "toggle-section": function (event) { toggleSection(this) },
    "demo-activate": function (event) { alert('Demo: Bill würde auf ACTIVE gesetzt') },
    "demo-filter": function (event) { setFilter(this.dataset.value) },
    "demo-vote": function (event) { castVote(this.dataset.bill, this.dataset.choice) },
    "demo-score": function (event) { document.getElementById('sv_' + this.dataset.bill).textContent = this.value > 0 ? '+' + this.value : this.value },
    "demo-consensus": function (event) { castConsensus(this.dataset.bill) },
    "embed-vote": function (event) { castVote(this.dataset.choice) },
    "filter-category": function (event) { filterByCat(this, this.dataset.value) },
    "load-bills": function (event) { loadBills() },
    "enable-evaluation": function (event) { enableEvaluation() },
    "login": function (event) { login() },
    "select-ticket": function (event) { selectTicket(Number(this.dataset.number)) },
    "toggle-vote-stop": function (event) { event.stopPropagation(); toggleVote(Number(this.dataset.number)) },
    "toggle-vote": function (event) { toggleVote(Number(this.dataset.number)) },
    "claim-ticket": function (event) { doClaim(Number(this.dataset.number)) },
    "load-and-render": function (event) { loadAndRender() },
    "close-qr-login": function () { closeQRLogin() },
  };
  function dispatch(event) {
    var node = event.target;
    while (node && node.getAttribute) {
      var action = node.getAttribute("data-csp-" + event.type);
      if (Object.prototype.hasOwnProperty.call(actions, action)) {
        if (actions[action].call(node, event) === false) event.preventDefault();
        break;
      }
      if (event.cancelBubble || event.type === "mouseenter" || event.type === "mouseleave") break;
      node = node.parentElement;
    }
  }
  ["click", "submit", "keydown", "input", "mouseover", "mouseout"].forEach(function (type) {
    document.addEventListener(type, dispatch);
  });
  ["mouseenter", "mouseleave"].forEach(function (type) {
    document.addEventListener(type, dispatch, true);
  });
})();

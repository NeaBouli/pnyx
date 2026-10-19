// API values enter the widget only through textContent or finite numeric styles.
var EmbedUI = (function () {
  function node(parent, tag, className, text) {
    var element = document.createElement(tag);
    element.className = className || '';
    if (text != null) element.textContent = String(text);
    parent.appendChild(element);
    return element;
  }
  function number(value) {
    return typeof value === 'number' && Number.isFinite(value) && value >= 0 ? value : null;
  }
  function votes(data) {
    var yes = number(data.yes_count), no = number(data.no_count);
    var abstain = number(data.abstain_count), total = number(data.total_votes);
    var yesPct = number(data.yes_percent), noPct = number(data.no_percent), absPct = number(data.abstain_percent);
    return { yes: yes, no: no, abstain: abstain, total: total, yesPct: yesPct, noPct: noPct, absPct: absPct,
      hasShares: [yes, no, abstain, total, yesPct, noPct, absPct].every(function (v) { return v !== null; }) };
  }
  function width(element, percent, minimum) {
    element.style.width = Math.min(100, Math.max(percent, minimum || 0)) + '%';
  }
  function results(parent, data, greek) {
    var v = votes(data);
    parent.replaceChildren();
    if (v.hasShares && v.total > 0) {
      var bars = node(parent, 'div', 'bar-wrap');
      width(node(bars, 'div', 'bar-yes', v.yesPct + '%'), v.yesPct, 5);
      width(node(bars, 'div', 'bar-no', v.noPct + '%'), v.noPct, 5);
      node(parent, 'div', 'stats', v.total + (greek ? ' ψήφοι' : ' votes'));
    } else if (!v.hasShares) {
      node(parent, 'div', 'stats', '—');
      node(parent, 'div', 'stats', (v.total == null ? '—' : v.total) + (greek ? ' ψήφοι' : ' votes'));
    } else {
      node(parent, 'div', 'stats', greek ? 'Δεν υπάρχουν ψήφοι ακόμα' : 'No votes yet');
    }
  }
  function attribution(parent, greek, href, label) {
    var attr = node(parent, 'div', 'attr', (greek ? 'Πηγή' : 'Source') + ': ');
    var source = node(attr, 'a', '', 'ekklesia.gr');
    source.href = 'https://ekklesia.gr'; source.target = '_blank'; source.rel = 'noopener';
    node(attr, 'span', '', ' · ');
    var link = node(attr, 'a', '', label);
    link.href = href; link.target = '_blank'; link.rel = 'noopener';
  }
  return { node: node, votes: votes, width: width, results: results, attribution: attribution };
}());

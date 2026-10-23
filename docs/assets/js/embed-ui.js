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
  function parliamentUrl(value) {
    if (!value || !/^https:\/\//i.test(value) || /[\\\s\u0000-\u001f\u007f]/.test(value)) return null;
    try {
      var url = new URL(value), authority = value.slice('https://'.length).split(/[/?#]/)[0];
      if (url.protocol !== 'https:'
        || ['www.hellenicparliament.gr', 'hellenicparliament.gr'].indexOf(url.hostname) < 0
        || url.username || url.password || url.port || authority.toLowerCase() !== url.hostname) return null;
      return url;
    } catch (_) { return null; }
  }
  function parliamentAttribution(parent, bill, greek) {
    if (bill.source !== 'PARLIAMENT') return false;
    var value = parliamentUrl(bill.official_source_url) ? bill.official_source_url : bill.parliament_url;
    if (!parliamentUrl(value)) return false;
    var attr = node(parent, 'div', 'attr');
    node(attr, 'div', '', greek ? 'Αναδημοσίευση από τη διαδικτυακή πύλη της Βουλής των Ελλήνων'
      : 'Republished from the website of the Hellenic Parliament');
    var date = [bill.source_last_success, bill.created_at].map(function (value) {
      if (!value) return null;
      var parsed = new Date(value.indexOf('T') >= 0 && !/(Z|[+-]\d{2}:?\d{2})$/i.test(value) ? value + 'Z' : value);
      return Number.isFinite(parsed.getTime()) ? parsed : null;
    }).filter(Boolean)[0];
    node(attr, 'div', '', (greek ? 'Ημερομηνία: ' : 'Date: ') + (date ? date.toLocaleDateString('en-GB', {
      timeZone: 'Europe/Athens', day: '2-digit', month: '2-digit', year: 'numeric'
    }) : (greek ? 'Μη διαθέσιμη' : 'Unavailable')));
    var original = node(attr, 'a', '', greek ? 'Πρωτότυπο' : 'Original');
    original.href = value; original.target = '_blank'; original.rel = 'noopener external';
    return true;
  }
  function attribution(parent, greek, href, label) {
    var attr = node(parent, 'div', 'attr', (greek ? 'Πηγή' : 'Source') + ': ');
    var source = node(attr, 'a', '', 'ekklesia.gr');
    source.href = 'https://ekklesia.gr'; source.target = '_blank'; source.rel = 'noopener';
    node(attr, 'span', '', ' · ');
    var link = node(attr, 'a', '', label);
    link.href = href; link.target = '_blank'; link.rel = 'noopener';
  }
  return { node: node, votes: votes, width: width, results: results, attribution: attribution, parliamentAttribution: parliamentAttribution };
}());

/* ekklesia.gr Motion Pack v1
   Adds .is-visible to .ekk-fade-up and .ekk-stagger when entering viewport.
   No dependencies. Safe fallback: content remains readable if JS is disabled.
*/
(function () {
  const targets = document.querySelectorAll('.ekk-fade-up, .ekk-stagger');
  if (!targets.length) return;

  if (!('IntersectionObserver' in window)) {
    targets.forEach((el) => el.classList.add('is-visible'));
    return;
  }

  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add('is-visible');
        observer.unobserve(entry.target);
      }
    });
  }, { rootMargin: '0px 0px -10% 0px', threshold: 0.16 });

  targets.forEach((el) => observer.observe(el));
})();

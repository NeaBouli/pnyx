/**
 * @section LANDING_PAGE
 * @update-hint Main page for Greek citizens. All text via i18n (el/en).
 * @seo title="εκκλησία — Ekklesia.gr" description="Ψηφιακή Πλατφόρμα Αμέσης Δημοκρατίας"
 * @geo target="GR" lang="el" fallback="en"
 * @ai-anchor HOMEPAGE_ROOT
 */
import { useLocale } from "next-intl";
import Link from "next/link";
import Image from "next/image";

// ─── SECTION: HERO ───────────────────────────────────────────────────────────
// @update-hint Main message + CTA buttons
function HeroSection() {
  const locale = useLocale();
  const isEl = locale === "el";

  return (
    <section className="bg-gradient-to-b from-blue-50 to-white py-24 px-6 text-center">
      {/* Badge */}
      <div className="inline-flex items-center gap-2 bg-blue-100 text-blue-700 px-4 py-2 rounded-full text-sm font-semibold mb-8">
        <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
        {isEl ? "Beta — Ανοιχτός Κώδικας · MIT License · © Vendetta Labs" : "Beta — Open Source · MIT License · © Vendetta Labs"}
      </div>

      {/* Logo */}
      <div className="flex justify-center mb-6">
        <Image src="/logo.png" alt="εκκλησία" width={120} height={120} priority />
      </div>

      {/* Title */}
      <h1 className="text-7xl font-black text-gray-900 mb-4 tracking-tight">
        εκκλησία
      </h1>
      <p className="text-2xl font-semibold text-blue-600 mb-6">
        {isEl ? "Η φωνή σου μετράει." : "Your voice matters."}
      </p>
      <p className="text-xl text-gray-600 max-w-2xl mx-auto mb-4 leading-relaxed">
        {isEl
          ? "Ψήφισε για πραγματικά νομοσχέδια."
          : "Vote on real parliamentary bills."}
      </p>
      <p className="italic text-sm text-gray-400 max-w-3xl mx-auto mb-12 leading-relaxed">
        {isEl
          ? "«Η Εκκλησία του Δήμου — η κύρια δημοκρατική συνέλευση της αρχαίας Αθήνας — πραγματοποιούνταν στον λόφο της Πνύκας, στην Αρχαία Αγορά ή στο Θέατρο του Διονύσου και αποτελούσε τον πυρήνα της αθηναϊκής δημοκρατίας. Η ιστοσελίδα ekklesia.gr εμπνέεται από αυτή την ιστορική παράδοση και αποτελεί ανεξάρτητη, ιδιωτική πλατφόρμα, χωρίς κρατική συγκατάθεση ή επίσημο χαρακτήρα. Όλες οι ψηφοφορίες που διεξάγονται στην πλατφόρμα αυτή έχουν αποκλειστικά ενημερωτικό χαρακτήρα και δεν παράγουν κανενός είδους νομική ή πολιτική δεσμευτικότητα.»"
          : "\"The Ekklesia — the principal democratic assembly of ancient Athens — convened on Pnyx hill, the Ancient Agora, or the Theatre of Dionysus and formed the core of Athenian democracy. ekklesie.gr is inspired by this historical tradition and is an independent, private platform with no state endorsement or official status. All votes conducted on this platform are purely informational and carry no legal or political binding force.\""}
      </p>
      <p className="text-xl text-gray-600 max-w-2xl mx-auto mb-12 leading-relaxed">
        {isEl
          ? "Μια ανοιχτή, ανώνυμη και ασφαλής πλατφόρμα για τον Έλληνα πολίτη. Συγκρίνετε τις θέσεις σας με τα κόμματα. Ψηφίστε για πραγματικά νομοσχέδια της Βουλής."
          : "An open, anonymous and secure platform for Greek citizens. Compare your positions with parties. Vote on real parliamentary bills."}
      </p>

      {/* CTA */}
      <div className="flex flex-col sm:flex-row gap-4 justify-center">
        <Link href="vaa"
          className="px-10 py-4 bg-blue-600 hover:bg-blue-700 text-white rounded-2xl font-bold text-lg transition-all shadow-lg shadow-blue-200 hover:scale-105">
          {isEl ? "🗳️ Ξεκινήστε την Πυξίδα" : "🗳️ Start VoteCompass"}
        </Link>
        <Link href="bills"
          className="px-10 py-4 bg-white hover:bg-gray-50 text-gray-800 rounded-2xl font-bold text-lg transition-all shadow-md border border-gray-200 hover:scale-105">
          {isEl ? "🏛️ Δείτε τα Νομοσχέδια" : "🏛️ See Parliament Bills"}
        </Link>
      </div>

      {/* Social Proof */}
      <p className="mt-10 text-sm text-gray-400">
        {isEl
          ? "Ανοιχτός κώδικας · Χωρίς διαφημίσεις · Χωρίς cookies · Χωρίς προσωπικά δεδομένα"
          : "Open source · No ads · No cookies · No personal data"}
      </p>
    </section>
  );
}

// ─── SECTION: HOW IT WORKS ───────────────────────────────────────────────────
// @update-hint Step-by-step usage guide. 4 steps.
function HowItWorksSection() {
  const locale = useLocale();
  const isEl = locale === "el";

  const steps = isEl ? [
    { icon: "📱", step: "1", title: "Επαλήθευση", desc: "Εισάγετε τον αριθμό κινητού σας. Λαμβάνετε SMS. Ο αριθμός διαγράφεται αμέσως — δεν αποθηκεύεται πουθενά." },
    { icon: "🔑", step: "2", title: "Κλειδί Ταυτότητας", desc: "Δημιουργείται ένα κρυπτογραφικό κλειδί μόνο για εσάς. Αποθηκεύεται μόνο στη συσκευή σας — όχι στους servers μας." },
    { icon: "🗳️", step: "3", title: "Ψηφίστε", desc: "Ψηφίστε Υπέρ, Κατά ή Αποχή σε πραγματικά νομοσχέδια. Κάθε ψήφος υπογράφεται κρυπτογραφικά — αδύνατη η πλαστογράφηση." },
    { icon: "📊", step: "4", title: "Δείτε τη Διαφορά", desc: "Συγκρίνετε πώς ψήφισαν οι πολίτες vs η Βουλή. Ο Δείκτης Απόκλισης δείχνει πόσο απέχουν οι βουλευτές από τον λαό." },
  ] : [
    { icon: "📱", step: "1", title: "Verify", desc: "Enter your mobile number. Receive SMS. The number is deleted immediately — stored nowhere." },
    { icon: "🔑", step: "2", title: "Identity Key", desc: "A cryptographic key is created just for you. Stored only on your device — not on our servers." },
    { icon: "🗳️", step: "3", title: "Vote", desc: "Vote Yes, No or Abstain on real bills. Every vote is cryptographically signed — impossible to falsify." },
    { icon: "📊", step: "4", title: "See the Difference", desc: "Compare how citizens voted vs Parliament. The Divergence Score shows how far MPs are from the people." },
  ];

  return (
    <section className="py-20 px-6 bg-white">
      <div className="max-w-5xl mx-auto">
        <h2 className="text-4xl font-black text-gray-900 text-center mb-4">
          {isEl ? "Πώς λειτουργεί;" : "How does it work?"}
        </h2>
        <p className="text-gray-500 text-center mb-16 text-lg">
          {isEl ? "Τέσσερα απλά βήματα. Χωρίς λογαριασμό. Χωρίς email." : "Four simple steps. No account. No email."}
        </p>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
          {steps.map((s, i) => (
            <div key={i} className="text-center">
              <div className="w-16 h-16 bg-blue-100 rounded-2xl flex items-center justify-center text-3xl mx-auto mb-4">
                {s.icon}
              </div>
              <div className="w-8 h-8 bg-blue-600 text-white rounded-full flex items-center justify-center text-sm font-bold mx-auto mb-3">
                {s.step}
              </div>
              <h3 className="font-bold text-gray-900 text-lg mb-2">{s.title}</h3>
              <p className="text-gray-500 text-sm leading-relaxed">{s.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ─── SECTION: FEATURES ───────────────────────────────────────────────────────
// @update-hint Feature cards. Add new features here.
function FeaturesSection() {
  const locale = useLocale();
  const isEl = locale === "el";

  const features = isEl ? [
    {
      icon: "🗳️", color: "bg-blue-50 border-blue-200", iconBg: "bg-blue-100",
      title: "Πολιτική Πυξίδα",
      desc: "15 πολιτικές θέσεις. 8 κόμματα. Δείτε με ποιο κόμμα συμφωνείτε περισσότερο — σε λιγότερο από 5 λεπτά.",
      cta: "Ξεκινήστε →", href: "vaa",
    },
    {
      icon: "🏛️", color: "bg-green-50 border-green-200", iconBg: "bg-green-100",
      title: "Ψηφοφορία Πολιτών",
      desc: "Ψηφίστε για πραγματικά νομοσχέδια που συζητούνται ή ψηφίστηκαν στη Βουλή. Ανώνυμα. Ασφαλώς.",
      cta: "Δείτε νομοσχέδια →", href: "bills",
    },
    {
      icon: "📊", color: "bg-purple-50 border-purple-200", iconBg: "bg-purple-100",
      title: "Δείκτης Απόκλισης",
      desc: "Πόσο απέχουν οι βουλευτές από τους πολίτες; Ο Δείκτης Απόκλισης το δείχνει αυτόματα για κάθε ψηφοφορία.",
      cta: null, href: null,
    },
    {
      icon: "🔐", color: "bg-yellow-50 border-yellow-200", iconBg: "bg-yellow-100",
      title: "Απόλυτη Ανωνυμία",
      desc: "Ed25519 κρυπτογράφηση. Nullifier Hash. Ο αριθμός σας διαγράφεται. Κανένα προσωπικό δεδομένο δεν αποθηκεύεται ποτέ.",
      cta: "Μάθετε περισσότερα →", href: "verify",
    },
    {
      icon: "📖", color: "bg-orange-50 border-orange-200", iconBg: "bg-orange-100",
      title: "Πλήρης Διαφάνεια",
      desc: "Ο κώδικας είναι 100% ανοιχτός. Κάθε αλγόριθμος, κάθε απόφαση, κάθε γραμμή κώδικα — δημόσια στο GitHub.",
      cta: "GitHub →", href: "https://github.com/NeaBouli/pnyx",
    },
    {
      icon: "⛓️", color: "bg-gray-50 border-gray-200", iconBg: "bg-gray-100",
      title: "TrueRepublic Bridge",
      desc: "Σύνδεση με το TrueRepublic Blockchain (Φάση V2). Μελλοντικά: αμετάβλητες ψήφοι on-chain με PnyxCoin.",
      cta: "Χάρτης Πορείας →", href: "about",
    },
  ] : [
    {
      icon: "🗳️", color: "bg-blue-50 border-blue-200", iconBg: "bg-blue-100",
      title: "VoteCompass", href: "vaa", cta: "Start →",
      desc: "15 political positions. 8 parties. See which party you agree with most — in under 5 minutes.",
    },
    {
      icon: "🏛️", color: "bg-green-50 border-green-200", iconBg: "bg-green-100",
      title: "Citizen Voting", href: "bills", cta: "See bills →",
      desc: "Vote on real bills discussed or passed in Parliament. Anonymously. Securely.",
    },
    {
      icon: "📊", color: "bg-purple-50 border-purple-200", iconBg: "bg-purple-100",
      title: "Divergence Score", href: null, cta: null,
      desc: "How far are MPs from citizens? The Divergence Score shows it automatically for every vote.",
    },
    {
      icon: "🔐", color: "bg-yellow-50 border-yellow-200", iconBg: "bg-yellow-100",
      title: "Full Anonymity", href: "verify", cta: "Learn more →",
      desc: "Ed25519 encryption. Nullifier Hash. Your number is deleted. No personal data is ever stored.",
    },
    {
      icon: "📖", color: "bg-orange-50 border-orange-200", iconBg: "bg-orange-100",
      title: "Full Transparency", href: "https://github.com/NeaBouli/pnyx", cta: "GitHub →",
      desc: "The code is 100% open. Every algorithm, every decision, every line of code — public on GitHub.",
    },
    {
      icon: "⛓️", color: "bg-gray-50 border-gray-200", iconBg: "bg-gray-100",
      title: "TrueRepublic Bridge", href: "about", cta: "Roadmap →",
      desc: "Connection to TrueRepublic Blockchain (Phase V2). Future: immutable votes on-chain with PnyxCoin.",
    },
  ];

  return (
    <section className="py-20 px-6 bg-gray-50">
      <div className="max-w-5xl mx-auto">
        <h2 className="text-4xl font-black text-gray-900 text-center mb-4">
          {isEl ? "Τι προσφέρει η Ekklesia;" : "What does Ekklesia offer?"}
        </h2>
        <p className="text-gray-500 text-center mb-16 text-lg">
          {isEl ? "Όλα σε μια πλατφόρμα — ανοιχτή, δωρεάν, για όλους." : "Everything in one platform — open, free, for everyone."}
        </p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {features.map((f, i) => (
            <div key={i} className={`rounded-2xl p-6 border ${f.color} hover:scale-105 transition-transform`}>
              <div className={`w-12 h-12 ${f.iconBg} rounded-xl flex items-center justify-center text-2xl mb-4`}>
                {f.icon}
              </div>
              <h3 className="font-bold text-gray-900 text-lg mb-2">{f.title}</h3>
              <p className="text-gray-600 text-sm leading-relaxed mb-4">{f.desc}</p>
              {f.cta && f.href && (
                f.href.startsWith("http")
                  ? <a href={f.href} target="_blank" rel="noopener noreferrer"
                      className="text-blue-600 font-semibold text-sm hover:underline">{f.cta}</a>
                  : <Link href={f.href} className="text-blue-600 font-semibold text-sm hover:underline">{f.cta}</Link>
              )}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ─── SECTION: TRUST / SECURITY ───────────────────────────────────────────────
// @update-hint Trust signals. Privacy promises.
function TrustSection() {
  const locale = useLocale();
  const isEl = locale === "el";

  const promises = isEl ? [
    { icon: "🚫", title: "Χωρίς προσωπικά δεδομένα", desc: "Ο αριθμός κινητού σας διαγράφεται αμέσως μετά την επαλήθευση. Δεν αποθηκεύεται ποτέ." },
    { icon: "🔓", title: "100% Ανοιχτός Κώδικας", desc: "Κάθε γραμμή κώδικα είναι δημόσια στο GitHub. Ο καθένας μπορεί να τον ελέγξει." },
    { icon: "🇪🇺", title: "GDPR Συμμόρφωση", desc: "Σχεδιασμένο από την αρχή για πλήρη συμμόρφωση με τον Ευρωπαϊκό Κανονισμό Προστασίας Δεδομένων." },
    { icon: "🔑", title: "Ed25519 Κρυπτογράφηση", desc: "Κρυπτογράφηση στρατιωτικής ισχύος. Το ιδιωτικό κλειδί βρίσκεται μόνο στη συσκευή σας." },
    { icon: "⚖️", title: "MIT License", desc: "Ελεύθερη χρήση, τροποποίηση και διανομή. © 2026 Vendetta Labs." },
    { icon: "🌐", title: "Servers στην Ευρώπη", desc: "Φιλοξενία αποκλειστικά σε ευρωπαϊκά data centers — GDPR by default." },
  ] : [
    { icon: "🚫", title: "No personal data", desc: "Your mobile number is deleted immediately after verification. Never stored." },
    { icon: "🔓", title: "100% Open Source", desc: "Every line of code is public on GitHub. Anyone can audit it." },
    { icon: "🇪🇺", title: "GDPR Compliant", desc: "Designed from the ground up for full compliance with European data protection law." },
    { icon: "🔑", title: "Ed25519 Encryption", desc: "Military-grade encryption. The private key lives only on your device." },
    { icon: "⚖️", title: "MIT License", desc: "Free to use, modify and distribute. © 2026 Vendetta Labs." },
    { icon: "🌐", title: "European Servers", desc: "Hosted exclusively in European data centers — GDPR by default." },
  ];

  return (
    <section className="py-20 px-6 bg-white">
      <div className="max-w-5xl mx-auto">
        <h2 className="text-4xl font-black text-gray-900 text-center mb-4">
          {isEl ? "Γιατί να μας εμπιστευτείτε;" : "Why trust us?"}
        </h2>
        <p className="text-gray-500 text-center mb-16 text-lg">
          {isEl
            ? "Δεν ζητάμε εμπιστοσύνη — την αποδεικνύουμε με κώδικα."
            : "We don't ask for trust — we prove it with code."}
        </p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {promises.map((p, i) => (
            <div key={i} className="flex gap-4 p-5 rounded-2xl bg-gray-50 border border-gray-100">
              <span className="text-3xl flex-shrink-0">{p.icon}</span>
              <div>
                <h3 className="font-bold text-gray-900 mb-1">{p.title}</h3>
                <p className="text-gray-500 text-sm leading-relaxed">{p.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ─── SECTION: DEMOCRACY CTA ──────────────────────────────────────────────────
// @update-hint Emotional closing + final CTA
function DemocracyCTA() {
  const locale = useLocale();
  const isEl = locale === "el";

  return (
    <section className="py-24 px-6 bg-gradient-to-b from-blue-600 to-blue-800 text-white text-center">
      <div className="max-w-3xl mx-auto">
        <h2 className="text-5xl font-black mb-6 leading-tight">
          {isEl
            ? "Η δημοκρατία δεν είναι θέαμα. Είναι πράξη."
            : "Democracy is not a spectacle. It is action."}
        </h2>
        <p className="text-blue-100 text-xl mb-10 leading-relaxed">
          {isEl
            ? "Η εκκλησία ήταν η λαϊκή συνέλευση της αρχαίας Αθήνας — εκεί όπου κάθε πολίτης είχε φωνή. Η Ekklesia.gr είναι η ψηφιακή αναβίωσή της."
            : "The ekklesia was the popular assembly of ancient Athens — where every citizen had a voice. Ekklesia.gr is its digital revival."}
        </p>
        <div className="flex flex-col sm:flex-row gap-4 justify-center">
          <Link href="vaa"
            className="px-10 py-4 bg-white text-blue-700 rounded-2xl font-bold text-lg hover:bg-blue-50 transition-all shadow-lg hover:scale-105">
            {isEl ? "🗳️ Ξεκινήστε τώρα — δωρεάν" : "🗳️ Start now — free"}
          </Link>
          <a href="https://github.com/NeaBouli/pnyx/wiki"
            target="_blank" rel="noopener noreferrer"
            className="px-10 py-4 bg-blue-500 hover:bg-blue-400 text-white rounded-2xl font-bold text-lg transition-all border border-blue-400 hover:scale-105">
            {isEl ? "📖 Διαβάστε το Wiki" : "📖 Read the Wiki"}
          </a>
        </div>
      </div>
    </section>
  );
}

// ─── SECTION: ROADMAP PREVIEW ────────────────────────────────────────────────
// @update-hint Roadmap phases. Update when new phase begins.
function RoadmapSection() {
  const locale = useLocale();
  const isEl = locale === "el";

  const phases = [
    {
      phase: "Beta",
      status: "active",
      color: "border-green-400 bg-green-50",
      badge: "bg-green-500",
      items: isEl
        ? ["SMS Επαλήθευση", "Πολιτική Πυξίδα (8 κόμματα, 15 θέσεις)", "Ψηφοφορία Πολιτών", "Δείκτης Απόκλισης"]
        : ["SMS Verification", "VoteCompass (8 parties, 15 positions)", "Citizen Voting", "Divergence Score"],
    },
    {
      phase: "Alpha",
      status: "upcoming",
      color: "border-yellow-400 bg-yellow-50",
      badge: "bg-yellow-500",
      items: isEl
        ? ["gov.gr OAuth2.0 Επαλήθευση", "Δημογραφική Ανάλυση", "3+ NGO Συνεργάτες"]
        : ["gov.gr OAuth2.0 Verification", "Demographic Analysis", "3+ NGO Partners"],
    },
    {
      phase: "V2",
      status: "planned",
      color: "border-purple-400 bg-purple-50",
      badge: "bg-purple-500",
      items: isEl
        ? ["TrueRepublic Blockchain Bridge", "PnyxCoin On-Chain Ψήφοι", "Rust + WASM Κρυπτογράφηση", "Εφαρμογή Κινητού (iOS + Android)"]
        : ["TrueRepublic Blockchain Bridge", "PnyxCoin On-Chain Votes", "Rust + WASM Encryption", "Mobile App (iOS + Android)"],
    },
  ];

  return (
    <section className="py-20 px-6 bg-gray-50">
      <div className="max-w-5xl mx-auto">
        <h2 className="text-4xl font-black text-gray-900 text-center mb-4">
          {isEl ? "Χάρτης Πορείας" : "Roadmap"}
        </h2>
        <p className="text-gray-500 text-center mb-16 text-lg">
          {isEl ? "Πού βρισκόμαστε και πού πάμε." : "Where we are and where we're going."}
        </p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {phases.map((p) => (
            <div key={p.phase} className={`rounded-2xl p-6 border-2 ${p.color}`}>
              <div className="flex items-center gap-3 mb-4">
                <span className={`w-3 h-3 rounded-full ${p.badge} ${p.status === "active" ? "animate-pulse" : ""}`} />
                <span className="font-black text-gray-900 text-xl">{p.phase}</span>
                {p.status === "active" && (
                  <span className="text-xs bg-green-500 text-white px-2 py-1 rounded-full font-semibold">
                    {isEl ? "Τώρα" : "Now"}
                  </span>
                )}
              </div>
              <ul className="space-y-2">
                {p.items.map((item, i) => (
                  <li key={i} className="flex gap-2 text-sm text-gray-700">
                    <span className="text-green-500 flex-shrink-0">✓</span>
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ─── SECTION: WIKI LINK ──────────────────────────────────────────────────────
// @update-hint Wiki connection. Maintained on wiki updates.
function WikiSection() {
  const locale = useLocale();
  const isEl = locale === "el";

  const wikiPages = isEl ? [
    { title: "Αρχιτεκτονική",     desc: "Πώς είναι χτισμένη η πλατφόρμα",    href: "https://github.com/NeaBouli/pnyx/wiki/Architecture" },
    { title: "Ασφάλεια",          desc: "Ed25519, Nullifier, ZK — αναλυτικά", href: "https://github.com/NeaBouli/pnyx/wiki/Security" },
    { title: "Οδηγός Συμμετοχής", desc: "Πώς να συμβάλετε στον κώδικα",       href: "https://github.com/NeaBouli/pnyx/wiki/Contributing" },
    { title: "API Τεκμηρίωση",    desc: "Πλήρης τεχνική τεκμηρίωση API",      href: "https://github.com/NeaBouli/pnyx/wiki/API" },
  ] : [
    { title: "Architecture",      desc: "How the platform is built",           href: "https://github.com/NeaBouli/pnyx/wiki/Architecture" },
    { title: "Security",          desc: "Ed25519, Nullifier, ZK — in detail",  href: "https://github.com/NeaBouli/pnyx/wiki/Security" },
    { title: "Contributing",      desc: "How to contribute to the code",       href: "https://github.com/NeaBouli/pnyx/wiki/Contributing" },
    { title: "API Docs",          desc: "Full technical API documentation",    href: "https://github.com/NeaBouli/pnyx/wiki/API" },
  ];

  return (
    <section className="py-20 px-6 bg-white">
      <div className="max-w-4xl mx-auto text-center">
        <h2 className="text-4xl font-black text-gray-900 mb-4">
          {isEl ? "📖 Wiki — Τεχνικές Λεπτομέρειες" : "📖 Wiki — Technical Details"}
        </h2>
        <p className="text-gray-500 mb-12 text-lg">
          {isEl
            ? "Θέλετε να καταλάβετε πώς λειτουργεί το σύστημα; Το Wiki έχει όλες τις απαντήσεις."
            : "Want to understand how the system works? The Wiki has all the answers."}
        </p>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          {wikiPages.map((w, i) => (
            <a key={i} href={w.href} target="_blank" rel="noopener noreferrer"
              className="p-4 rounded-2xl bg-gray-50 border border-gray-200 hover:border-blue-400 hover:bg-blue-50 transition-all text-left group">
              <p className="font-bold text-gray-900 text-sm mb-1 group-hover:text-blue-700">{w.title}</p>
              <p className="text-gray-500 text-xs">{w.desc}</p>
            </a>
          ))}
        </div>
        <a href="https://github.com/NeaBouli/pnyx/wiki"
          target="_blank" rel="noopener noreferrer"
          className="inline-flex items-center gap-2 px-8 py-4 bg-gray-900 hover:bg-gray-700 text-white rounded-2xl font-bold transition-all">
          <svg width="20" height="20" fill="currentColor" viewBox="0 0 24 24">
            <path d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"/>
          </svg>
          {isEl ? "Ανοίξτε το Wiki" : "Open the Wiki"}
        </a>
      </div>
    </section>
  );
}

// ─── FOOTER ──────────────────────────────────────────────────────────────────
// @update-hint Footer links + disclaimer
function Footer() {
  const locale = useLocale();
  const isEl = locale === "el";

  return (
    <footer className="bg-gray-900 text-gray-400 py-12 px-6">
      <div className="max-w-5xl mx-auto">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-8 mb-8">
          <div>
            <p className="text-white font-bold text-lg mb-3">εκκλησία</p>
            <p className="text-sm leading-relaxed">
              {isEl ? "Ψηφιακή Άμεση Δημοκρατία για τον Έλληνα Πολίτη" : "Digital Direct Democracy for Greek Citizens"}
            </p>
          </div>
          <div>
            <p className="text-white font-semibold mb-3">{isEl ? "Πλατφόρμα" : "Platform"}</p>
            <ul className="space-y-2 text-sm">
              <li><Link href="vaa" className="hover:text-white transition-colors">{isEl ? "Πολιτική Πυξίδα" : "VoteCompass"}</Link></li>
              <li><Link href="bills" className="hover:text-white transition-colors">{isEl ? "Νομοσχέδια" : "Bills"}</Link></li>
              <li><Link href="verify" className="hover:text-white transition-colors">{isEl ? "Επαλήθευση" : "Verify"}</Link></li>
            </ul>
          </div>
          <div>
            <p className="text-white font-semibold mb-3">{isEl ? "Πληροφορίες" : "Info"}</p>
            <ul className="space-y-2 text-sm">
              <li><a href="https://github.com/NeaBouli/pnyx/wiki" target="_blank" rel="noopener noreferrer" className="hover:text-white transition-colors">Wiki</a></li>
              <li><a href="https://github.com/NeaBouli/pnyx" target="_blank" rel="noopener noreferrer" className="hover:text-white transition-colors">GitHub</a></li>
            </ul>
          </div>
          <div>
            <p className="text-white font-semibold mb-3">{isEl ? "Νομικά" : "Legal"}</p>
            <ul className="space-y-2 text-sm">
              <li><span>MIT License</span></li>
              <li><span>© 2026 Vendetta Labs</span></li>
              <li><span>GDPR Compliant</span></li>
            </ul>
          </div>
        </div>

        <div className="border-t border-gray-800 pt-8 text-center text-xs text-gray-600">
          <p>
            {isEl
              ? "Η πλατφόρμα αυτή δεν είναι νομικά δεσμευτική και δεν αντικαθιστά επίσημες εκλογικές διαδικασίες."
              : "This platform is not legally binding and does not replace official electoral processes."}
          </p>
          <p className="mt-2">
            εκκλησία · Ekklesia.gr · © 2026 Vendetta Labs · MIT License ·{" "}
            <a href="https://github.com/NeaBouli/pnyx" className="hover:text-gray-400">Open Source</a>
          </p>
        </div>
      </div>
    </footer>
  );
}

// ─── PAGE ROOT ───────────────────────────────────────────────────────────────
// @ai-anchor HOMEPAGE_SECTIONS_ORDER
// Order: Hero → HowItWorks → Features → Trust → DemocracyCTA → Roadmap → Wiki → Footer
export default function HomePage() {
  return (
    <main>
      <HeroSection />
      <HowItWorksSection />
      <FeaturesSection />
      <TrustSection />
      <DemocracyCTA />
      <RoadmapSection />
      <WikiSection />
      <Footer />
    </main>
  );
}

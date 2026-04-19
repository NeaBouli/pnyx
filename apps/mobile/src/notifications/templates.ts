export const PUSH_TEMPLATES = {
  VOTE_OPEN: {
    title: () => "🗳️ Νέα Ψηφοφορία",
    body: (data: { bill_title: string }) => `${data.bill_title} — Ψηφίστε τώρα`,
    data: { screen: "Bills", filter: "active" },
  },
  VOTE_24H: {
    title: () => "⏰ Τελευταίες 24 Ώρες",
    body: (data: { bill_title: string }) => `${data.bill_title} κλείνει αύριο`,
    data: { screen: "Bills", filter: "active" },
  },
  VOTE_RESULT: {
    title: () => "📊 Αποτέλεσμα",
    body: (data: { bill_title: string; divergence: number }) =>
      `${data.bill_title} — Απόκλιση ${data.divergence}%`,
    data: { screen: "Bills", filter: "results" },
  },
  BILL_ANNOUNCED: {
    title: () => "🏛️ Νέο Νομοσχέδιο",
    body: (data: { bill_title: string }) => `${data.bill_title} — Σύντομα για ψηφοφορία`,
    data: { screen: "Bills", filter: "all" },
  },
  WEEKLY_DIGEST: {
    title: () => "📋 Εβδομαδιαία Ανακεφαλαίωση",
    body: (data: { count: number; results: number }) =>
      `${data.count} ψηφοφορίες — ${data.results} αποτελέσματα αυτή την εβδομάδα`,
    data: { screen: "Home" },
  },
  SYSTEM_UPDATE: {
    title: () => "⚙️ Ενημέρωση εκκλησία",
    body: (data: { message: string }) => data.message,
    data: { screen: "Home" },
  },
} as const;

export type PushTemplateId = keyof typeof PUSH_TEMPLATES;

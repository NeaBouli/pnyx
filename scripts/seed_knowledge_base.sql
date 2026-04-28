-- Knowledge Base Seed — ekklesia.gr
-- Run: docker exec ekklesia-db psql -U ekklesia -d ekklesia_prod -f /tmp/seed_kb.sql

DELETE FROM knowledge_base;

INSERT INTO knowledge_base (category, title_el, title_en, content_el, content_en, keywords, priority) VALUES
('mission', 'Τι είναι η εκκλησία;', 'What is ekklesia?',
 'Η εκκλησία του έθνους (ekklesia.gr) είναι μια ανεξάρτητη, μη κρατική, open-source πλατφόρμα ψηφιακής άμεσης δημοκρατίας. Επιτρέπει σε Έλληνες πολίτες να ψηφίζουν ανώνυμα σε πραγματικά νομοσχέδια της Ελληνικής Βουλής. Η πλατφόρμα μετράει τη γνώμη των πολιτών και τη συγκρίνει με τις ψήφους των κομμάτων στη Βουλή, δημιουργώντας τον Δείκτη Απόκλισης (Divergence Score). Η εκκλησία ΔΕΝ είναι κυβερνητική υπηρεσία. Οι ψηφοφορίες δεν είναι νομικά δεσμευτικές. Λειτουργεί υπό άδεια MIT, χρηματοδοτείται αποκλειστικά από πολίτες, χωρίς διαφημίσεις ή κρατική επιχορήγηση. Ιδρύθηκε το 2026 από τα Vendetta Labs.',
 'ekklesia (ekklesia.gr) is an independent, non-governmental, open-source platform for digital direct democracy. It allows Greek citizens to vote anonymously on real bills from the Hellenic Parliament. The platform measures citizen opinion and compares it with party votes in Parliament, creating the Divergence Score. Founded in 2026 by Vendetta Labs. MIT License.',
 '["εκκλησία","ekklesia","δημοκρατία","democracy","platform","open source"]', 1),

('mission', 'Ποιος δημιούργησε την εκκλησία;', 'Who created ekklesia?',
 'Η εκκλησία δημιουργήθηκε από τα Vendetta Labs, ένα ανεξάρτητο development studio με έδρα την Ελλάδα. Ο κώδικας είναι 100% open source στο GitHub (github.com/NeaBouli/pnyx). Η ανάπτυξη γίνεται εθελοντικά. Δεν υπάρχει εταιρικός χορηγός, κρατική χρηματοδότηση ή διαφημίσεις. Η πλατφόρμα χρηματοδοτείται αποκλειστικά από δωρεές πολιτών μέσω Stripe και PayPal.',
 'ekklesia was created by Vendetta Labs, an independent development studio based in Greece. The code is 100% open source on GitHub (github.com/NeaBouli/pnyx). Funded exclusively by citizen donations.',
 '["Vendetta Labs","NeaBouli","GitHub","open source","δωρεές"]', 2),

('privacy', 'Πώς προστατεύεται η ανωνυμία μου;', 'How is my anonymity protected?',
 'Η εκκλησία χρησιμοποιεί κρυπτογραφία Ed25519 για ψηφιακές υπογραφές. Ο αριθμός τηλεφώνου σου χρησιμοποιείται ΜΟΝΟ για επαλήθευση μέσω HLR Lookup (χωρίς SMS) και διαγράφεται αμέσως μετά. Αποθηκεύεται μόνο ένα nullifier hash που δεν μπορεί να αντιστραφεί. Το ιδιωτικό κλειδί αποθηκεύεται ΜΟΝΟ στη συσκευή σου (Android Keystore / iOS Keychain). Ο server δεν γνωρίζει ποτέ τι ψήφισες. Δεν υπάρχουν cookies, accounts ή email.',
 'ekklesia uses Ed25519 cryptography. Phone number is used ONLY for HLR verification and deleted immediately. Only a non-reversible nullifier hash is stored. Private key stays on your device only.',
 '["ανωνυμία","anonymity","Ed25519","nullifier","κρυπτογραφία","HLR","privacy"]', 1),

('privacy', 'Τι δεδομένα αποθηκεύονται;', 'What data is stored?',
 'Ο server αποθηκεύει: (1) nullifier hash (μη αντιστρέψιμο), (2) δημόσιο κλειδί Ed25519, (3) κρυπτογραφική υπογραφή ψήφου, (4) δημογραφικό hash (Περιφέρεια/Δήμος, προαιρετικό). ΔΕΝ αποθηκεύει: αριθμό τηλεφώνου, όνομα, email, IP διεύθυνση, cookies, ιστορικό πλοήγησης. Τα αποτελέσματα αρχειοθετούνται μόνιμα στο Arweave blockchain.',
 'Server stores: nullifier hash, Ed25519 public key, vote signature, demographic hash. Does NOT store: phone number, name, email, IP address, cookies. Results archived on Arweave blockchain.',
 '["δεδομένα","data","Arweave","blockchain"]', 1),

('process', 'Πώς ψηφίζω;', 'How do I vote?',
 'Βήμα 1: Κατεβάστε την εφαρμογή εκκλησία (Android APK ή Play Store). Βήμα 2: Επαληθεύστε ότι είστε Έλληνας πολίτης μέσω του αριθμού κινητού (+30). Η επαλήθευση γίνεται μέσω HLR Lookup χωρίς SMS. Βήμα 3: Δημιουργείται αυτόματα ένα κρυπτογραφικό κλειδί Ed25519. Βήμα 4: Ψηφίστε ΝΑΙ, ΟΧΙ ή ΑΠΟΧΗ σε ενεργά νομοσχέδια. Η ψήφος υπογράφεται ψηφιακά στη συσκευή σας. Μπορείτε επίσης να ψηφίσετε μέσω web στο ekklesia.gr/el/bills.',
 'Step 1: Download the ekklesia app. Step 2: Verify Greek citizenship via mobile number (+30). Step 3: Ed25519 key is generated on device. Step 4: Vote YES, NO or ABSTAIN. Vote is digitally signed on device. Also available at ekklesia.gr/el/bills.',
 '["ψήφος","vote","εφαρμογή","app","επαλήθευση","verification"]', 1),

('process', 'Τι είναι ο Δείκτης Απόκλισης;', 'What is the Divergence Score?',
 'Ο Δείκτης Απόκλισης μετράει πόσο διαφέρει η γνώμη των πολιτών από τις ψήφους των κομμάτων στη Βουλή. Τιμή 0 = πλήρης ευθυγράμμιση, τιμή 1 = πλήρης αντίθεση. Αν η πλειοψηφία πολιτών ψηφίζει ΟΧΙ αλλά η Βουλή ΝΑΙ, ο δείκτης είναι υψηλός. Είναι το κεντρικό εργαλείο της πλατφόρμας.',
 'The Divergence Score measures how much citizen opinion differs from party votes in Parliament. Value 0 = full alignment, value 1 = complete opposition.',
 '["απόκλιση","divergence","score","Βουλή","κόμματα"]', 1),

('process', 'Ποια νομοσχέδια μπορώ να ψηφίσω;', 'Which bills can I vote on?',
 'Μπορείτε να ψηφίσετε σε νομοσχέδια ACTIVE (Ανοιχτή Ψηφοφορία) ή OPEN_END (Αρχείο Ανοιχτό). Τα νομοσχέδια προέρχονται από τη Βουλή των Ελλήνων (hellenicparliament.gr). Η πλατφόρμα καλύπτει εθνικά νομοσχέδια, περιφερειακές αποφάσεις μέσω Διαύγεια, και δημοτικές αποφάσεις. Κάθε νομοσχέδιο περιλαμβάνει τίτλο, περίληψη, κατηγορία, σύνδεσμο στη Βουλή, και AI ανάλυση.',
 'You can vote on ACTIVE or OPEN_END bills from the Hellenic Parliament. The platform covers national bills, regional decisions via Diavgeia, and municipal decisions.',
 '["νομοσχέδια","bills","Βουλή","parliament","Διαύγεια"]', 1),

('faq', 'Χρειάζεται λογαριασμός;', 'Do I need an account?',
 'Όχι. Η εκκλησία δεν χρησιμοποιεί λογαριασμούς, email ή κωδικούς πρόσβασης. Η ταυτότητά σας επαληθεύεται μόνο μέσω του ελληνικού αριθμού κινητού. Μετά την επαλήθευση, ο αριθμός διαγράφεται και λαμβάνετε ένα κρυπτογραφικό κλειδί στη συσκευή σας.',
 'No. ekklesia does not use accounts, email, or passwords. Identity verified only through Greek mobile number, then deleted.',
 '["λογαριασμός","account","email","κωδικός"]', 1),

('faq', 'Μπορώ να ψηφίσω από το εξωτερικό;', 'Can I vote from abroad?',
 'Ναι, αρκεί να έχετε ελληνικό αριθμό κινητού (+30) με ενεργή SIM. Η επαλήθευση HLR ελέγχει μόνο αν ο αριθμός είναι έγκυρος ελληνικός αριθμός.',
 'Yes, as long as you have a Greek mobile number (+30) with an active SIM.',
 '["εξωτερικό","abroad","SIM","diaspora"]', 1),

('faq', 'Είναι νόμιμο;', 'Is it legal?',
 'Ναι. Η εκκλησία είναι νόμιμη πλατφόρμα έκφρασης γνώμης, όπως μια δημοσκόπηση. Δεν αντικαθιστά τους θεσμικούς μηχανισμούς. Οι ψηφοφορίες ΔΕΝ είναι νομικά δεσμευτικές. Λειτουργεί ως εργαλείο civic education και διαφάνειας.',
 'Yes. ekklesia is a legal platform for expressing opinions, like a poll. Votes are NOT legally binding.',
 '["νόμιμο","legal","δημοσκόπηση","poll"]', 1),

('faq', 'Πόσο κοστίζει;', 'How much does it cost?',
 'Τίποτα. Η εκκλησία είναι δωρεάν για τους πολίτες. Το κόστος λειτουργίας (~250 ευρώ ανά έτος για server, domain, AI) καλύπτεται από εθελοντικές δωρεές. Δεν υπάρχουν διαφημίσεις, συνδρομές ή κρυφές χρεώσεις.',
 'Nothing. ekklesia is free for citizens. Operating costs (~250 EUR/year) covered by voluntary donations. No ads.',
 '["κόστος","cost","δωρεάν","free","δωρεές"]', 1),

('faq', 'Πόσο ζυγίζει η ψήφος μου;', 'How much does my vote weigh?',
 'Με SMS/HLR επαλήθευση: x1.0 βάρος. Με gov.gr OAuth επαλήθευση (μελλοντικό): x2.0 βάρος. Η gov.gr επαλήθευση αναμένει κυβερνητική έγκριση. Κάθε πολίτης μπορεί να ψηφίσει μόνο μία φορά ανά νομοσχέδιο.',
 'With SMS/HLR verification: x1.0 weight. With gov.gr OAuth (future): x2.0 weight. One vote per bill per citizen.',
 '["βάρος","weight","ψήφος","vote"]', 1),

('faq', 'Είναι ασφαλής η πλατφόρμα;', 'Is the platform secure?',
 'Η πλατφόρμα χρησιμοποιεί: Ed25519 κρυπτογραφία, HTTPS/TLS σε όλες τις συνδέσεις, PostgreSQL με parameterized queries (χωρίς SQL injection), rate limiting σε όλα τα endpoints, HLR Lookup αντί SMS (ανθεκτικό σε SIM swap), Arweave blockchain για μόνιμη αρχειοθέτηση. Ο κώδικας είναι open source και μπορεί να ελεγχθεί από οποιονδήποτε.',
 'The platform uses: Ed25519 cryptography, HTTPS/TLS, parameterized SQL queries, rate limiting, HLR Lookup, Arweave blockchain archiving. Code is open source and auditable.',
 '["ασφάλεια","security","Ed25519","HTTPS","open source"]', 1),

('features', 'Τι υπηρεσίες προσφέρει η εκκλησία;', 'What services does ekklesia offer?',
 'Η πλατφόρμα περιλαμβάνει: (1) Ψηφοφορία σε πραγματικά νομοσχέδια, (2) Σύγκριση κομμάτων με πολίτες (MP Comparison), (3) Δείκτη Απόκλισης, (4) Τοπική Αυτοδιοίκηση μέσω Διαύγεια, (5) AI Βοηθό (chatbot), (6) Forum πνύκα (pnyx.ekklesia.gr), (7) Newsletter, (8) Public API (CC BY 4.0), (9) Αρχειοθέτηση στο Arweave blockchain, (10) Mobile App Android.',
 'The platform includes: voting on real bills, party comparison, Divergence Score, local government via Diavgeia, AI chatbot, forum (pnyx.ekklesia.gr), newsletter, public API, Arweave archiving, Android app.',
 '["υπηρεσίες","services","features","chatbot","forum","API"]', 2),

('features', 'Τι είναι η πνύκα;', 'What is the pnyx?',
 'Η πνύκα (pnyx.ekklesia.gr) είναι το δημόσιο forum της εκκλησίας. Οι πολίτες μπορούν να συζητήσουν νομοσχέδια, να προτείνουν ιδέες, και να ανταλλάξουν απόψεις. Τα νομοσχέδια δημοσιεύονται αυτόματα στο forum. Υπάρχουν κατηγορίες για κάθε Περιφέρεια (Αγορά Πολιτών) όπου οι πολίτες δημιουργούν δικά τους θέματα. Εγγραφή μέσω email, Google, ή ekklesia επαλήθευση.',
 'The pnyx (pnyx.ekklesia.gr) is the public forum. Citizens discuss bills, propose ideas. Bills auto-published. Categories per Region. Registration via email, Google, or ekklesia verification.',
 '["πνύκα","pnyx","forum","συζήτηση"]', 2),

('features', 'Πώς λειτουργεί ο AI Βοηθός;', 'How does the AI Assistant work?',
 'Ο AI Βοηθός χρησιμοποιεί τεχνολογία RAG (Retrieval-Augmented Generation). Αναζητά στη βάση δεδομένων νομοσχεδίων και στη βάση γνώσεων, και δημιουργεί απαντήσεις βασισμένες σε πραγματικά δεδομένα. Τρέχει τοπικά στον server μέσω Ollama (llama3.2). Δεν αποθηκεύει τις ερωτήσεις σας. Περιορισμός: 5 ερωτήσεις ανά λεπτό.',
 'The AI Assistant uses RAG technology. Searches bill database and knowledge base. Runs locally via Ollama. Does not store questions. Limit: 5 req/min.',
 '["AI","chatbot","Ollama","RAG","βοηθός"]', 2),

('govgr', 'Τι είναι η gov.gr επαλήθευση;', 'What is gov.gr verification?',
 'Η gov.gr OAuth επαλήθευση είναι τεχνικά υλοποιημένη αλλά αναμένει κυβερνητική έγκριση. Με τη gov.gr επαλήθευση, η ψήφος θα ζυγίζει x2.0 αντί x1.0. Δύο τρόποι ενεργοποίησης: (1) Εθνική Έγκριση από ΓΓΠΣ/GSRT, ή (2) Αίτημα Δημάρχου/Περιφερειάρχη. Μέχρι τότε, SMS (HLR) επαλήθευση λειτουργεί κανονικά.',
 'gov.gr OAuth is technically implemented but awaits government approval. Would give x2.0 vote weight. Two activation paths: national approval or municipal request.',
 '["gov.gr","OAuth","επαλήθευση","ΓΓΠΣ","βάρος"]', 2);

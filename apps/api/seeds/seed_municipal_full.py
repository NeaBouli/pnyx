"""
Seed ALL 325 Greek Municipalities (Dimoi) per Kallikratis reform (2011).
13 Periferias + 325 Dimoi — complete dataset.

Upsert pattern: existing records updated, new ones inserted.
Run: docker exec ekklesia-api python seeds/seed_municipal_full.py
"""
import asyncio
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database import engine, AsyncSessionLocal
from models import Periferia, Dimos
from sqlalchemy import select

# 13 Periferias (same as seed_municipal.py — ensures idempotency)
PERIFERIAS = [
    ("Αττικής", "Attica", "GR-I"),
    ("Κεντρικής Μακεδονίας", "Central Macedonia", "GR-B"),
    ("Δυτικής Ελλάδας", "Western Greece", "GR-G"),
    ("Θεσσαλίας", "Thessaly", "GR-E"),
    ("Κρήτης", "Crete", "GR-M"),
    ("Πελοποννήσου", "Peloponnese", "GR-J"),
    ("Ανατολικής Μακεδονίας και Θράκης", "Eastern Macedonia and Thrace", "GR-A"),
    ("Ηπείρου", "Epirus", "GR-D"),
    ("Δυτικής Μακεδονίας", "Western Macedonia", "GR-C"),
    ("Στερεάς Ελλάδας", "Central Greece", "GR-H"),
    ("Ιονίων Νήσων", "Ionian Islands", "GR-F"),
    ("Βορείου Αιγαίου", "North Aegean", "GR-K"),
    ("Νοτίου Αιγαίου", "South Aegean", "GR-L"),
]

# ═══════════════════════════════════════════════════════════════
# ALL 325 DIMOI — Kallikratis Reform (Law 3852/2010)
# Population: 2021 Census (ELSTAT)
# ═══════════════════════════════════════════════════════════════

DIMOI = {
    # ── GR-I: ΑΤΤΙΚΗ (66 dimoi) ──────────────────────────────
    "GR-I": [
        # Κεντρικός Τομέας Αθηνών
        ("Αθηναίων", "Athens", 664046),
        ("Βύρωνος", "Vyronas", 61308),
        ("Γαλατσίου", "Galatsi", 59345),
        ("Δάφνης-Υμηττού", "Dafni-Ymittos", 33613),
        ("Ζωγράφου", "Zografou", 76115),
        ("Ηλιουπόλεως", "Ilioupoli", 78153),
        ("Καισαριανής", "Kaisariani", 26370),
        ("Φιλαδελφείας-Χαλκηδόνος", "Filadelfia-Chalkidona", 35776),
        # Βόρειος Τομέας Αθηνών
        ("Αγίας Παρασκευής", "Agia Paraskevi", 63902),
        ("Αμαρουσίου", "Marousi", 72333),
        ("Βριλησσίων", "Vrilissia", 30741),
        ("Ηρακλείου", "Irakleio Attikis", 49642),
        ("Κηφισιάς", "Kifisia", 79540),
        ("Λυκόβρυσης-Πεύκης", "Lykovrysi-Pefki", 30120),
        ("Μεταμορφώσεως", "Metamorfosi", 29891),
        ("Νέας Ιωνίας", "Nea Ionia", 67183),
        ("Παπάγου-Χολαργού", "Papagou-Cholargos", 44939),
        ("Πεντέλης", "Penteli", 34934),
        ("Χαλανδρίου", "Chalandri", 74192),
        ("Ψυχικού", "Psychiko", 10134),
        # Νότιος Τομέας Αθηνών
        ("Αγίου Δημητρίου", "Agios Dimitrios", 71294),
        ("Αλίμου", "Alimos", 41720),
        ("Γλυφάδας", "Glyfada", 87305),
        ("Ελληνικού-Αργυρούπολης", "Elliniko-Argyroupoli", 51356),
        ("Καλλιθέας", "Kallithea", 100641),
        ("Μοσχάτου-Ταύρου", "Moschato-Tavros", 33629),
        ("Νέας Σμύρνης", "Nea Smyrni", 73076),
        ("Παλαιού Φαλήρου", "Palaio Faliro", 64759),
        # Δυτικός Τομέας Αθηνών
        ("Αγίας Βαρβάρας", "Agia Varvara", 26550),
        ("Αγίων Αναργύρων-Καματερού", "Agioi Anargyroi-Kamatero", 61236),
        ("Αιγάλεω", "Egaleo", 69946),
        ("Ιλίου", "Ilion", 84793),
        ("Περιστερίου", "Peristeri", 139981),
        ("Πετρούπολης", "Petroupoli", 58979),
        ("Χαϊδαρίου", "Chaidari", 45642),
        # Πειραιάς
        ("Πειραιώς", "Piraeus", 163688),
        ("Κερατσινίου-Δραπετσώνας", "Keratsini-Drapetsona", 77077),
        ("Κορυδαλλού", "Korydallos", 63445),
        ("Νίκαιας-Αγ.Ι.Ρέντη", "Nikaia-Rentis", 93609),
        ("Περάματος", "Perama", 25720),
        # Νήσοι
        ("Αίγινας", "Aegina", 13056),
        ("Αγκιστρίου", "Agkistri", 1142),
        ("Κυθήρων", "Kythira", 3927),
        ("Πόρου", "Poros", 3993),
        ("Σαλαμίνος", "Salamina", 39283),
        ("Σπετσών", "Spetses", 4027),
        ("Τροιζηνίας-Μεθάνων", "Troizinia-Methana", 7678),
        ("Ύδρας", "Hydra", 1966),
        # Ανατολική Αττική
        ("Αχαρνών", "Acharnes", 106943),
        ("Βάρης-Βούλας-Βουλιαγμένης", "Vari-Voula-Vouliagmeni", 49194),
        ("Διονύσου", "Dionysos", 27395),
        ("Κρωπίας", "Kropia", 30250),
        ("Λαυρεωτικής", "Lavreotiki", 22105),
        ("Μαραθώνος", "Marathon", 33423),
        ("Μαρκοπούλου Μεσογαίας", "Markopoulo Mesogaias", 20579),
        ("Παιανίας", "Paiania", 26753),
        ("Παλλήνης", "Pallini", 54390),
        ("Ραφήνας-Πικερμίου", "Rafina-Pikermi", 21529),
        ("Σαρωνικού", "Saronikos", 17978),
        ("Σπάτων-Αρτέμιδος", "Spata-Artemida", 30800),
        ("Ωρωπού", "Oropos", 28789),
        # Δυτική Αττική
        ("Ασπροπύργου", "Aspropyrgos", 33565),
        ("Ελευσίνας", "Elefsina", 29902),
        ("Μάνδρας-Ειδυλλίας", "Mandra-Eidyllia", 19879),
        ("Μεγαρέων", "Megara", 34625),
        ("Φυλής", "Fyli", 45164),
    ],

    # ── GR-B: ΚΕΝΤΡΙΚΗ ΜΑΚΕΔΟΝΙΑ (38 dimoi) ──────────────────
    "GR-B": [
        ("Θεσσαλονίκης", "Thessaloniki", 325182),
        ("Αμπελοκήπων-Μενεμένης", "Ampelokipoi-Menemeni", 52127),
        ("Θερμαϊκού", "Thermaikos", 50264),
        ("Θέρμης", "Thermi", 53201),
        ("Καλαμαριάς", "Kalamaria", 91518),
        ("Κορδελιού-Ευόσμου", "Kordelio-Evosmos", 101753),
        ("Νεάπολης-Συκεών", "Neapoli-Sykies", 84741),
        ("Παύλου Μελά", "Pavlos Melas", 99245),
        ("Πυλαίας-Χορτιάτη", "Pylaia-Chortiatis", 70110),
        ("Ωραιοκάστρου", "Oraiokastro", 38317),
        ("Βόλβης", "Volvi", 22397),
        ("Δέλτα", "Delta", 45839),
        ("Λαγκαδά", "Lagkadas", 41103),
        ("Χαλκηδόνος", "Chalkidona", 33673),
        # Σέρρες
        ("Σερρών", "Serres", 76817),
        ("Αμφίπολης", "Amfipoli", 9182),
        ("Βισαλτίας", "Visaltia", 20039),
        ("Εμμανουήλ Παππά", "Emmanouil Pappas", 14051),
        ("Ηράκλειας", "Irakleia", 16954),
        ("Νέας Ζίχνης", "Nea Zichni", 11670),
        ("Σιντικής", "Sintiki", 21122),
        # Ημαθία
        ("Βέροιας", "Veroia", 66547),
        ("Αλεξάνδρειας", "Alexandria", 41570),
        ("Νάουσας", "Naoussa", 32494),
        # Κιλκίς
        ("Κιλκίς", "Kilkis", 51926),
        ("Παιονίας", "Paionia", 28905),
        # Πέλλα
        ("Έδεσσας", "Edessa", 28814),
        ("Αλμωπίας", "Almopia", 26456),
        ("Πέλλας", "Pella", 63122),
        ("Σκύδρας", "Skydra", 18098),
        # Πιερία
        ("Κατερίνης", "Katerini", 85851),
        ("Δίου-Ολύμπου", "Dion-Olympos", 25668),
        ("Πύδνας-Κολινδρού", "Pydna-Kolindros", 22861),
        # Χαλκιδική
        ("Πολυγύρου", "Polygyros", 22048),
        ("Αριστοτέλη", "Aristotelis", 18520),
        ("Κασσάνδρας", "Kassandra", 15659),
        ("Νέας Προποντίδας", "Nea Propontida", 37107),
        ("Σιθωνίας", "Sithonia", 12394),
    ],

    # ── GR-G: ΔΥΤΙΚΗ ΕΛΛΑΔΑ (19 dimoi) ──────────────────────
    "GR-G": [
        # Αχαΐα
        ("Πατρέων", "Patras", 213984),
        ("Αιγιαλείας", "Aigialia", 49872),
        ("Δυτικής Αχαΐας", "Western Achaia", 14847),
        ("Ερυμάνθου", "Erymanthos", 8409),
        ("Καλαβρύτων", "Kalavryta", 17242),
        # Αιτωλοακαρνανία
        ("Αγρινίου", "Agrinio", 94181),
        ("Μεσολογγίου", "Messolonghi", 34416),
        ("Ναυπακτίας", "Nafpaktia", 27800),
        ("Θέρμου", "Thermo", 6889),
        ("Ξηρομέρου", "Xeromero", 10332),
        ("Αμφιλοχίας", "Amfilochia", 19410),
        ("Ακτίου-Βόνιτσας", "Aktio-Vonitsa", 22956),
        # Ηλεία
        ("Πύργου", "Pyrgos", 54985),
        ("Ήλιδας", "Ilida", 32637),
        ("Ανδραβίδας-Κυλλήνης", "Andravida-Kyllini", 21352),
        ("Αρχαίας Ολυμπίας", "Ancient Olympia", 13409),
        ("Ανδρίτσαινας-Κρεστένων", "Andritsaina-Krestena", 11091),
        ("Ζαχάρως", "Zacharo", 14635),
        ("Πηνειού", "Pineios", 12857),
    ],

    # ── GR-E: ΘΕΣΣΑΛΙΑ (25 dimoi) ────────────────────────────
    "GR-E": [
        # Λάρισα
        ("Λαρισαίων", "Larissa", 162591),
        ("Αγιάς", "Agia", 11356),
        ("Ελασσόνας", "Elassona", 32121),
        ("Κιλελέρ", "Kileler", 19799),
        ("Τεμπών", "Tempi", 13457),
        ("Τυρνάβου", "Tyrnavos", 24010),
        ("Φαρσάλων", "Farsala", 18498),
        # Μαγνησία
        ("Βόλου", "Volos", 144449),
        ("Αλμυρού", "Almyros", 18614),
        ("Ζαγοράς-Μουρεσίου", "Zagora-Mouresi", 5765),
        ("Νοτίου Πηλίου", "South Pelion", 9186),
        ("Ρήγα Φεραίου", "Rigas Feraios", 10811),
        ("Αλοννήσου", "Alonnisos", 2750),
        ("Σκιάθου", "Skiathos", 6088),
        ("Σκοπέλου", "Skopelos", 4960),
        # Τρίκαλα
        ("Τρικκαίων", "Trikala", 81355),
        ("Καλαμπάκας", "Kalabaka", 21991),
        ("Πύλης", "Pyli", 13298),
        ("Φαρκαδόνας", "Farkadona", 14218),
        # Καρδίτσα
        ("Καρδίτσας", "Karditsa", 56747),
        ("Μουζακίου", "Mouzaki", 14658),
        ("Παλαμά", "Palamas", 15820),
        ("Σοφάδων", "Sofades", 18050),
        ("Αργιθέας", "Argithea", 3387),
        ("Λίμνης Πλαστήρα", "Lake Plastiras", 4316),
    ],

    # ── GR-M: ΚΡΗΤΗ (24 dimoi) ───────────────────────────────
    "GR-M": [
        # Ηράκλειο
        ("Ηρακλείου", "Heraklion", 173993),
        ("Αρχανών-Αστερουσίων", "Archanes-Asterousia", 18500),
        ("Βιάννου", "Viannos", 5563),
        ("Γόρτυνας", "Gortyna", 14628),
        ("Μαλεβιζίου", "Malevizi", 27600),
        ("Μινώα Πεδιάδος", "Minoa Pediados", 17563),
        ("Φαιστού", "Phaistos", 24466),
        ("Χερσονήσου", "Hersonissos", 27993),
        # Χανιά
        ("Χανίων", "Chania", 108642),
        ("Αποκορώνου", "Apokoronas", 14278),
        ("Γαύδου", "Gavdos", 152),
        ("Κανδάνου-Σελίνου", "Kandanos-Selino", 5895),
        ("Κισσάμου", "Kissamos", 10411),
        ("Πλατανιά", "Platanias", 20942),
        ("Σφακίων", "Sfakia", 2035),
        # Ρέθυμνο
        ("Ρεθύμνης", "Rethymno", 55525),
        ("Αγίου Βασιλείου", "Agios Vasileios", 10079),
        ("Ανωγείων", "Anogeia", 2432),
        ("Αμαρίου", "Amari", 5975),
        ("Μυλοποτάμου", "Mylopotamos", 14368),
        # Λασίθι
        ("Αγίου Νικολάου", "Agios Nikolaos", 27074),
        ("Ιεράπετρας", "Ierapetra", 27756),
        ("Οροπεδίου Λασιθίου", "Lasithi Plateau", 2145),
        ("Σητείας", "Siteia", 18318),
    ],

    # ── GR-J: ΠΕΛΟΠΟΝΝΗΣΟΣ (26 dimoi) ────────────────────────
    "GR-J": [
        # Αρκαδία
        ("Τρίπολης", "Tripoli", 47254),
        ("Βόρειας Κυνουρίας", "North Kynouria", 8096),
        ("Γορτυνίας", "Gortynia", 10405),
        ("Μεγαλόπολης", "Megalopoli", 11122),
        ("Νότιας Κυνουρίας", "South Kynouria", 8611),
        # Μεσσηνία
        ("Καλαμάτας", "Kalamata", 69849),
        ("Δυτικής Μάνης", "Western Mani", 10460),
        ("Μεσσήνης", "Messini", 26209),
        ("Οιχαλίας", "Oichalia", 12037),
        ("Πύλου-Νέστορος", "Pylos-Nestor", 21335),
        ("Τριφυλίας", "Trifylia", 25372),
        # Λακωνία
        ("Σπάρτης", "Sparta", 35259),
        ("Ανατολικής Μάνης", "East Mani", 12622),
        ("Ευρώτα", "Evrotas", 17478),
        ("Μονεμβασίας", "Monemvasia", 22139),
        ("Ελαφονήσου", "Elafonisos", 1049),
        # Αργολίδα
        ("Ναυπλιέων", "Nafplio", 33356),
        ("Άργους-Μυκηνών", "Argos-Mycenae", 42022),
        ("Επιδαύρου", "Epidavros", 8115),
        ("Ερμιονίδας", "Ermionida", 13327),
        # Κορινθία
        ("Κορινθίων", "Corinth", 58192),
        ("Βέλου-Βόχας", "Velo-Vocha", 18630),
        ("Λουτρακίου-Περαχώρας-Αγ.Θεοδώρων", "Loutraki-Perachora", 27089),
        ("Νεμέας", "Nemea", 6725),
        ("Ξυλοκάστρου-Ευρωστίνης", "Xylokastro-Evrostini", 18426),
        ("Σικυωνίων", "Sicyon", 23460),
    ],

    # ── GR-A: ΑΝΑΤΟΛΙΚΗ ΜΑΚΕΔΟΝΙΑ & ΘΡΑΚΗ (22 dimoi) ────────
    "GR-A": [
        # Έβρος
        ("Αλεξανδρούπολης", "Alexandroupoli", 72959),
        ("Διδυμοτείχου", "Didymoteicho", 19493),
        ("Ορεστιάδας", "Orestiada", 37695),
        ("Σαμοθράκης", "Samothrace", 2859),
        ("Σουφλίου", "Soufli", 12212),
        # Ξάνθη
        ("Ξάνθης", "Xanthi", 65133),
        ("Αβδήρων", "Avdira", 19346),
        ("Μύκης", "Myki", 14767),
        ("Τοπείρου", "Topeiros", 10851),
        # Ροδόπη
        ("Κομοτηνής", "Komotini", 66919),
        ("Αρριανών", "Arriana", 13879),
        ("Ιάσμου", "Iasmos", 12671),
        ("Μαρωνείας-Σαπών", "Maroneia-Sapes", 14497),
        # Δράμα
        ("Δράμας", "Drama", 58944),
        ("Δοξάτου", "Doxato", 13349),
        ("Κάτω Νευροκοπίου", "Kato Nevrokopi", 7081),
        ("Παρανεστίου", "Paranesti", 4215),
        ("Προσοτσάνης", "Prosotsani", 13009),
        # Καβάλα
        ("Καβάλας", "Kavala", 70501),
        ("Θάσου", "Thasos", 13770),
        ("Νέστου", "Nestos", 22331),
        ("Παγγαίου", "Pangaio", 31521),
    ],

    # ── GR-D: ΗΠΕΙΡΟΣ (18 dimoi) ─────────────────────────────
    "GR-D": [
        # Ιωάννινα
        ("Ιωαννιτών", "Ioannina", 112486),
        ("Βορείων Τζουμέρκων", "North Tzoumerka", 6582),
        ("Δωδώνης", "Dodoni", 10924),
        ("Ζαγορίου", "Zagori", 3700),
        ("Ζίτσας", "Zitsa", 14682),
        ("Κόνιτσας", "Konitsa", 6180),
        ("Μετσόβου", "Metsovo", 6196),
        ("Πωγωνίου", "Pogoni", 7875),
        # Άρτα
        ("Άρτας", "Arta", 43000),
        ("Γεωργίου Καραϊσκάκη", "Georgiou Karaiskaki", 6076),
        ("Κεντρικών Τζουμέρκων", "Central Tzoumerka", 5478),
        ("Νικολάου Σκουφά", "Nikolaos Skoufas", 13426),
        # Πρέβεζα
        ("Πρέβεζας", "Preveza", 31733),
        ("Ζηρού", "Ziros", 9012),
        ("Πάργας", "Parga", 11233),
        # Θεσπρωτία
        ("Ηγουμενίτσας", "Igoumenitsa", 25039),
        ("Σουλίου", "Souli", 6098),
        ("Φιλιατών", "Filiates", 7973),
    ],

    # ── GR-C: ΔΥΤΙΚΗ ΜΑΚΕΔΟΝΙΑ (12 dimoi) ────────────────────
    "GR-C": [
        # Κοζάνη
        ("Κοζάνης", "Kozani", 71388),
        ("Βοΐου", "Voio", 16612),
        ("Εορδαίας", "Eordaia", 44979),
        ("Σερβίων", "Servia", 16855),
        # Καστοριά
        ("Καστοριάς", "Kastoria", 35763),
        ("Νεστορίου", "Nestorio", 3067),
        ("Ορεστίδος", "Orestida", 12992),
        # Φλώρινα
        ("Φλώρινας", "Florina", 32282),
        ("Αμυνταίου", "Amyntaio", 15047),
        ("Πρεσπών", "Prespes", 2371),
        # Γρεβενά
        ("Γρεβενών", "Grevena", 25905),
        ("Δεσκάτης", "Deskati", 6055),
    ],

    # ── GR-H: ΣΤΕΡΕΑ ΕΛΛΑΔΑ (25 dimoi) ──────────────────────
    "GR-H": [
        # Φθιώτιδα
        ("Λαμιέων", "Lamia", 75315),
        ("Αμφίκλειας-Ελάτειας", "Amfiklia-Elateia", 11127),
        ("Δομοκού", "Domokos", 12322),
        ("Λοκρών", "Lokri", 19623),
        ("Μακρακώμης", "Makrakomi", 14553),
        ("Μώλου-Αγ.Κωνσταντίνου", "Molos-Ag.Konstantinos", 12321),
        ("Στυλίδος", "Stylida", 12727),
        # Φωκίδα
        ("Δελφών", "Delphi", 26117),
        ("Δωρίδος", "Dorida", 13040),
        # Βοιωτία
        ("Λεβαδέων", "Livadeia", 31006),
        ("Αλιάρτου-Θεσπιέων", "Aliartos-Thespies", 11041),
        ("Διστόμου-Αράχοβας-Αντίκυρας", "Distomo-Arachova-Antikyra", 10113),
        ("Θηβαίων", "Thebes", 36477),
        ("Ορχομενού", "Orchomenos", 11364),
        ("Τανάγρας", "Tanagra", 19432),
        # Εύβοια
        ("Χαλκιδέων", "Chalkida", 92809),
        ("Διρφύων-Μεσσαπίων", "Dirfyes-Messapies", 17937),
        ("Ερέτριας", "Eretria", 13053),
        ("Ιστιαίας-Αιδηψού", "Istiaia-Aidipsos", 16938),
        ("Καρύστου", "Karystos", 12682),
        ("Κύμης-Αλιβερίου", "Kymi-Aliveri", 24812),
        ("Μαντουδίου-Λίμνης-Αγ.Άννας", "Mantoudi-Limni-Agia Anna", 10519),
        ("Σκύρου", "Skyros", 2994),
        # Ευρυτανία
        ("Καρπενησίου", "Karpenisi", 11039),
        ("Αγράφων", "Agrafa", 5441),
    ],

    # ── GR-F: ΙΟΝΙΑ ΝΗΣΙΑ (7 dimoi) ──────────────────────────
    "GR-F": [
        ("Κερκυραίων", "Corfu", 102071),
        ("Παξών", "Paxoi", 2374),
        ("Λευκάδας", "Lefkada", 23693),
        ("Μεγανησίου", "Meganisi", 1040),
        ("Κεφαλονιάς", "Cephalonia", 35801),
        ("Ιθάκης", "Ithaca", 3084),
        ("Ζακύνθου", "Zakynthos", 40759),
    ],

    # ── GR-K: ΒΟΡΕΙΟ ΑΙΓΑΙΟ (9 dimoi) ────────────────────────
    "GR-K": [
        # Λέσβος
        ("Μυτιλήνης", "Mytilene", 37890),
        ("Δυτικής Λέσβου", "West Lesvos", 17675),
        # Χίος
        ("Χίου", "Chios", 26850),
        ("Οινουσσών", "Oinousses", 826),
        ("Ψαρών", "Psara", 458),
        # Σάμος
        ("Ανατολικής Σάμου", "East Samos", 15893),
        ("Δυτικής Σάμου", "West Samos", 17250),
        ("Ικαρίας", "Ikaria", 8423),
        ("Φούρνων Κορσεών", "Fournoi Korseon", 1459),
    ],

    # ── GR-L: ΝΟΤΙΟ ΑΙΓΑΙΟ (34 dimoi) ────────────────────────
    "GR-L": [
        # Κυκλάδες
        ("Σύρου-Ερμούπολης", "Syros-Ermoupoli", 21507),
        ("Άνδρου", "Andros", 9221),
        ("Τήνου", "Tinos", 8636),
        ("Μυκόνου", "Mykonos", 10134),
        ("Νάξου και Μικρών Κυκλάδων", "Naxos", 20009),
        ("Πάρου", "Paros", 15516),
        ("Αντιπάρου", "Antiparos", 1211),
        ("Μήλου", "Milos", 5129),
        ("Σίφνου", "Sifnos", 2625),
        ("Σερίφου", "Serifos", 1420),
        ("Κιμώλου", "Kimolos", 910),
        ("Κέας", "Kea", 2455),
        ("Κύθνου", "Kythnos", 1456),
        ("Αμοργού", "Amorgos", 1973),
        ("Ίου", "Ios", 2024),
        ("Σίκινου", "Sikinos", 274),
        ("Φολεγάνδρου", "Folegandros", 765),
        ("Θήρας", "Thira (Santorini)", 15550),
        ("Ανάφης", "Anafi", 271),
        # Δωδεκάνησα
        ("Ρόδου", "Rhodes", 115490),
        ("Κω", "Kos", 33388),
        ("Καλύμνου", "Kalymnos", 16179),
        ("Λέρου", "Leros", 7917),
        ("Πάτμου", "Patmos", 3047),
        ("Αστυπάλαιας", "Astypalaia", 1334),
        ("Κάσου", "Kasos", 1065),
        ("Καρπάθου", "Karpathos", 6226),
        ("Λειψών", "Lipsi", 790),
        ("Μεγίστης", "Megisti (Kastellorizo)", 492),
        ("Νισύρου", "Nisyros", 1008),
        ("Σύμης", "Symi", 2590),
        ("Τήλου", "Tilos", 780),
        ("Χάλκης", "Chalki", 478),
        ("Αγαθονησίου", "Agathonisi", 185),
    ],
}


async def seed():
    async with AsyncSessionLocal() as db:
        # ── Periferias (upsert) ──
        inserted_p = 0
        updated_p = 0
        for name_el, name_en, code in PERIFERIAS:
            existing = (await db.execute(
                select(Periferia).where(Periferia.code == code)
            )).scalar_one_or_none()
            if existing:
                existing.name_el = name_el
                existing.name_en = name_en
                updated_p += 1
            else:
                db.add(Periferia(name_el=name_el, name_en=name_en, code=code, is_active=True))
                inserted_p += 1
        await db.commit()
        print(f"Periferias: {inserted_p} inserted, {updated_p} updated")

        # ── Fetch periferia IDs ──
        periferias = {p.code: p.id for p in (await db.execute(select(Periferia))).scalars().all()}

        # ── Dimoi (upsert on name_el + periferia_id) ──
        inserted_d = 0
        updated_d = 0
        for code, dimoi in DIMOI.items():
            periferia_id = periferias.get(code)
            if not periferia_id:
                print(f"  WARNING: periferia {code} not found, skipping")
                continue
            for name_el, name_en, pop in dimoi:
                existing = (await db.execute(
                    select(Dimos).where(Dimos.name_el == name_el, Dimos.periferia_id == periferia_id)
                )).scalar_one_or_none()
                if existing:
                    existing.name_en = name_en
                    existing.population = pop
                    updated_d += 1
                else:
                    db.add(Dimos(
                        name_el=name_el, name_en=name_en,
                        periferia_id=periferia_id, population=pop, is_active=True
                    ))
                    inserted_d += 1
        await db.commit()
        print(f"Dimoi: {inserted_d} inserted, {updated_d} updated")

        # ── Summary ──
        total = sum(len(v) for v in DIMOI.values())
        print(f"\nTotal: 13 periferias, {total} dimoi seeded.")

    await engine.dispose()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(seed())

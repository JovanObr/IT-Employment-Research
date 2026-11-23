## Katere podatke smo uporabili in zakaj (5.-6. poglavje)

| Vir | Kaj meri | Obdobje | Kaj smo vzeli | Zakaj | Poglavje |
|---|---|---|---|---|---|
| **Hacker News**, niti »Who is hiring?« (prek javnega vmesnika Algolia) | objave podjetij, ki iščejo ljudi, ena nit na mesec | januar 2015 – oktober 2026 (81.495 objav v 140 mesecih) | ali objava omenja delo na daljavo (»remote«) in umetno inteligenco (AI, ML, LLM, strojno učenje …); mesečni deleži | edini javni vir z besedilom objav za delo skozi vsa leta | 5 |
| **Indeed Hiring Lab**, sledilnik dela na daljavo | delež oglasov, ki ponujajo delo na daljavo ali hibridno delo | 1. 1. 2019 – 30. 9. 2026, dnevno | ZDA, oglasi za razvoj programske opreme; mesečna in letna povprečja | preverba Hacker News na največjem portalu za zaposlitve | 5 |
| **BLS QCEW** (ameriški statistični urad za delo, popis zaposlenih in podjetij) | število zaposlenih in podjetij po panogah in mestnih območjih, četrtletno | 2019 in 2024 (403 mestna območja, 263 z objavljenim številom zaposlenih v obeh letih) | IT storitve (koda 5415), zasebni sektor: zaposleni in število podjetij | uradni popis skoraj vseh delovnih mest v ZDA | 6 |
| **Census ACS** in **FHFA** (ameriški urad za popis prebivalstva, agencija za stanovanjsko financiranje) | imena mestnih območij | ACS 2019 in 2024 | samo ime (iz njega zvezna država in obala) | ime območja ni v datoteki QCEW | 6 |
| **Census Gazetteer** | lega mestnih območij | razmejitev 2023 | koordinate za zemljevid | zemljevid v 8. zvezku | 6 |
| **Brookings** (Muro in You, 2022) | seznam velikih tehnoloških središč in hitro rastočih mest | objava 2022 | imena 17 mest v dveh skupinah | skupine je določil nekdo drug, pred našimi podatki | 6 |
| **Eurostat**, anketa o delovni sili (`isoc_sks_itspt`) | strokovnjaki IKT kot delež vseh zaposlenih in v tisočih | 2015 – 2025, letno, 27 držav EU in povprečje EU | delež (%) in število (tisoč) | uradna primerljiva statistika za vse države EU | 6 |

**Kaj smo s podatki naredili, preden smo karkoli testirali** (podrobno v `docs/methods/A.md`, `B.md`, `A2.md`, `F.md`):

- Hacker News: štejemo samo prve objave v niti (ne odgovorov). Objava »omenja delo na daljavo«, če vsebuje besedo »remote«; zanikanje (»no remote«) se ne upošteva, zato so deleži približni. Besedil objav ne objavimo, le mesečne deleže.
- Dela za začetnike nismo merili: pravilo smo preverili na 240 ročno prebranih objavah in ni doseglo vnaprej zapisanega praga (natančnost 37 % namesto vsaj 80 %).
- QCEW: četrtletje, v katerem urad števila zaposlenih ne objavi (zaradi zaupnosti), štejemo kot manjkajoče, nikoli kot nič. Rast 2019 → 2024 primerja ista četrtletja v obeh letih (243 območij), če to ni mogoče, povprečje objavljenih četrtletij (20 območij); 140 območij nima rasti. Območja, ki so leta 2023 dobila novo kodo, smo povezali s staro (`config/qcew_code_crosswalk.csv`).
- Obali: po prvi zvezni državi v imenu mesta, s seznamom držav, zapisanim pred testom.
- Eurostat: vrednosti uporabimo, kot so objavljene; ocene (oznaka »e«) in prelom metode leta 2021 (oznaka »b«) so našteti v rezultatih. Primerjave sprememb se začnejo leta 2021.

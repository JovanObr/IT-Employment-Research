## Katere podatke smo uporabili in zakaj (1.-4. poglavje)

Vsi podatki so javni. Za vsak vir: kaj meri, katero obdobje, katere podatke smo iz njega vzeli, zakaj smo ga izbrali in kje ga uporabimo.

| Vir | Kaj meri | Obdobje | Kaj smo vzeli | Zakaj | Poglavje |
|---|---|---|---|---|---|
| **Layoffs.fyi** (javni seznam, zbirajo prostovoljci iz novic) | napovedi odpuščanj v tehnoloških podjetjih po svetu | 11. 3. 2020 – 8. 10. 2026 (4.626 napovedi, od tega 2.910 v ZDA) | podjetje, datum, število ljudi, delež zaposlenih, država | edini javni seznam po podjetjih in datumih | 1, 2, 3, 4 |
| **Challenger, Gray & Christmas** (kadrovsko podjetje, objavlja mesečno) | napovedana odpuščanja ameriških podjetij v tehnološkem sektorju | 2022 – 2025 (letne in nekatere mesečne številke, ročno prepisane iz poročil) | skupno število ljudi | neodvisna kontrola našega glavnega vira | 1 |
| **Indeed Hiring Lab** (raziskovalni oddelek portala Indeed) | število oglasov za delo, indeks (1. 2. 2020 = 100) | 1. 2. 2020 – oktober 2026, dnevno | ZDA: oglasi za razvoj programske opreme in vsi oglasi; mesečna povprečja | najhitrejši znak, koliko ljudi podjetja iščejo | 1, 8 |
| **FRED** (Zvezna rezervna banka St. Louis) | obrestna mera ameriške centralne banke | januar 2015 – oktober 2026, mesečno | obrestna mera (»federal funds rate«) | cena denarja: ali so odpuščanja prišla, ko se je podražil | 2 |
| **BLS JOLTS** (ameriški statistični urad za delo) | mesečna stopnja odpuščanj po panogah | januar 2015 – avgust 2026 | informacijski sektor in vse panoge | uradna statistika, ki zajame tudi podjetja, ki niso v novicah | 2 |
| **SEC EDGAR, finančna poročila** (borzna agencija ZDA) | premoženje, prihodki, stroški javnih podjetij | 2019 – 2026, četrtletno (869 tehnoloških podjetij) | velikost (premoženje), rast prihodkov in stroškov | uradni, preverjeni podatki za vsako podjetje | 3 |
| **SEC EDGAR, letna poročila 10-K** | število zaposlenih na zadnji dan poslovnega leta | 2019, 2021 – 2025 (862 podjetij) | število zaposlenih, prebrano iz besedila poročila | edini javni podatek o zaposlenih po podjetjih | 3, 4 |
| **SEC EDGAR, poročila 8-K (točka 2.02)** | datumi četrtletnih poročil o poslovanju | 2020 – 2026 | datum vsakega poročila | da preverimo, ali napovedi sovpadajo s poročili | 4 |
| **SURS, register delovno aktivnega prebivalstva** (Statistični urad RS, tabela 0700921S) | vsi zaposleni in samozaposleni v Sloveniji po dejavnostih | januar 2015 – december 2025, mesečno | dejavnosti J62 in J63 (programiranje, svetovanje, druge informacijske dejavnosti) ter vsi zaposleni | register šteje vse, ne le vzorca: preveri padec, ki ga kaže anketa (hipoteza H) | 6 |
| **Yahoo Finance** | dnevne cene delnic | januar 2019 – oktober 2026 | cene ob dnevih objave odpuščanj in indeks celotne borze | odziv borze na napoved | 4 |

**Kaj smo s podatki naredili, preden smo karkoli testirali** (podrobno v `docs/methods/`):

- Iz seznama Layoffs.fyi ljudi štejemo le, kjer je število napisano (zato so vse številke spodnja meja). Kot napoved v ZDA štejemo podjetja s sedežem v ZDA.
- Podjetja s seznama smo z bazo SEC povezali po imenu: najprej ročno zapisana imena (`config/company_aliases.csv`), nato točno ujemanje, nato začetek imena, nato podobnost; vse razen ročnih in enoličnih točnih ujemanj je označeno za pregled.
- Število zaposlenih smo iz besedila letnih poročil prebrali s pravili; skok za več kot desetkrat v enem letu štejemo za napako branja in ga izpustimo.
- Tehnološka podjetja so tista z ustrezno panožno kodo (SIC) v bazi SEC.
- Dnevne podatke smo povprečili po mesecih ali tednih; datumi med vikendom se premaknejo na ponedeljek.

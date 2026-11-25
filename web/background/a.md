## Podjetja, vzroki in borza (1.-4. poglavje)

### Hipoteze in podrobni opisi metod

Vsaka hipoteza ima svoj opis: vprašanje, točni podatki in od kod, vsi koraki priprave podatkov s števili vrstic, test, koda, rezultati in omejitve.

| Hipoteza | Vprašanje | Odgovor | Opis metode |
|---|---|---|---|
| C (1. krog) | Ali so imela podjetja z napovedjo odpuščanj 2021-2023 večji padec zaposlenih? | ne moremo trditi | [C.md](https://github.com/JovanObr/IT-Employment-Research/blob/main/docs/methods/C.md) |
| D (1. krog) | Ali borza ponovljene napovedi kaznuje bolj kot prve? | ne moremo trditi | [D.md](https://github.com/JovanObr/IT-Employment-Research/blob/main/docs/methods/D.md) |
| C2 (2. krog) | Ali se napoved odpuščanj 2024 in 2025 pokaže v številu zaposlenih? | da | [C2.md](https://github.com/JovanObr/IT-Employment-Research/blob/main/docs/methods/C2.md) |
| E (2. krog) | Ali podjetja odpuščanja napovedo ob četrtletnih poročilih? | da | [E.md](https://github.com/JovanObr/IT-Employment-Research/blob/main/docs/methods/E.md) |
| H (3. krog) | Je delež IT v Sloveniji po registru zaposlenih 2021-2023 zrasel, čeprav anketa kaže padec? | da | [H.md](https://github.com/JovanObr/IT-Employment-Research/blob/main/docs/methods/H.md) |

Vnaprejšnje registracije: [1. krog](https://github.com/JovanObr/IT-Employment-Research/blob/main/docs/hypotheses/PREREGISTRATION.md), [2. krog (C2, E)](https://github.com/JovanObr/IT-Employment-Research/blob/main/docs/hypotheses/round2/C2_E.md), [3. krog (H)](https://github.com/JovanObr/IT-Employment-Research/blob/main/docs/hypotheses/round3/H.md). Datum in ura vsake registracije sta zapisana v zgodovini repozitorija (git), zato se vidi, da je bila zapisana pred rezultati.

### Vprašanja, ki jih pričakujemo

**Layoffs.fyi zbirajo prostovoljci. Zakaj bi mu verjeli?**
Ker smo ga preverili z dvema neodvisnima viroma. Za leto 2023 se s štetjem podjetja Challenger ujema na 6 % (178.725 proti 168.032 ljudi). In napovedi se pokažejo v uradnih letnih poročilih: podjetja z napovedjo so imela manj zaposlenih (hipoteza C2). Za 2024 in 2025 seznam ujame manj (približno 70-80 % Challengerjevega števila), zato v teh letih ne trdimo nič o obsegu.

**Ali obrestna mera res povzroči odpuščanja? Saj je to le časovno sovpadanje.**
Res je, ne trdimo vzroka. Pokažemo, da je skok napovedi po prvem zvišanju večji kot pri 95 % drugih datumov, in da ga ob izidu ChatGPT ni bilo. Isto vprašanje smo preverili na mestih (hipoteza B, San Francisco proti Austinu) in ga podatki niso potrdili. Zato v govoru rečemo »odpuščanja so prišla za dražjim denarjem«, ne »zaradi dražjega denarja«.

**Zakaj ste ChatGPT izločili? Saj podjetja govorijo o umetni inteligenci.**
Ne trdimo, da umetna inteligenca nima vpliva na delo, le da ni sprožila vala 2022-2023: ob izidu ChatGPT se je val že dogajal in se ni povečal (21,3 napovedi na teden prej, 21,6 potem). Vpliv na vrste del obravnava 5. poglavje.

**Zakaj se uradna statistika (JOLTS) ni premaknila?**
JOLTS meri ves informacijski sektor (telekomunikacije, mediji, programska oprema …), kjer so znana tehnološka podjetja le del zaposlenih. Val napovedi je bil v novicah velik, v celotnem sektorju pa manjši od običajnih nihanj.

**Zakaj mediane in permutacijski testi, ne povprečja in t-test?**
Število zaposlenih se včasih spremeni skokovito (prevzemi, napake pri branju poročil). Povprečje bi premaknila ena sama skrajna vrednost, mediana ne. Permutacijski test ne predpostavlja nobene oblike porazdelitve: oznake »z napovedjo« in »brez« naključno premešamo 10.000-krat in pogledamo, kako pogosto je razlika tako velika kot v resnici.

**Kako veste, da test ne najde učinka, ki ga ni?**
Za vsak test: (1) izmišljeni podatki z vstavljenim učinkom (test ga najde) in brez njega (ne najde), (2) placebo: test na premešanih podatkih, kjer zmotno najde nekaj v približno 5 % primerov (C2: 4,4 %; pri E premiki datumov za ±30 in ±45 dni niso dali nobenega učinka), (3) izračun najmanjšega učinka, ki ga test zanesljivo opazi.

**Zakaj je hipoteza C v 1. krogu padla, C2 v 2. krogu pa zdržala?**
C je primerjala obdobje 2021-2023, ki vključuje leto 2021, ko so ista podjetja še močno zaposlovala; v dveh letih se rast in padec verjetno delno izničita. Pri pogledu na 2022-2023 smo razliko opazili, a to je bil pogled po rezultatu, zato smo ga preverili na novih letih (2024, 2025) kot C2. Tako hipoteze ne potrdimo na podatkih, ki so jo navdihnili.

**Ali ste velikost podjetja upoštevali?**
Da. Velika podjetja so pogosteje na seznamu, tudi zato, ker so v novicah. Pri vseh primerjavah podjetij (rast zaposlovanja, prihodki) smo velikost upoštevali v modelu ali pa primerjali podjetja s samimi seboj skozi čas.

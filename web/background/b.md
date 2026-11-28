## Objave za delo, geografija, Evropa (5.-6. poglavje)

### Hipoteze in podrobni opisi metod

Vsaka hipoteza ima svoj opis: vprašanje, točni podatki in od kod, vsi koraki priprave podatkov s števili vrstic, test, koda, rezultati in omejitve.

| Hipoteza | Vprašanje | Odgovor | Opis metode |
|---|---|---|---|
| A (1. krog) | Ali je delež strokovnjakov IKT 2021-2024 v Sloveniji zrasel bolj kot v večini držav EU? | ne moremo trditi (delež je padel) | [A.md](https://github.com/JovanObr/IT-Employment-Research/blob/main/docs/methods/A.md) |
| B (1. krog) | Ali je San Francisco po zvišanju obrestne mere izgubil IT delovna mesta v primerjavi z Austinom? | ne moremo trditi | [B.md](https://github.com/JovanObr/IT-Employment-Research/blob/main/docs/methods/B.md) |
| A2 (2. krog) | Ali so države EU z več strokovnjaki IKT pred letom 2021 do 2024 rasle počasneje? | ne moremo trditi | [A2.md](https://github.com/JovanObr/IT-Employment-Research/blob/main/docs/methods/A2.md) |
| F (2. krog) | Ali je bila rast IT delovnih mest 2019-2024 na zahodni obali drugačna kot na vzhodni? | ne moremo trditi | [F.md](https://github.com/JovanObr/IT-Employment-Research/blob/main/docs/methods/F.md) |
| G (3. krog) | Ali so prosta delovna mesta v IKT v državah EU sledila domači centralni banki? | ne moremo trditi | [G.md](https://github.com/JovanObr/IT-Employment-Research/blob/main/docs/methods/G.md) |

Vnaprejšnji registraciji: [1. krog](https://github.com/JovanObr/IT-Employment-Research/blob/main/docs/hypotheses/PREREGISTRATION.md), [2. krog (A2, F)](https://github.com/JovanObr/IT-Employment-Research/blob/main/docs/hypotheses/round2/A2_F.md), [3. krog (G)](https://github.com/JovanObr/IT-Employment-Research/blob/main/docs/hypotheses/round3/G.md).

- **A:** Slovenija −0,50 odstotne točke, povprečje drugih 26 držav +0,58; po spremembi zadnja (27. od 27). Brez popravka p = 0,027, po popravku za štiri teste 0,107, in smer je nasprotna od napovedane.
- **B:** San Francisco je za Austinom zaostajal že pred zvišanjem obrestne mere; prelom po njem −5 % (razpon od −14 % do +5 %), p po popravku 0,579. Isti test na drugih parih mest najde »učinek« v 29 % primerov, zato je ta načrt šibak.
- **A2:** naklon −0,03 (razpon od −0,20 do +0,10), p = 0,734 (po popravku prav tako 0,734). Izhodišče Slovenije je bilo na 13. mestu od 27; po skupnem trendu bi morala zrasti za 0,6 točke.
- **F:** srednja rast 2 % na zahodu (41 mest) in 13 % na vzhodu (97 mest), razlika −10,7 točke (razpon od −25,4 do +14,5), p = 0,292, po popravku 0,585.
- **G:** ocena +0,02 točke prostih delovnih mest na točko dviga domače obrestne mere (razpon od −0,05 do +0,10), p = 0,52, po popravku za dva testa prav tako 0,52; smer je nasprotna od napovedane. Placebo: 3,9 % lažnih zadetkov. Test bi s 80-odstotno verjetnostjo našel učinek −0,16.

### Vprašanja, ki jih pričakujemo

**Ali so podatki za Slovenijo normalizirani? Majhna država ima vendar manj strokovnjakov.**
Da. Merimo delež strokovnjakov IKT med vsemi zaposlenimi, zato se velikost države izniči. Ne izniči pa se negotovost: anketa v majhni državi zajame manj ljudi, zato se ocena iz leta v leto bolj premika. Eurostat objavi tudi število ljudi: v Sloveniji 46,5 tisoč leta 2021, 37,2 tisoč leta 2023 in 45,2 tisoč leta 2025.

**Je bil slovenski rezultat posledica visokega izhodišča ali časa?**
Izhodišča ne: države z višjim deležem niso rasle počasneje (A2), Slovenija pa je začela na sredini. Čas pa je pomemben: leto 2021 je bilo za Slovenijo najvišje (4,8 %), najnižje leto 2023 (3,8 %), do 2025 se je delno vrnila (4,5 %). Primerjava od 2021 do 2024 se torej začne na slovenskem vrhu. Leto 2021 nismo izbrali zato, ampak ker je Eurostat takrat spremenil metodo ankete. Med 2015 in 2020 Slovenija ni rasla prej kot druge (+0,80 točke proti +0,87).

**Zakaj izhodišče iz let 2019-2020 in ne 2021?**
Če bi izhodišče in sprememba uporabljala isto številko za leto 2021, bi naključna napaka v tisti številki sama ustvarila navidezno dohitevanje (regresija k povprečju). S simulacijo smo preverili, da naš načrt zmotno najde učinek v 4,55 % primerov, kot mora.

**Zakaj Mann-Whitneyjev test pri obalah, ne t-test?**
Majhna mesta lahko zrastejo za 200 % ali več. Ena taka vrednost močno premakne povprečje, vrstnega reda pa skoraj ne. Test primerja vrstni red mest, ne povprečij.

**Kako ste določili obali?**
Po zveznih državah, zapisano vnaprej: zahod = Washington, Oregon, Kalifornija; vzhod = atlantske države od Maina do Floride, s Pensilvanijo in Washingtonom D.C. Mesto, ki leži v več državah, šteje k prvi državi v imenu. Tako k obali štejejo tudi mesta v notranjosti (Atlanta, Sacramento).

**Kaj pa mesta, za katera ni podatkov?**
Urad števila zaposlenih ne objavi, kadar bi lahko razkril podatke posameznega podjetja. Na vzhodu manjka 30 mest (med njimi Atlanta), na zahodu 4. Število podjetij urad vedno objavi; tudi tam je zahod rasel počasneje, a razlika prav tako ni dokazana (p = 0,117).

**Zakaj samo »IT storitve« (koda 5415)?**
To je edina IT panoga, za katero ameriški urad objavi dovolj mest v obeh letih (235 od 407 v preverjanju izvedljivosti). Podjetja, ki prodajajo lastne programe, so v drugih, ožjih kodah, ki jih urad objavi za premalo mest.

**Hacker News je forum zagonskih podjetij. Je to reprezentativno?**
Ne za ves trg, zato isto preverimo na Indeedu, največjem portalu za zaposlitve: oglasi za programerje z delom na daljavo 8 % (2019), 43 % (2022), 32,5 % (2026). Oba vira kažeta enak potek. Beseda »remote« šteje tudi, ko je zanikana (»no remote«), zato so deleži približni.

**Zakaj ne pokažete, kaj se je zgodilo z deli za mlade?**
Ker naše pravilo za prepoznavanje del za začetnike ni dovolj zanesljivo. Pri 240 ročno prebranih objavah je bilo pravilnih le 37 % označenih (zahtevali smo vsaj 80 %, prag smo zapisali vnaprej). Graf iz takega pravila bi lahko kazal napako pravila namesto spremembe na trgu.

**Ali umetna inteligenca odvzema delovna mesta?**
Tega ne testiramo. Pokažemo le, da jo objave za delo omenjajo vse pogosteje (17 % leta 2019, 57 % leta 2026), in da se je val odpuščanj začel pred ChatGPT (2. poglavje).

**Ali torej obresti niso vplivale na zaposlovanje v IT?**
Tega test ne pove. Meri le, ali je domača centralna banka vplivala poleg skupnega sunka, ki je hkrati zadel vse države (Fed, ECB, svetovni tehnološki cikel). Tega ne najdemo: v Češki, Madžarski, Poljski in Romuniji, ki so obresti dvignile leto pred ECB, so prosta mesta v IKT začela padati v istem četrtletju kot drugje (začetek 2022).

**Zakaj prosta delovna mesta in ne odpuščanja ali oglasi?**
Podatke o odpuščanjih in oglasih smo za to vprašanje že videli, zato bi bil test na njih nepošten. Eurostatove statistike prostih delovnih mest pred registracijo ni videl nihče od nas.

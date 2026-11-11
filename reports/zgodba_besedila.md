# Besedila zgodbe (za lektoriranje)

## 1_casovnica
**Kaj vidimo?** Na enem grafu je več črt: koliko odpuščanj so podjetja napovedala na teden, obrestna mera ameriške centralne banke (Fed), borzni indeks NASDAQ in, če so podatki na voljo, delež objav za delo na Hacker Newsu, ki omenjajo delo na daljavo oziroma umetno inteligenco. Vsako črto smo preračunali na lestvico od 0 do 100, da jih lahko primerjamo; ko miško premakneš na črto, vidiš pravo vrednost. Črtkani črti označujeta prvo zvišanje obrestne mere in izid ChatGPT. S spustnim menijem nad grafom preklopiš med številom napovedi in številom odpuščenih ljudi.

**Zakaj smo to naredili?** Hoteli smo videti, ali se te stvari dogajajo ob istem času. Številke imajo različne enote (število, odstotki, točke), zato jih brez preračuna ne bi mogli narisati na isto os.

**Kaj to pomeni?** V 26 tednih pred prvim zvišanjem obrestne mere (16. 3. 2022) je bilo povprečno 1,0 napovedi na teden, v 26 tednih po njem 15,4; obrestna mera je zrasla z 0,1 % na 5,3 %; borzni indeks NASDAQ je od vrha do dna izgubil 32 %. Če namesto napovedi štejemo ljudi, je bilo povprečno 392 napovedanih odpuščenih na teden pred zvišanjem obrestne mere in 1.427 po njem. Dražji denar, padec borze in val napovedanih odpuščanj so se torej zgodili v istem obdobju.

**Česa ne vemo?** Dogajanje ob istem času še ne dokazuje vzroka. Seznam odpuščanj beleži napovedi, ne števila dejansko odpuščenih ljudi, in je po letu 2022 postal bolj znan, zato se je lahko povečalo tudi samo beleženje.

**Viri podatkov:** Layoffs.fyi, javni seznam napovedi odpuščanj v tehnoloških podjetjih (ročno prenesen): `data/processed/layoffs_clean.csv`; FRED, Zvezna rezervna banka St. Louis (obrestna mera Fed in borzni indeks NASDAQ): `data/raw/fred_series.csv`; Hacker News, mesečne niti »Who is hiring?«, kjer podjetja objavljajo prosta delovna mesta: `data/raw/hn_whoishiring_posts.csv`. Graf bere obdelano datoteko `data/processed/hn_flags_monthly.csv` (izdela jo `python -m analysis.hn_text flags`).

## 1_koledar
**Kaj vidimo?** Vsaka vrstica je eno leto, vsak stolpec en teden v letu. Čim temnejše je polje, tem več odpuščanj so podjetja v tistem tednu napovedala. Prazna polja pomenijo, da za tisti teden nimamo podatkov. Ko miško premakneš na polje, vidiš točno število. S spustnim menijem preklopiš na število odpuščenih ljudi; pri tem se barva ustavi pri 95. percentilu, da en sam teden ne zasenči ostalih, točno število pa vidiš ob premiku miške.

**Zakaj smo to naredili?** Hoteli smo videti, ali so napovedi razporejene enakomerno ali pridejo v valovih.

**Kaj to pomeni?** Največ napovedi je bilo leta 2023 (859). Najbolj pretresljiv je bil teden z začetkom 30. 3. 2020, ko je bilo napovedanih 83 odpuščanj. Polovica vseh napovedi je padla v samo 51 od 342 tednov, torej v zelo kratkih valovih. Po številu ljudi je najbolj pretresljiv teden z začetkom 16. 1. 2023: napovedanih je bilo 27.691 odpuščenih.

**Česa ne vemo?** Seznam odpuščanj se je začel marca 2020, zato so prvi tedni prazni. Pozna se tudi to, da se beležijo predvsem znana podjetja.

**Viri podatkov:** Layoffs.fyi, javni seznam napovedi odpuščanj v tehnoloških podjetjih (ročno prenesen): `data/processed/layoffs_clean.csv`.

## 1_ljudje
**Kaj vidimo?** Zgornji graf kaže, koliko ljudi so podjetja v ZDA v posameznem četrtletju napovedala odpustiti; ko miško premakneš na stolpec, vidiš največje napovedi tistega četrtletja. Spodnji graf kaže sredino (mediano) deleža zaposlenih, ki ga je prizadela posamezna napoved: polovica napovedi je pod črto, polovica nad njo. Četrtletij s premalo znanimi deleži ne kažemo.

**Zakaj smo to naredili?** Število napovedi ne pove, koliko ljudi je izgubilo delo: ena velika napoved je lahko težja od desetin majhnih. Zato smo šteli tudi ljudi in delež zaposlenih.

**Kaj to pomeni?** Skupaj je bilo napovedanih 662.971 odpuščenih ljudi (pri napovedih, kjer je število znano). Največ jih je bilo v četrtletju 2023Q1: 124.185, med njimi Google (12.000), Meta (10.000), Microsoft (10.000). Sredina deleža zaposlenih, ki ga je prizadela posamezna napoved, je 15 %.

**Česa ne vemo?** Število ljudi je znano pri 63 % napovedi, delež zaposlenih pri 62 %; pri ostalih manjka, zato so vsote spodnja meja. Števila so tisto, kar so podjetja ali mediji objavili ob napovedi: gre za napovedi, ne za preverjene odhode. Seznam beleži predvsem znana podjetja in je zato nepopoln.

**Viri podatkov:** Layoffs.fyi, javni seznam napovedi odpuščanj v tehnoloških podjetjih (ročno prenesen): `data/processed/layoffs_clean.csv`.

## 1_najvecje
**Kaj vidimo?** Vsak stolpec je ena napoved odpuščanj: dolžina pove, koliko ljudi naj bi podjetje odpustilo. Ko miško premakneš na stolpec, vidiš datum in delež zaposlenih (če je znan).

**Zakaj smo to naredili?** Skupna številka skriva, kako neenakomerno so odpuščanja razporejena: nekaj velikih podjetij lahko odtehta stotine majhnih.

**Kaj to pomeni?** Deset največjih napovedi je skupaj 146.000 ljudi, to je 22 % vseh napovedanih odpuščenih z znanim številom, čeprav je vseh napovedi 1.847. Največja je Intel (2025) z 22.000 ljudmi (20 % zaposlenih).

**Česa ne vemo?** Gre za napovedana števila ob objavi, ne za dejansko izgubljena delovna mesta; podjetja jih pogosto razporedijo čez več mesecev ali držav. Delež zaposlenih ni znan pri vseh napovedih, seznam pa beleži predvsem znana podjetja.

**Viri podatkov:** Layoffs.fyi, javni seznam napovedi odpuščanj v tehnoloških podjetjih (ročno prenesen): `data/processed/layoffs_clean.csv`.

## 2_datumi
**Kaj vidimo?** Dva grafa: levi kaže tedne okoli prvega zvišanja obrestne mere Fed (16. 3. 2022), desni okoli izida ChatGPT (30. 11. 2022). Vsak stolpec je en teden, 26 tednov pred in 26 tednov po datumu. Siva polja so pred datumom, modra po njem, vodoravni črti pa kažeta povprečje pred in po. Zgornja vrstica šteje napovedi, spodnja odpuščene ljudi.

**Zakaj smo to naredili?** Pogosto slišimo, da sta ta dva trenutka prelomnici za odpuščanja. Preverili smo, ali se je število napovedi res spremenilo prav takrat.

**Kaj to pomeni?** Okoli zvišanja obrestne mere je bilo povprečje 1,0 napovedi na teden pred datumom in 15,4 po njem. Okoli izida ChatGPT 21,3 pred in 21,6 po datumu, torej skoraj nespremenjeno. Če za vsak teden v celotnem obdobju izračunamo enako primerjavo, je največji skok števila napovedi v tednu z začetkom 23. 5. 2022, približno 10 tednov po prvem zvišanju obrestne mere. Če namesto napovedi štejemo ljudi: okoli zvišanja obrestne mere je bilo povprečno 392 napovedanih odpuščenih na teden pred datumom in 1.427 po njem, okoli izida ChatGPT 3.244 pred in 5.730 po, torej naraslo. Število napovedi se ob ChatGPT torej ni spremenilo, število ljudi pa je naraslo: nekaj zelo velikih napovedi odtehta število.

**Česa ne vemo?** Datuma sta le osem mesecev narazen in v istem obdobju padanja borze, zato ju podatki ne morejo ločiti. Poleg tega seznam odpuščanj ne pove, ali je bil razlog umetna inteligenca, zato lahko le rečemo, kdaj se je število napovedi spremenilo, ne zakaj. Povprečje ljudi je zelo občutljivo na nekaj velikih napovedi, število ljudi pa ni znano pri vseh napovedih.

**Viri podatkov:** Layoffs.fyi, javni seznam napovedi odpuščanj v tehnoloških podjetjih (ročno prenesen): `data/processed/layoffs_clean.csv`.

## 2_zamiki
**Kaj vidimo?** Vsaka vrstica primerja eno makro številko (kako se je v zadnjih 12 mesecih spremenila obrestna mera ali borza) z enim merilom odpuščanj. Stolpci so zamiki v mesecih: kaj dobimo, če odpuščanja primerjamo z makro podatkom izpred nekaj mesecev (pozitiven zamik) ali nekaj mesecev pozneje (negativen). Modra pomeni, da se vrsti premikata v isto smer, rdeča v nasprotno; zvezdica označuje najmočnejši zamik.

**Zakaj smo to naredili?** Vprašali smo se, ali dražji denar in padec borze 'prehitevata' odpuščanja, in ali to velja za vsa merila: število napovedi, število odpuščenih ljudi in uradno statistiko.

**Kaj to pomeni?** Število napovedi se ujema s spremembo obrestne mere: korelacija 0,82, p = 0,02, kar pomeni, da bi tako dobro ujemanje videli le v približno 2 % naključnih premikov vrste po koledarju. Število napovedi se ujema s spremembo borze: korelacija -0,85, p = 0,02, kar pomeni, da bi tako dobro ujemanje videli le v približno 2 % naključnih premikov vrste po koledarju. Pri številu odpuščenih ljudi in pri uradni statistiki (JOLTS) povezave ni videti (p od 0,40 do 0,61). Z besedami: število napovedanih odpuščanj sledi obrestnim meram in borzi, a to ne pomeni nujno, da je odpuščenih več ljudi.

**Česa ne vemo?** Imamo en cikel obrestnih mer in okoli šest let podatkov, zato se skoraj vsaki dve vrsti, ki v tem času rasteta ali padata, ujemata; test to upošteva le delno. 12-mesečna sprememba zaostaja za pravo spremembo, zato zamik +1 ne pomeni, da je obrestna mera delovala mesec prej. Vzroka s tem ne dokažemo.

**Viri podatkov:** Layoffs.fyi, javni seznam napovedi odpuščanj v tehnoloških podjetjih (ročno prenesen): `data/processed/layoffs_clean.csv`; FRED, Zvezna rezervna banka St. Louis (obrestna mera Fed in borzni indeks NASDAQ): `data/raw/fred_series.csv`; ameriški statistični urad za delo (BLS), raziskava JOLTS o odpuščanjih in prostih mestih: `data/raw/bls_jolts.csv`.

## 2_rast
**Kaj vidimo?** Podjetja smo razvrstili v štiri enako velike skupine glede na to, kako hitro so rasla v letih 2019 do 2021: po rasti prihodkov, po rasti stroškov in po tem, ali so stroški rasli hitreje od prihodkov. Stolpec kaže, kolikšen delež podjetij iz skupine je v letih 2022 in 2023 napovedal odpuščanja.

**Zakaj smo to naredili?** Preverjamo pogosto razlago, da so podjetja v času razcveta zaposlovala preveč in morala zato kasneje odpuščati.

**Kaj to pomeni?** Med podjetji z najpočasnejšo rastjo prihodkov je odpuščanja napovedalo 5 %, med najhitreje rastočimi 23 %; delež narašča iz skupine v skupino. Če podjetja razvrstimo po tem, ali so stroški rasli hitreje od prihodkov, so deleži od 10 % do 20 % in ne naraščajo enakomerno. Hitra rast torej gre z odpuščanji, kar pa še ne pomeni, da so podjetja zaposlovala preveč glede na prihodke.

**Česa ne vemo?** Nimamo števila zaposlenih, zato stroški le približno nadomeščajo zaposlovanje (vključujejo tudi nakupe podjetij in plačevanje z delnicami). Hitro rastoča podjetja so pogosto bolj znana, zato jih seznam odpuščanj lažje zazna. V vsaki skupini je le nekaj deset podjetij, zato so razlike negotove.

**Viri podatkov:** SEC EDGAR, javna finančna poročila ameriških borznih podjetij: `data/raw/sec_financials_quarterly.csv`, `data/raw/sec_revenue_universe.csv`, `data/raw/sec_universe_sic.csv`, `data/raw/sec_company_matches.csv`; Layoffs.fyi, javni seznam napovedi odpuščanj v tehnoloških podjetjih (ročno prenesen): `data/processed/layoffs_clean.csv`.

## 3_velikost
**Kaj vidimo?** Podjetja smo po vrednosti njihovih sredstev razdelili v deset enako velikih skupin: od najmanjših (1) do največjih (10). Stolpec kaže, v kolikšnem deležu četrtletij je podjetju v naslednjih dveh četrtletjih sledila napoved odpuščanj. Ko miško premakneš na stolpec, vidiš število četrtletij.

**Zakaj smo to naredili?** Hoteli smo ugotoviti, kaj najbolj loči podjetja, ki se znajdejo na seznamu odpuščanj, od tistih, ki se ne.

**Kaj to pomeni?** Pri najmanjših podjetjih je napovedi sledilo 0,0 % četrtletij, pri največjih 15,0 %, torej veliko pogosteje. Velikost podjetja je v naših podatkih zelo močno sporočilo.

**Česa ne vemo?** Veliko podjetje je tudi bolj opazno: seznam odpuščanj beleži predvsem znana podjetja. Velikost zato verjetno meri tudi to, kako zanesljivo je podjetje sploh zabeleženo, ne le, kako veliko je tveganje za odpuščanja.

**Viri podatkov:** SEC EDGAR, javna finančna poročila ameriških borznih podjetij: `data/raw/sec_financials_quarterly.csv`, `data/raw/sec_revenue_universe.csv`, `data/raw/sec_universe_sic.csv`, `data/raw/sec_company_matches.csv`; Layoffs.fyi, javni seznam napovedi odpuščanj v tehnoloških podjetjih (ročno prenesen): `data/processed/layoffs_clean.csv`. Graf bere obdelano datoteko `data/processed/company_panel.csv` (izdela jo `python -m analysis.company_panel`).

## 3_modeli
**Kaj vidimo?** Primerjamo, kako dobro različni modeli razvrstijo podjetja od tistih, ki bodo po vsej verjetnosti napovedala odpuščanja, do tistih, ki jih ne bodo. Mera se imenuje PR-AUC: višja vrednost pomeni, da so podjetja, ki so res napovedala odpuščanja, višje na seznamu. Črtkana črta je rezultat naključnega ugibanja. Črte na stolpcih kažejo negotovost (z 95-odstotno zanesljivostjo je prava vrednost nekje v tem območju).

**Zakaj smo to naredili?** Zanimalo nas je, ali lahko iz javnih računovodskih podatkov podjetij vnaprej ocenimo, kdo bo napovedal odpuščanja, in še bolj, od česa je ta uspeh odvisen.

**Kaj to pomeni?** Logistični model doseže 0,22, kar je 4,1-krat boljše od naključja (0,05). Samo velikost podjetja doseže 0,28. Ko modelu velikost vzamemo, pade na 0,08 (1,5-krat boljše od naključja). Skoraj vse, kar modeli znajo, torej pride iz velikosti podjetja.

**Česa ne vemo?** Preizkušali smo na 386 napovedih odpuščanj, ki jih je dalo 131 podjetij v letih od 2023 naprej; učili smo se na starejših podatkih, ki jih je bilo bistveno manj. Model zna razvrščati, ne zna pa zanesljivo povedati, kako verjetno je odpuščanje (verjetnosti so v povprečju prenizke). Ne pove nam tudi, zakaj podjetja odpuščajo.

**Viri podatkov:** SEC EDGAR, javna finančna poročila ameriških borznih podjetij: `data/raw/sec_financials_quarterly.csv`, `data/raw/sec_revenue_universe.csv`, `data/raw/sec_universe_sic.csv`, `data/raw/sec_company_matches.csv`; Layoffs.fyi, javni seznam napovedi odpuščanj v tehnoloških podjetjih (ročno prenesen): `data/processed/layoffs_clean.csv`. Graf bere obdelano datoteko `data/processed/company_panel.csv` (izdela jo `python -m analysis.company_panel`).

## 3_skupine
**Kaj vidimo?** Podjetja smo razdelili v tretjine po velikosti. V vsaki tretjini vidimo, kolikokrat je model boljši od naključnega ugibanja (1 pomeni: nič boljši). Oranžni stolpci so modeli, ki poznajo velikost, modri tisti, ki je ne. Tretjine z občutno premalo napovedmi odpuščanj ne ocenjujemo.

**Zakaj smo to naredili?** Če velikost približno držimo na isti ravni, vidimo, ali ostane še kaj, iz česar bi lahko ocenili tveganje.

**Kaj to pomeni?** Med največjimi podjetji je model z velikostjo 2,6-krat boljši od naključja, brez velikosti pa 1,3-krat. Med srednje velikimi podjetji je model 1,7-krat boljši od naključja.

**Česa ne vemo?** V najmanjši tretjini je le 14 napovedi odpuščanj med 2.486 četrtletji, zato je izpustimo. Tudi znotraj tretjine so podjetja različno velika, zato velikost ni popolnoma izenačena. Število podjetij s pozitivnim izidom je omejeno, zato so razlike med modeli negotove.

**Viri podatkov:** SEC EDGAR, javna finančna poročila ameriških borznih podjetij: `data/raw/sec_financials_quarterly.csv`, `data/raw/sec_revenue_universe.csv`, `data/raw/sec_universe_sic.csv`, `data/raw/sec_company_matches.csv`; Layoffs.fyi, javni seznam napovedi odpuščanj v tehnoloških podjetjih (ročno prenesen): `data/processed/layoffs_clean.csv`. Graf bere obdelano datoteko `data/processed/company_panel.csv` (izdela jo `python -m analysis.company_panel`).

## 3_podjetja
**Kaj vidimo?** Vsaka pika je eno podjetje. Vodoravno je velikost (sredstva ob koncu 2019; lestvica se z vsako črto podeseteri), navpično rast prihodkov med letoma 2019 in 2021. Rdeče pike so podjetja, ki so v letih 2022 in 2023 napovedala odpuščanja, sive tista, ki niso. Črtkani črti sta mediani: pol podjetij je levo od navpične črte, pol desno, in enako za vodoravno. Ko miško premakneš na piko, vidiš ime podjetja.

**Zakaj smo to naredili?** Hoteli smo videti obe razlagi hkrati: ali odpuščajo predvsem velika podjetja, hitro rastoča podjetja ali oboja.

**Kaj to pomeni?** Med 94 podjetji, ki so nad mediano tako po velikosti kot po rasti (zgornji desni kot), je odpuščanja napovedalo 32 %, med ostalimi 242 pa 7 %, torej približno 4,8-krat pogosteje.

**Česa ne vemo?** Vsaka pika je le eno podjetje, zato so izjeme. Sredstva so le približek velikosti, rast prihodkov pa ne pove, koliko ljudi so podjetja zaposlila. Seznam odpuščanj beleži predvsem znana podjetja, zato so velika podjetja že vnaprej bolj vidna.

**Viri podatkov:** SEC EDGAR, javna finančna poročila ameriških borznih podjetij: `data/raw/sec_financials_quarterly.csv`, `data/raw/sec_revenue_universe.csv`, `data/raw/sec_universe_sic.csv`, `data/raw/sec_company_matches.csv`; Layoffs.fyi, javni seznam napovedi odpuščanj v tehnoloških podjetjih (ročno prenesen): `data/processed/layoffs_clean.csv`.

## 6_pot
**Kaj vidimo?** Graf kaže, kako se je cena delnice v povprečju gibala v dneh okoli objave odpuščanj, ko od njenega gibanja odštejemo gibanje celotne borze (temu rečemo nenavadni donos). Dan 0 je prvi trgovalni dan po objavi; sivo območje označuje dneva 0 in +1, ko borza novico prebavi. Črta je povprečje preko 611 objav, modro območje je 95-odstotna negotovost. Ko miško premakneš na točko, vidiš vrednost.

**Zakaj smo to naredili?** Zanima nas, ali vlagatelji objavo odpuščanj nagradijo ali kaznujejo, torej ali je za borzo novica dobra ali slaba.

**Kaj to pomeni?** V dneh 0 in +1 se je cena v povprečju znižala za 0,6 % (negotovost od -1,3 % do 0,1 %). Ker negotovost zajema ničlo, ne moremo trditi, da je sprememba več kot naključje. V dneh pred objavo ni opaznega premika, kar je dober znak: novica očitno ni pricurljala vnaprej.

**Česa ne vemo?** Podjetja odpuščanja pogosto objavijo skupaj z rezultati poslovanja ali opozorili vlagateljem, zato učinka odpuščanj ne moremo ločiti od druge novice istega dne. Datum na seznamu je lahko dan prepozen. Podjetja, ki so kasneje izginila z borze, v podatkih manjkajo. Gre za povprečje: posamezne objave se zelo razlikujejo. Preizkus na naključnih dnevih kaže, da naš test v 9 % primerov zazna učinek, ki ga ni (pričakovanih je 5 %). Intervali so zato nekoliko preozki, kar pri rezultatu, ki že zajema ničlo, sklepa ne spremeni.

**Viri podatkov:** Layoffs.fyi, javni seznam napovedi odpuščanj v tehnoloških podjetjih (ročno prenesen): `data/processed/layoffs_clean.csv`; SEC EDGAR, javna finančna poročila ameriških borznih podjetij: `data/raw/sec_company_matches.csv`; Yahoo Finance, dnevne cene delnic (prenesene s knjižnico yfinance): `data/raw/prices_daily.csv`.

## 6_porazdelitev
**Kaj vidimo?** Vsak stolpec šteje, koliko objav je imelo določen nenavadni donos v dneh 0 in +1 (v odstotkih). Rdeča črta je povprečje, oranžna mediana (sredinska vrednost, polovica objav je pod njo, polovica nad njo). Skrajne vrednosti smo skrčili na ±20 %, da je graf berljiv.

**Zakaj smo to naredili?** Povprečje lahko skriva, kako različne so posamezne objave, zato pogledamo vse.

**Kaj to pomeni?** Pri polovici objav se je cena premaknila za manj kot 3,0 %, pri devetih od desetih za manj kot 14,0 %. Navzgor jo je potisnilo 48 % objav, navzdol 52 %. Mediana je -0,2 %, povprečje -0,6 %.

**Česa ne vemo?** Razpršenost je tudi posledica običajnega nihanja posameznih delnic, ne le novice o odpuščanjih. Z nekaj sto objavami lahko govorimo o skupini podjetij, ne o posameznem podjetju.

**Viri podatkov:** Layoffs.fyi, javni seznam napovedi odpuščanj v tehnoloških podjetjih (ročno prenesen): `data/processed/layoffs_clean.csv`; SEC EDGAR, javna finančna poročila ameriških borznih podjetij: `data/raw/sec_company_matches.csv`; Yahoo Finance, dnevne cene delnic (prenesene s knjižnico yfinance): `data/raw/prices_daily.csv`.

## 6_skupine
**Kaj vidimo?** Levo so podjetja razdeljena v tretjine po velikosti, desno po letu objave. Pika je povprečni nenavadni donos v dneh 0 in +1, črte kažejo 95-odstotno negotovost. Če črta prečka ničlo, ne moremo reči, da se je cena sploh premaknila. Skupin z manj kot 10 objavami ne kažemo.

**Zakaj smo to naredili?** Zanima nas, ali je odziv borze drugačen pri majhnih in velikih podjetjih ali v različnih letih, na primer med največjim valom odpuščanj leta 2022 in pozneje.

**Kaj to pomeni?** Po velikosti: najmanjša tretjina: -0,8 % (od -2,4 do 0,8 %); srednja tretjina: -1,1 % (od -2,5 do 0,2 %); največja tretjina: 0,2 % (od -0,6 do 1,0 %). Razlika med najmanjšimi in največjimi podjetji je -1,0 odstotne točke (negotovost od -2,8 do 1,1), kar ni statistično zanesljivo. Po letih pri nobenem letu negotovost ne izključuje ničle, zato jasnega vzorca ni.

**Česa ne vemo?** V posamezni skupini je od nekaj deset do dvesto objav, zato so razlike negotove. Hkrati primerjamo več skupin, zato je lahko katera 'opazna' razlika tudi naključna. Velikost je merjena z vrednostjo sredstev pred objavo, ne z vrednostjo podjetja na borzi.

**Viri podatkov:** Layoffs.fyi, javni seznam napovedi odpuščanj v tehnoloških podjetjih (ročno prenesen): `data/processed/layoffs_clean.csv`; SEC EDGAR, javna finančna poročila ameriških borznih podjetij: `data/raw/sec_company_matches.csv`, `data/raw/sec_financials_quarterly.csv`; Yahoo Finance, dnevne cene delnic (prenesene s knjižnico yfinance): `data/raw/prices_daily.csv`.

## 4_teme_povrsina
**Kaj vidimo?** Vsaka barvna plast je ena tema, ki jo je računalnik sam našel v besedilih oglasov za delo. Debelina plasti pove, kolikšen delež objav v tistem mesecu govori predvsem o tej temi; skupaj plasti vedno dajo 100 %. Ko miško premakneš na plast, vidiš ime teme in njen delež; črtkani črti označujeta prvo zvišanje obrestne mere in ChatGPT.

**Zakaj smo to naredili?** Hoteli smo videti, ali se je spremenilo, o čem delodajalci pišejo, ko iščejo ljudi: o tehnologijah, o vrsti dela ali o podjetju.

**Kaj to pomeni?** V prvih 12 mesecih s podatki (1/2015 do 2/2016) je bila najpogostejša tema »razvoj poslovnih sistemov« (20 % objav), v zadnjih 12 mesecih pa »zagonska podjetja z UI in agenti« (42 %). Najbolj je narasla tema »zagonska podjetja z UI in agenti« (z 0 % na 42 %), najbolj je padla »mobilne aplikacije (iOS, Android)« (z 13 % na 2 %).

**Česa ne vemo?** Hacker News je kotiček trga, kjer prevladujejo zagonska podjetja (startupi) iz ZDA, zato ne predstavlja vseh delodajalcev. Teme je določil algoritem (vsaka objava je pripisana svoji najmočnejši temi), imena tem pa smo dali mi; z drugim številom tem bi bila razdelitev nekoliko drugačna. Graf kaže, o čem se piše, ne koliko ljudi je zaposlenih.

**Viri podatkov:** Hacker News, mesečne niti »Who is hiring?«, kjer podjetja objavljajo prosta delovna mesta: `data/raw/hn_whoishiring_posts.csv`, `data/raw/hn_whoishiring_text.csv`. Graf bere obdelano datoteko `data/processed/hn_topics_monthly.csv` (izdela jo `python -m analysis.hn_text run`).

## 4_teme_mali_grafi
**Kaj vidimo?** Vsak mali graf je ena od 10 tem. Tanka črta je delež objav v posameznem mesecu, debela pa povprečje zadnjih 12 mesecev, ki skrije mesečno nihanje. Vsi grafi imajo enako navpično os, zato so velikosti neposredno primerljive. Črtkana črta je datum izida ChatGPT (30. 11. 2022).

**Zakaj smo to naredili?** Na skupnem grafu se majhne teme izgubijo. Tukaj vidimo vsako posebej in lahko primerjamo, katera je rasla in katera padala.

**Kaj to pomeni?** Primerjali smo 12 mesecev pred izidom ChatGPT z zadnjimi 12 meseci (do 10/2026). Za vsaj eno odstotno točko je pridobilo 1 od 10 tem, izgubilo pa 8. Največ je pridobila »zagonska podjetja z UI in agenti« (+37,0 odstotne točke), največ izgubila »spletne tehnologije (React, Node, TypeScript)« (−7,3 odstotne točke).

**Česa ne vemo?** Hacker News je kotiček trga, kjer prevladujejo zagonska podjetja (startupi) iz ZDA, zato ne predstavlja vseh delodajalcev. Sprememba po datumu izida ChatGPT ne pomeni, da jo je povzročil ChatGPT: hkrati so se zviševale obrestne mere in zmanjševalo zaposlovanje. Imena tem so naša, teme pa je določil algoritem.

**Viri podatkov:** Hacker News, mesečne niti »Who is hiring?«, kjer podjetja objavljajo prosta delovna mesta: `data/raw/hn_whoishiring_posts.csv`, `data/raw/hn_whoishiring_text.csv`. Graf bere obdelano datoteko `data/processed/hn_topics_monthly.csv` (izdela jo `python -m analysis.hn_text run`).

## 4_teme_toplotna
**Kaj vidimo?** Vsaka vrstica je ena tema, vsak stolpec eno leto. Številka v polju je povprečen delež objav tistega leta v odstotkih; temnejše polje pomeni večji delež. Teme so razvrščene po spremembi: zgoraj tiste, ki so najbolj pridobile, spodaj tiste, ki so najbolj izgubile.

**Zakaj smo to naredili?** Mesečne številke precej nihajo. Letna povprečja dajo bolj miren pregled, katere teme so v zadnjih letih dobile prostor.

**Kaj to pomeni?** Primerjali smo prva leta (2015-2017) z zadnjimi (2024-2026). Najbolj je pridobila »zagonska podjetja z UI in agenti«: z 0,8 % na 31,2 % objav. Najbolj je izgubila »San Francisco in okolica«: z 13,7 % na 4,4 %.

**Česa ne vemo?** Hacker News je kotiček trga, kjer prevladujejo zagonska podjetja (startupi) iz ZDA, zato ne predstavlja vseh delodajalcev. Zadnje leto je lahko nepopolno (podatki ne pokrivajo vseh mesecev), zato je njegovo povprečje manj zanesljivo. Teme je določil algoritem, zato meje med njimi niso ostre.

**Viri podatkov:** Hacker News, mesečne niti »Who is hiring?«, kjer podjetja objavljajo prosta delovna mesta: `data/raw/hn_whoishiring_posts.csv`, `data/raw/hn_whoishiring_text.csv`. Graf bere obdelano datoteko `data/processed/hn_topics_monthly.csv` (izdela jo `python -m analysis.hn_text run`).

## 4_daljava_ui
**Kaj vidimo?** Modra črta je delež objav, ki omenjajo delo na daljavo, vijolična delež objav, ki omenjajo umetno inteligenco ali strojno učenje. Debele vodoravne stopnice so povprečna raven med dvema premikoma: računalnik je poiskal mesece, ko se je raven najbolj spremenila (»premik skozi čas«). Črtkane črte označujejo začetek pandemije, prvo zvišanje obrestne mere in ChatGPT.

**Zakaj smo to naredili?** Želeli smo videti, kdaj točno sta se spremenili dve stvari, o katerih se največ govori: delo na daljavo in umetna inteligenca.

**Kaj to pomeni?** Omembe dela na daljavo so v prvih 12 mesecih zajemale 21 % objav, v zadnjih 12 mesecih 54 % (delež je narasel); vrh je bil 2/2022 s 87 %. Večji premiki ravni so se zgodili 4/2020, 10/2020, 10/2023. Omembe umetne inteligence so v prvih 12 mesecih zajemale 10 % objav, v zadnjih 12 mesecih 57 % (delež je narasel); vrh je bil 8/2026 s 64 %. Večji premiki ravni so se zgodili 2/2023, 6/2024, 7/2025.

**Česa ne vemo?** Hacker News je kotiček trga, kjer prevladujejo zagonska podjetja (startupi) iz ZDA, zato ne predstavlja vseh delodajalcev. Oznake temeljijo na iskanju ključnih besed: objava, ki napiše »no remote«, šteje kot omemba dela na daljavo. Premiki skozi čas so ocena (iskali smo največ tri), ne dokaz, da se je kaj zgodilo prav tisti mesec, in ne povedo, zakaj.

**Viri podatkov:** Hacker News, mesečne niti »Who is hiring?«, kjer podjetja objavljajo prosta delovna mesta: `data/raw/hn_whoishiring_posts.csv`. Graf bere obdelane datoteke `data/processed/hn_flags_monthly.csv` (izdela jo `python -m analysis.hn_text flags`), `data/processed/hn_change_points.csv` (izdela jo `python -m analysis.hn_text flags`).

## 5_zemljevid
**Kaj vidimo?** Vsak krog je eno metro območje v ZDA (mesto z okolico). Velikost kroga pove, koliko ljudi je tam leta 2019 delalo v IT, barva pa, ali se je število do leta 2024 povečalo (modro) ali zmanjšalo (rdeče); bela pomeni skoraj brez spremembe. Sivi križci so območja, kjer je podatek skrit. Z menijem levo zgoraj preklopiš na rast števila IT podjetij; ko miško premakneš na krog, vidiš ime in številke.

**Zakaj smo to naredili?** Zanimalo nas je, ali se je IT delo po pandemiji preselilo: ali so velika tradicionalna središča izgubljala in manjša, cenejša mesta pridobivala.

**Kaj to pomeni?** Med 259 metro območji z uporabnim podatkom se je IT zaposlenost povečala v 62 % območij; pri tipičnem območju (mediana) je zrasla za 12,7 %. Med 25 največjimi je najbolj zrasel Dallas (+48 %), najslabše se je odrezal Detroit (−22 %). Število IT podjetij je pri tipičnem območju zraslo za 45 % (podatek imamo za 367 območij, ker se število podjetij ne skriva). Za 131 območij je podatek o zaposlenosti skrit ali nepopoln, med njimi Chicago, Atlanta, Minneapolis, Kansas City, Indianapolis.

**Česa ne vemo?** IT tukaj pomeni samo podjetja za svetovanje in programiranje po naročilu (NAICS 5415); založniki programske opreme in velika tehnološka podjetja niso všteti. Kjer je podatek skrit, to ni nič: urad ga ne objavi, da ne bi razkril posameznega podjetja. Primerjamo le dve leti, zato zemljevid ne pokaže, kaj se je dogajalo vmes. Rast pri majhnih območjih je lahko velika že zaradi enega podjetja. Zemljevid kaže, kje se je kaj spremenilo, ne pa zakaj.

**Viri podatkov:** ameriški statistični urad za delo (BLS), popis zaposlenih in podjetij QCEW: `data/raw/bls_qcew_areas_it_industries.csv`; ameriški urad za popis prebivalstva (Census), lega mestnih območij (Gazetteer): `data/raw/census_gazetteer_cbsa.csv`; ameriški urad za popis prebivalstva (Census), raziskava ACS: `data/raw/census_acs5_metro.csv`. Graf bere obdelano datoteko `data/processed/metro_map_data.csv` (izdela jo `python build_metro_panel.py, nato python -m analysis.geo mapdata`).

## 5_regije
**Kaj vidimo?** Štirje grafi, po eden za vsako veliko regijo ZDA. Vsaka pika je eno metro območje, njena višina pa rast IT zaposlenosti med 2019 in 2024. Škatla zajame srednjo polovico območij, črta v njej in napis pa mediano (tipično območje). Ko miško premakneš na piko, vidiš ime.

**Zakaj smo to naredili?** Zemljevid kaže posamezna mesta, tukaj pa preverimo, ali je celoten jug ali zahod rasel hitreje kot severovzhod in srednji zahod.

**Kaj to pomeni?** Mediana rasti po regijah: severovzhod −5,3 % (45 območij); srednji zahod −0,4 % (55 območij); jug +33,8 % (87 območij); zahod +18,5 % (76 območij). Najvišja je na jugu, najnižja na severovzhodu; razlika med njima je 39,1 odstotne točke.

**Česa ne vemo?** IT tukaj pomeni samo podjetja za svetovanje in programiranje po naročilu (NAICS 5415); založniki programske opreme in velika tehnološka podjetja niso všteti. Kjer je podatek skrit, to ni nič: urad ga ne objavi, da ne bi razkril posameznega podjetja. Regijo določimo po prvi zvezni državi v imenu območja, kar pri območjih čez mejo držav ni povsem natančno. Vsako območje šteje enako, ne glede na velikost.

**Viri podatkov:** ameriški statistični urad za delo (BLS), popis zaposlenih in podjetij QCEW: `data/raw/bls_qcew_areas_it_industries.csv`; ameriški urad za popis prebivalstva (Census), lega mestnih območij (Gazetteer): `data/raw/census_gazetteer_cbsa.csv`; ameriški urad za popis prebivalstva (Census), raziskava ACS: `data/raw/census_acs5_metro.csv`. Graf bere obdelano datoteko `data/processed/metro_map_data.csv` (izdela jo `python build_metro_panel.py, nato python -m analysis.geo mapdata`).

## povzetek

**Kaj smo se naučili**

- **Kdaj:** napovedi odpuščanj so se močno povečale spomladi 2022. Pred prvim zvišanjem obrestne mere jih je bilo povprečno 1,0 na teden, po njem 15,4. Ob izidu ChatGPT se je število skoraj nespremenjeno (21,3 pred, 21,6 po).
- **Koliko ljudi:** napovedanih je bilo skupaj 662.971 odpuščenih (število je znano pri 63 % napovedi, zato je prava številka večja). Deset največjih napovedi je 22 % vseh, največ ljudi pa je bilo napovedanih v četrtletju 2023Q1 (124.185). Sredina deleža zaposlenih na napoved je 15 %.
- **Zakaj:** število napovedi sledi obrestnim meram in borzi, števila odpuščenih ljudi in uradne statistike pa isti vzorec ne ujame. Seznam torej bolj kaže, kdaj so podjetja objavljala odpuščanja, kot koliko ljudi je izgubilo delo.
- **Katera podjetja (rast):** podjetja, ki so v letih 2019 do 2021 najhitreje rasla, so pozneje pogosteje napovedala odpuščanja (23 % proti 5 % pri najpočasnejših), vendar ne zato, ker bi jim stroški rasli hitreje od prihodkov.
- **Katera podjetja (velikost):** največ pove velikost podjetja. Samo z njo dosežemo 0,28 (naključje 0,05), model z računovodskimi kazalniki 0,22, brez velikosti pa 0,08.
- **Kaj iščejo delodajalci:** delež objav na Hacker Newsu, ki omenjajo delo na daljavo, je bil leta 2019 32 %, na vrhuncu (12-mesečno povprečje do 8/2022) 84 %, v zadnjih 12 mesecih pa 54 %; delež objav z umetno inteligenco je z 10 % v prvih 12 mesecih narasel na 57 % v zadnjih 12 mesecih. To je vzorec iz kotička trga s prevlado zagonskih podjetij, ne slika vseh delodajalcev.
- **Kje:** med 259 ameriškimi metro območji z uporabnim podatkom se je IT zaposlenost (svetovanje in programiranje po naročilu) med letoma 2019 in 2024 povečala v 62 % območij; pri tipičnem območju (mediana) je zrasla za 12,7 %. Za 131 območij je podatek skrit ali nepopoln, kar ni enako nič.
- **Borza:** ob objavi odpuščanj se cena delnice v povprečju znižala za 0,6 % (negotovost od -1,3 do 0,1 %), kar ni jasno več kot naključje.

**Česa ne vemo**

- Seznam odpuščanj beleži napovedi predvsem znanih podjetij, ne vseh odpuščanj; tudi uradna statistika kaže manj dramatično sliko kot seznam.
- Vse povezave so povezave v času, ne dokaz vzroka: imamo en cikel obrestnih mer in nekaj sto podjetij.
- Nimamo števila zaposlenih in ne vemo, ali je bil razlog za odpuščanja umetna inteligenca.
- Podjetja, ki so kasneje izginila z borze, v podatkih o cenah manjkajo.

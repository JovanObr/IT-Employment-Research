# Vzorec sloga

Ta stran pokaže vse gradnike predstavitve. Je za avtorje (Jovan, Petar), ne za občinstvo. Pravila so v `web/CONTRACT.md`.

---

## Velika številka

{{stevilka: 178.725 | ljudi so podjetja v ZDA napovedala odpustiti leta 2023 (izmišljen primer)}}

Ena številka na zaslon, ko je številka sama sporočilo. Številka mora biti tudi v grafu ali besedilu z virom.

---

## Glavni poudarek

{{poudarek: Val odpuščanj se je začel **po** zvišanju [[obrestna mera|obrestne mere]], ne ob izidu ChatGPT.}}

En poudarek na poglavje, praviloma na zadnjem zaslonu. Besede s pikčasto črto pokažejo razlago, ko greš nanje z miško.

{{govor: Tako je videti opomba za govorca. Prikaže se s tipko N.}}

---

## Črtni graf: naslov je sklep, oznake na koncu črt, puščica na bistvo

{{figure: vzorec_crta}}

---

## Stolpci: ena barva za sporočilo, siva za ostalo

{{figure: vzorec_stolpci}}

---

## Barve in njihov pomen

- **Modra** (`ROLE["main"]`): naši podatki, tisto, o čemer govori zaslon.
- **Oranžna** (`ROLE["contrast"]`): ena stvar, s katero primerjamo. Modra in oranžna sta ločljivi tudi za barvno slepe.
- **Rdeča** (`ROLE["loss"]`): odpuščanja, padci. Nikoli ne sme biti rdeča proti zeleni edina razlika.
- **Siva** (`ROLE["context"]`, `ROLE["muted"]`): vse ostalo, ozadje, primerjave.

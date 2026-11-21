---
title: Se je res zgodilo?
question: Napovedi niso prazne besede in niso naključne
minutes: 2
owner: A
---
## Napoved se pokaže v številu zaposlenih

Napoved še ni odpuščanje. Zato smo preverili letna poročila: podjetja, ki so v letih 2024 in 2025 napovedala odpuščanja, so imela konec leta v [[mediana|sredini]] **4 % manj** zaposlenih. Ostala so jih imela **1 % več**.

{{figure: 4w_zaposleni}}

{{govor: To je naša hipoteza C2, ki smo jo zapisali vnaprej, preden smo prenesli podatke za 2024 in 2025. Prvič smo to opazili na letih 2022 in 2023, zato smo jo preverili na novih letih, ki je niso navdihnila. Razlika je potrjena tudi po popravku za več testov: p je 0,004.}}

---

## Napovedi so načrtovane

Podjetja odpuščanja pogosto napovedo skupaj s [[četrtletno poročilo|četrtletnim poročilom]] o poslovanju. Ob poročilih jih je bilo **219**, po naključju bi jih pričakovali **79**.

{{figure: 4w_porocila}}

{{govor: To je hipoteza E. Za vsako napoved smo pogledali, ali je bila največ tri delovne dni pred ali po poročilu istega podjetja. Nato smo vsako napoved deset tisočkrat prestavili na naključen delovni dan istega leta in prešteli, koliko bi jih padlo ob poročila. Nikoli ni bilo blizu 219. Razlaga: odpuščanje je poslovna odločitev, ki jo uprava sporoči skupaj z rezultati, ne panična reakcija.}}

---

## In borza?

{{stevilka: −0,6 % | povprečna sprememba cene delnice v dneh ob objavi odpuščanj (glede na celotno borzo)}}

Razlika je v mejah naključja (od −1,3 % do +0,1 %). Borza odpuščanj v povprečju ni ne nagradila ne kaznovala.

{{govor: To je [[nenavadni donos]]: sprememba cene delnice, ki je ne pojasni gibanje celotne borze. Povprečje je rahlo negativno, a interval zaupanja vključuje nič. Tudi hipoteza D, da borza ponovljene napovedi kaznuje bolj kot prve, ni potrjena.}}

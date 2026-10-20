# Video scenārijs (apmēram 2,5 minūtes)

Pirms ierakstīšanas: **Iestatījumi → Atjaunot demonstrācijas datus**, pārlūka logs vismaz 1280 px plats.

| Laiks | Ekrānā | Ko teikt |
|---|---|---|
| 0:00–0:15 | Uzdevumu saraksts | „Šis ir mūsu sistēmas prototips. Tas darbojas kā spraudnis Jira vidē un palīdz vadītājam izvēlēties uzdevumam darbinieku. Augšā ir seši nepiešķirti uzdevumi.“ |
| 0:15–0:35 | **Kvalifikāciju katalogs** → „+ Jauna kvalifikācija“ → „Kubernetes“, kategorija „Infrastruktūra“ → Saglabāt | „Pirmā sadaļa ir kvalifikāciju katalogs. Tas glabājas datubāzē, un pēc katras izmaiņas tā kopija tiek atjaunota Forge Storage.“ |
| 0:35–0:55 | **Darbinieki** → Mārtiņš → „Kvalifikācijas“ → Kubernetes, līmenis 4 → Piešķirt. Vēlreiz Kubernetes → paziņojums „Darbiniekam šāda kvalifikācija jau ir“ | „Darbiniekam piešķiram kvalifikāciju un līmeni. Ja mēģinām piešķirt to pašu vēlreiz, sistēma to neļauj. Tā strādā lēmumu tabula 5.1.2.“ |
| 0:55–1:30 | **Uzdevumi → DEV-21**. Parādīt prasības (Python obligāta ≥3, pytest un Docker vēlamas) → „Meklēt kandidātus“ | „Otrā sadaļa ir ieteikums. Sistēma nolasa uzdevumu un komandu no Jira, ar vienu JQL vaicājumu iegūst noslodzi un nosūta datus aprēķinu servisam. Anna ir pirmajā vietā, un pamatojums rāda, kas to noteica. Robertam ir labas kvalifikācijas, taču viņš ir pārslogots, tāpēc saņem sodu. Edgars ir atvaļinājumā, tāpēc ir izslēgts.“ |
| 1:30–1:50 | „Izvēlēties citu“ → Līga → iemesls „Līgai jāapgūst servera daļa“ → Piešķirt | „Gala lēmums paliek vadītāja ziņā. Ja izvēlas citu darbinieku, jānorāda iemesls. Izpildītājs tiek iestatīts Jira, un lēmums tiek saglabāts vēsturē.“ |
| 1:50–2:10 | Uzdevumu saraksts → „Sadalīt visus nepiešķirtos“ → Apstiprināt atzīmētos | „Vairākus uzdevumus var sadalīt vienlaikus. Ungāru algoritms atrod sadali ar lielāko kopējo vērtējumu. Uzdevumam DEV-25 neviens neatbilst obligātajām prasībām, tāpēc sistēma to nepiešķir.“ |
| 2:10–2:25 | **Lēmumu vēsture** (Lēmumi, pēc tam Audita žurnāls) | „Trešā sadaļa ir lēmumu vēsture. Te redzams ieteiktais darbinieks, gala izvēle, vērtējumi un iemesls, kā arī visas izmaiņas audita žurnālā.“ |
| 2:25–2:40 | **Iestatījumi** → ieslēgt „Simulēt aprēķinu servisa nepieejamību“ → DEV-26: pievienot „Dokumentācija“ (obligāta) → Meklēt → manuālā izvēle | „Ja aprēķinu serviss nav pieejams, vadītājs joprojām var piešķirt uzdevumu manuāli. Tā tiek nodrošināta pieejamība.“ |
| 2:40–2:50 | Terminālī `pytest -q` (49 passed) | „Sadales loģikai ir 49 automātiskie testi, kurus palaiž CI konveijerā.“ |

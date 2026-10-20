# Dinamiska darba uzdevumu sadales sistēma: prototips

Prototips palīdz komandas vadītājam izvēlēties uzdevumam piemērotāko darbinieku. Sistēma ņem vērā kvalifikāciju atbilstību, pašreizējo noslodzi, citus augstas prioritātes darbus un tuvojošos termiņus. Gala lēmumu pieņem vadītājs: viņš apstiprina ieteikumu vai izvēlas citu darbinieku.

Autori: Kristaps Duļbinskis, Iļja Terentjevs, Aleksandrs Varakuta, Beatrise Sauka. RTU, 2026.

## Palaišana

Nepieciešams Python 3.12 vai jaunāks.

```bash
python -m venv .venv
.venv\Scripts\activate            # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:create_app --factory --port 8000
```

Pēc palaišanas atveriet http://localhost:8000. API dokumentācija (FastAPI, automātiski ģenerēta) ir pieejama http://localhost:8000/docs.

Pirmajā palaišanā sistēma pati izveido demonstrācijas datus: projektu DEV ar 9 Jira lietotājiem, 8 darbinieku profiliem, 11 kvalifikācijām un 6 nepiešķirtiem uzdevumiem. Datus var atjaunot sadaļā **Iestatījumi → Atjaunot demonstrācijas datus** vai ar komandu `python -m app.seed`.

Testi:

```bash
pytest -q
```

Ar PostgreSQL (kā arhitektūras dokumentā, nepieciešams Docker):

```bash
docker compose up --build
```

## Kas prototipā strādā

Prasība bija 2–3 strādājošas sadaļas, kurās dati tiek nolasīti, apstrādāti un saglabāti. Prototipā tādas ir piecas, un visas ir saistītas ar galveno funkcionalitāti.

| # | Sadaļa | Nolasa | Apstrādā | Saglabā |
|---|---|---|---|---|
| 1 | **Uzdevuma prasības un kandidātu meklēšana** (uzdevuma skats, panelis „Uzdevumu sadale“) | Uzdevums un lietotāji no Jira REST API, noslodze ar vienu JQL vaicājumu, darbinieku profili no datubāzes, svari no Forge Storage | Validācija (5.1.1), obligāto prasību filtrs (5.1.3), svērtā vērtēšana, Ungāru algoritms, pamatojums | `Task_Requirements`, `Workload_Snapshots`, prioritāte Jira |
| 2 | **Ieteikuma apstiprināšana / cita darbinieka izvēle** | Algoritma rezultāts | Lēmumu tabula 5.1.5; cita darbinieka izvēlei jānorāda iemesls | Izpildītājs Jira, `Assignment_Decisions`, `Audit_Log` |
| 3 | **Kvalifikāciju katalogs un darbinieku kvalifikācijas** | `Skills`, `Employees`, `Employee_Skills` | Lēmumu tabula 5.1.2, dublikātu un izmantotu kvalifikāciju pārbaude | Datubāze un versēta kataloga kopija Forge Storage |
| 4 | **Sadalīt visus nepiešķirtos** (uzdevumu sarakstā) | Visi nepiešķirtie uzdevumi ar prasībām | Ungāru algoritms vairākiem uzdevumiem vienlaikus, augstākas prioritātes uzdevumiem lielāks svars | Izpildītāji Jira, lēmumi vēsturē |
| 5 | **Iestatījumi** | `weights.config`, `settings.project` | Svaru validācija un normalizēšana | Forge Storage, `Audit_Log` |

Lasīšanas skats **Lēmumu vēsture** rāda `Assignment_Decisions` un `Audit_Log` ar reāliem skaitļiem: cik lēmumu pieņemts, cik procentos ieteikums apstiprināts un cik uzdevumu piešķirts manuāli.

**Tikai vizuāla** ir sadaļa **Komandas pārskats**: tās skaitļi ir iekodēti, un tā rāda, kā izskatītos komandas noslodzes un ieteikumu statistikas skats.

## Atbilstība dokumentācijai

### Funkcionālās prasības (specifikācijas 10.1. nodaļa)

| Prasība | Kur prototipā |
|---|---|
| 1. Sadale Jira vidē | Panelis „Uzdevumu sadale“ Jira uzdevuma skatā |
| 2. Darbinieku kvalifikāciju uzturēšana | Darbinieki un kvalifikācijas |
| 3. Uzdevuma kvalifikāciju uzturēšana | Uzdevuma prasību panelis |
| 4. Jira uzdevumi, darbinieki, noslodze | `system.js`, `fetchWorkload`: viens JQL vaicājums visai komandai |
| 5. Obligāto prasību pārbaude | `app/algorithm/filtering.py` |
| 6. Vērtēšana pēc kvalifikācijām, darbiem, prioritātēm | `app/algorithm/scoring.py` |
| 7. Ieteikums vai kandidātu saraksts | Ieteikuma kartīte un kandidātu tabula ar pamatojumu |
| 8. Ieteikuma apstiprināšana | Poga „Apstiprināt“ |
| 9. Cita darbinieka izvēle | Poga „Izvēlēties citu“, iemesls tiek saglabāts |
| 10. Piešķiršana Jira uzdevumam | `PUT /rest/api/3/issue/{key}/assignee` |
| 11. Kataloga un svaru glabāšana | Forge Storage: `skills.catalog`, `weights.config` |
| 12. Profili, kvalifikācijas, lēmumu vēsture | Datubāzes tabulas (arhitektūras 5. tabula) |
| 13. Nav atbilstoša kandidāta | Statuss `no_candidates`, paziņojums un manuāla piešķiršana |

### Arhitektūra

- **Moduļi** (2.1. nodaļa). Vadītāja modulis ir `static/js/views/`. Sistēmas modulis ir `static/js/system.js`, kas, tāpat kā Forge pusē, koordinē plūsmu. Algoritma modulis ir `app/algorithm/` ar trim apakšmoduļiem: filtrēšana, vērtēšana un optimizācija.
- **ADR-001.** Algoritms saņem visus datus pieprasījumā (`POST /api/v1/algorithm/recommend`) un pats nepiekļūst ne Jira, ne datubāzei. Tāpēc to var testēt izolēti (`tests/test_algorithm.py`).
- **ADR-002.** Uzdevumi un noslodze netiek glabāti pastāvīgi. Tos nolasa no Jira katrā pieprasījumā, bet `Workload_Snapshots` saglabā tikai momentuzņēmumu.
- **Lēmumu tabulas** 5.1.1–5.1.5 ir realizētas ar tiem pašiem paziņojumu tekstiem, un katram noteikumam ir savs tests (`tests/test_api.py`).
- **Pieejamība** (6.4. nodaļa). Ja aprēķinu serviss neatbild noildzes laikā, vadītājs redz kandidātus bez vērtējuma un var piešķirt uzdevumu manuāli. To var pārbaudīt sadaļā Iestatījumi → „Simulēt aprēķinu servisa nepieejamību“. Servisa stāvokli rāda `/api/v1/health` un punkts augšējā joslā.
- **Datu atkarības** (3.3. nodaļa). Darbinieku nedzēš, bet deaktivizē. Kvalifikāciju, kas tiek izmantota, dzēst nevar.

### Atšķirības no dokumentācijas

Prototipā ir pieļaujamas atšķirības, kas parādās programmēšanas laikā. Šīs ir apzinātas:

1. **Forge spraudņa vietā ir tīmekļa saskarne, kas atdarina Jira uzdevuma skatu.** Īstam Forge spraudnim vajadzīga Atlassian izstrādes vietne. Saskarnes un sistēmas moduļa loģika ir tāda pati, un JavaScript kodu var pārnest uz Forge Custom UI.
2. **Jira Cloud REST API vietā ir lokāls aizstājējs** (`app/jira_stub.py`) ar tiem pašiem ceļiem un datu formātu (`/rest/api/3/issue`, `/search/jql`, `/user/assignable/search`, `/issue/{key}/assignee`).
3. **Forge Storage vietā ir JSON fails** ar tām pašām atslēgām: `skills.catalog`, `weights.config`, `settings.project`.
4. **Datubāze.** Pēc noklusējuma tiek izmantots SQLite ar to pašu shēmu, lai prototipu varētu palaist bez Docker. PostgreSQL tiek pieslēgts ar `DATABASE_URL` (skat. `docker-compose.yml`).
5. **CI.** Specifikācijā minēts GitHub Actions, bet arhitektūras dokumentā GitLab CI/CD, tāpēc repozitorijā ir abi konfigurācijas faili.
6. **Papildinājumi.** Pievienots režīms „Sadalīt visus nepiešķirtos“ (Ungāru algoritms vairākiem uzdevumiem), un, izvēloties citu darbinieku, obligāti jānorāda iemesls (sk. riskus: „vadītāji neuzticas ieteikumam“).

## Vērtēšanas modelis

Katram kandidātam, kas izturējis obligāto prasību filtru, tiek aprēķināti četri faktori robežās no 0 līdz 1:

| Faktors | Aprēķins | Noklusējuma svars |
|---|---|---|
| Kvalifikāciju atbilstība | Līmeņu vidējais pret maksimālo (5); obligātajām prasībām svars 1, vēlamajām 0,5 | 50 % |
| Noslodze | 1 − prioritātes punkti / robeža (Highest = 5 … Lowest = 1) | 25 % |
| Citi augstas prioritātes darbi | 1 − (High/Highest atvērtie uzdevumi / 3) | 15 % |
| Termiņi | 1 − (uzdevumi ar termiņu 7 dienu laikā / 3) | 10 % |

Vērtējums = Σ(svars × faktors) × 100. Ja noslodze pārsniedz robežu, tiek atņemti 20 punkti (lēmumu tabula 5.1.3, D3). Režīmā „Sadalīt visus“ izmaksu matrica ir `−prioritāte × vērtējums`, un `scipy.optimize.linear_sum_assignment` atrod piesaisti ar lielāko kopējo vērtējumu.

## Struktūra

```
app/
  algorithm/        algoritma modulis: contract, filtering, scoring, optimization
  api.py            datu piekļuves API, algoritma galapunkts, Forge Storage
  jira_stub.py      Jira REST API v3 aizstājējs
  models.py         7 datubāzes tabulas (arhitektūras 5. tabula)
  seed.py           demonstrācijas dati
  main.py           lietotnes izveide
static/
  js/system.js      sistēmas modulis: plūsmas koordinācija
  js/views/         vadītāja modulis: skati
tests/              pytest: algoritms izolēti, API pēc lēmumu tabulām
```

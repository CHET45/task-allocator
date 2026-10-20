"""Demo data: a Jira project with a small team, the skill catalog and a few new tasks.

Run `python -m app.seed` to reset everything back to this state.
"""
import json
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy.orm import Session

from .models import Employee, EmployeeSkill, Skill, TaskRequirement

SKILLS = [
    ("Python", "Programmēšana", "Servera daļa, algoritmi, FastAPI"),
    ("JavaScript/TypeScript", "Programmēšana", "Forge spraudņa un saskarnes kods"),
    ("React", "Saskarne", "Komponentes un UI Kit"),
    ("SQL / PostgreSQL", "Dati", "Shēmas, vaicājumi, migrācijas"),
    ("Docker", "Infrastruktūra", "Konteineri un izstrādes vide"),
    ("CI/CD", "Infrastruktūra", "Konveijeri, automātiskās pārbaudes"),
    ("pytest testēšana", "Kvalitāte", "Automātiskie testi Python kodam"),
    ("UI/UX dizains", "Saskarne", "Prototipi, lietojamība"),
    ("Dokumentācija", "Analīze", "Prasības, rokasgrāmatas"),
    ("Jira administrēšana", "Analīze", "Projekti, darbplūsmas, JQL"),
    ("Forge spraudņi", "Programmēšana", "Atlassian Forge manifests un izpildvide"),
]

# account id, name, team, status, {skill: level}; the last user exists only in Jira.
PEOPLE = [
    ("u01", "Anna Bērziņa", "Backend", "active",
     {"Python": 5, "SQL / PostgreSQL": 4, "Docker": 3, "pytest testēšana": 4}),
    ("u02", "Jānis Kalniņš", "Frontend", "active",
     {"JavaScript/TypeScript": 5, "React": 5, "UI/UX dizains": 3}),
    ("u03", "Līga Ozola", "Fullstack", "active",
     {"Python": 3, "JavaScript/TypeScript": 4, "React": 3, "SQL / PostgreSQL": 3}),
    ("u04", "Mārtiņš Liepiņš", "DevOps", "active",
     {"Docker": 5, "CI/CD": 5, "Python": 3, "SQL / PostgreSQL": 2}),
    ("u05", "Elīna Krūmiņa", "Kvalitāte", "active",
     {"pytest testēšana": 5, "Python": 3, "Dokumentācija": 4, "Jira administrēšana": 3}),
    ("u06", "Roberts Zariņš", "Backend", "active",
     {"Python": 4, "SQL / PostgreSQL": 5, "Docker": 2}),
    ("u07", "Kristīne Vītola", "Analīze", "active",
     {"Dokumentācija": 5, "Jira administrēšana": 4, "UI/UX dizains": 4, "SQL / PostgreSQL": 2}),
    ("u08", "Edgars Pētersons", "Backend", "on_leave",
     {"Python": 4, "JavaScript/TypeScript": 3}),
]
JIRA_ONLY = [("u09", "Paula Grīnberga")]

# key number, summary, priority, assignee, status, due offset (days) or None
EXISTING = [
    (1, "Projekta repozitorija izveide", "Medium", "u04", "Pabeigts", None),
    (2, "Prasību specifikācijas melnraksts", "High", "u07", "Pabeigts", None),
    (3, "Darbinieku profilu tabula", "Medium", "u01", "Procesā", None),
    (4, "Noslodzes JQL vaicājums", "High", "u01", "Procesā", 3),
    (5, "Iestatījumu skata makets", "High", "u02", "Procesā", None),
    (6, "Kandidātu kartītes stils", "Medium", "u02", "Jādara", None),
    (7, "Ikonas un krāsu tēma", "Low", "u02", "Jādara", None),
    (8, "Kvalifikāciju kataloga API", "Low", "u03", "Procesā", None),
    (9, "Docker Compose izstrādes videi", "Medium", "u04", "Procesā", None),
    (10, "Testa vides konfigurācija", "Medium", "u04", "Jādara", 10),
    (11, "Algoritma robežgadījumu testi", "High", "u05", "Procesā", 2),
    (12, "Regresijas testu plāns", "Medium", "u05", "Jādara", None),
    (13, "Datubāzes indeksu optimizācija", "Highest", "u06", "Procesā", 1),
    (14, "Audita žurnāla shēma", "High", "u06", "Procesā", None),
    (15, "Lēmumu vēstures eksports", "High", "u06", "Jādara", 5),
    (16, "Datu dublēšanas skripts", "Medium", "u06", "Jādara", None),
    (17, "Vaicājumu veiktspējas mērījumi", "Medium", "u06", "Jādara", None),
    (18, "Lietotāju intervijas kopsavilkums", "Medium", "u07", "Procesā", None),
    (19, "Ungāru algoritma izpēte", "Medium", "u01", "Pabeigts", None),
    (20, "Arhitektūras dokumenta pārskatīšana", "Low", "u05", "Pabeigts", None),
]

# key number, summary, description, priority, [(skill, required, min_level)]
NEW_TASKS = [
    (21, "Sadales API galapunkts /recommend",
     "FastAPI galapunkts, kas saņem uzdevumu un kandidātu datus un atgriež ieteikumu.", "High",
     [("Python", True, 3), ("pytest testēšana", False, 1), ("Docker", False, 1)]),
    (22, "Kandidātu saraksta komponente",
     "Saskarnes komponente kandidātu sarakstam ar vērtējumu un pamatojumu.", "Medium",
     [("React", True, 3), ("JavaScript/TypeScript", True, 3), ("UI/UX dizains", False, 1)]),
    (23, "PostgreSQL migrācijas lēmumu vēsturei",
     "Tabulas Assignment_Decisions un Audit_Log migrācijas skripti.", "High",
     [("SQL / PostgreSQL", True, 4), ("Python", False, 1)]),
    (24, "CI konveijers ar pytest",
     "Konveijers, kas pēc katras izmaiņas palaiž algoritma testus.", "Medium",
     [("CI/CD", True, 3), ("pytest testēšana", False, 1)]),
    (25, "Forge manifests un UI Kit panelis",
     "Spraudņa manifests un paneļa izvietojums Jira uzdevuma skatā.", "High",
     [("Forge spraudņi", True, 2)]),
    (26, "Lietotāja rokasgrāmata",
     "Īsa instrukcija vadītājam par sadales funkcionalitāti.", "Low", []),
]


def build_jira(today: date | None = None) -> dict:
    today = today or date.today()
    users = [
        {"accountId": acc, "displayName": name, "active": True, "projects": ["DEV"]}
        for acc, name, *_ in PEOPLE
    ] + [{"accountId": acc, "displayName": name, "active": True, "projects": ["DEV"]} for acc, name in JIRA_ONLY]

    issues = []
    for n, summary, prio, assignee, status, due in EXISTING:
        issues.append({
            "id": 10000 + n, "key": f"DEV-{n}", "project": "DEV", "summary": summary, "description": "",
            "issuetype": "Uzdevums", "priority": prio, "status": status, "assignee": assignee,
            "duedate": (today + timedelta(days=due)).isoformat() if due is not None else None,
            "created": (today - timedelta(days=30 - n)).isoformat(),
        })
    for n, summary, desc, prio, _ in NEW_TASKS:
        issues.append({
            "id": 10000 + n, "key": f"DEV-{n}", "project": "DEV", "summary": summary, "description": desc,
            "issuetype": "Uzdevums", "priority": prio, "status": "Jādara", "assignee": None,
            "duedate": (today + timedelta(days=14)).isoformat(), "created": today.isoformat(),
        })
    return {
        "projects": [{"key": "DEV", "name": "Uzdevumu sadales sistēma"}],
        "users": users,
        "issues": issues,
        "next_id": max(n for n, *_ in NEW_TASKS),
    }


def seed_database(db: Session) -> None:
    skills = {name: Skill(name=name, category=cat, description=desc) for name, cat, desc in SKILLS}
    db.add_all(skills.values())
    db.flush()
    for acc, name, team, status, levels in PEOPLE:
        emp = Employee(jira_account_id=acc, display_name=name, team=team, status=status)
        emp.skills = [EmployeeSkill(skill=skills[s], level=lvl) for s, lvl in levels.items()]
        db.add(emp)
    for n, *_, reqs in NEW_TASKS:
        for skill, required, min_level in reqs:
            db.add(TaskRequirement(issue_key=f"DEV-{n}", skill=skills[skill], required=required,
                                   min_level=min_level))
    db.commit()


def write_jira(path: Path) -> None:
    path.write_text(json.dumps(build_jira(), ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    from .main import reset_demo_data, settings_from_env

    reset_demo_data(*settings_from_env())
    print("Demo dati atjaunoti.")

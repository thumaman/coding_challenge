"""Demo data for development and the final demo (owner: Joseph).

    uv run python manage.py seed_demo          # adds data + a 'recruiter' login (password: recruiter)
    uv run python manage.py seed_demo --flush  # wipes candidates/clients first
"""

import random
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from candidates.models import Candidate
from clients.models import Client, Vacancy
from pricing.travel import offline_distance_km

CLIENTS = [
    ("Rabobank", "Finance", "Utrecht"),
    ("ASML", "High-tech", "Veldhoven"),
    ("Gemeente Amsterdam", "Government", "Amsterdam"),
    ("Coolblue", "E-commerce", "Rotterdam"),
    ("Philips", "Health tech", "Eindhoven"),
]

VACANCIES = [
    ("Senior Data Engineer", 120, "python, sql, spark, data"),
    ("Product Owner", 105, "scrum, product, agile"),
    ("DevOps Engineer", 115, "kubernetes, cloud, devops, ci"),
    ("Business Analyst", 95, "analysis, sql, requirements"),
    ("Java Developer", 100, "java, spring, backend"),
    ("Project Manager", 110, "prince2, project, stakeholder"),
    ("UX Designer", 90, "figma, ux, design, research"),
    ("Financial Controller", 98, "finance, control, reporting"),
    ("Frontend Developer", 95, "javascript, react, frontend"),
    ("Scrum Master", 100, "scrum, agile, coaching"),
    ("Security Officer", 125, "security, iso27001, risk"),
    ("Data Analyst", 85, "sql, power bi, analysis, data"),
]

FIRST = ["Sanne", "Daan", "Lotte", "Bram", "Emma", "Thijs", "Fleur", "Ruben", "Noor", "Jesse", "Iris", "Lucas",
         "Anouk", "Sem", "Femke", "Milan", "Julia", "Niels", "Eva", "Stijn"]
LAST = ["de Vries", "Jansen", "Bakker", "Visser", "Smit", "Meijer", "de Boer", "Mulder", "de Groot", "Bos",
        "Vos", "Peters", "Hendriks", "van Dijk", "Dekker"]
CITIES = ["Amsterdam", "Utrecht", "Rotterdam", "Eindhoven", "Den Haag", "Amersfoort", "Haarlem", "Leiden"]
NOTES = ["Values flexibility and remote work.", "Salary is the main driver.", "Prefers a 4-day work week.",
         "Wants extra training budget.", "Prefers public transport.", ""]


class Command(BaseCommand):
    help = "Create demo clients, vacancies and candidates"

    def add_arguments(self, parser):
        parser.add_argument("--flush", action="store_true", help="Delete existing candidates and clients first")
        parser.add_argument("--candidates", type=int, default=30)

    def handle(self, *args, flush=False, candidates=30, **options):
        rng = random.Random(42)
        if flush:
            Candidate.objects.all().delete()
            Client.objects.all().delete()

        if not User.objects.filter(username="recruiter").exists():
            User.objects.create_superuser("recruiter", "recruiter@example.com", "recruiter")
            self.stdout.write("Created login recruiter / recruiter")

        clients = [Client.objects.create(name=n, industry=i, city=c, contact_name="HR") for n, i, c in CLIENTS]
        vacancies = []
        for idx, (title, rate, skills) in enumerate(VACANCIES):
            client = clients[idx % len(clients)]
            max_salary = Decimal(rate - 10) / 2 * 40 * 13 / 3  # what the max rate allows (rate -> salary)
            vacancies.append(Vacancy.objects.create(
                client=client, title=title, city=client.city, max_rate_per_hour=rate,
                hours_per_week=rng.choice([32, 36, 40, 40]), remote_days_allowed=rng.choice([0, 1, 2, 2, 3]),
                client_pays_travel=idx % 4 == 0,
                min_salary=round(max_salary * Decimal("0.6"), -2), max_salary=round(max_salary, -2), skills=skills,
            ))

        for _ in range(candidates):
            vacancy = rng.choice(vacancies + [None])
            city = rng.choice(CITIES)
            Candidate.objects.create(
                first_name=rng.choice(FIRST), last_name=rng.choice(LAST),
                email=f"candidate{rng.randint(100, 999)}@example.com", phone=f"06{rng.randint(10000000, 99999999)}",
                city=city,
                desired_role=vacancy.title if vacancy and rng.random() < 0.8 else rng.choice(VACANCIES)[0],
                status=rng.choice(Candidate.Status.values[:3]),
                expected_salary_month=Decimal(rng.randrange(3200, 9500, 100)),
                hours_per_week=rng.choice([32, 36, 40, 40, 40]),
                # Offline estimate so seeding needs no network; the form recalculates via the routing API
                travel_distance_km=offline_distance_km(city, vacancy.location) if vacancy else None,
                transport_type=rng.choice(["car", "car", "ov"]),
                client_pays_travel=bool(vacancy and vacancy.client_pays_travel),
                remote_days_per_week=rng.choice([0, 1, 2, 2, 3]),
                vacancy=vacancy, notes=rng.choice(NOTES),
            )

        self.stdout.write(self.style.SUCCESS(
            f"Seeded {len(clients)} clients, {len(vacancies)} vacancies, {candidates} candidates."
        ))

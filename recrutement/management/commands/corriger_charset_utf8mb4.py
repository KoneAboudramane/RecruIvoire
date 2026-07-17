from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = (
        "Force le charset utf8mb4 sur la base et sur toutes ses tables (MySQL/MariaDB). "
        "Corrige le cas ou l'hebergeur a cree la base en utf8/utf8mb3 (incapable de "
        "stocker les emoji utilises dans certains libelles du projet, ex. erreur 1366 "
        "'Incorrect string value' sur pages_elementfooter.label pendant `migrate`). "
        "Idempotent : peut etre relancee sans risque, y compris sur une base deja en "
        "utf8mb4. A lancer avant (ou apres l'echec d') un `migrate`."
    )

    def handle(self, *args, **options):
        if connection.vendor != 'mysql':
            self.stdout.write(self.style.WARNING(
                f"Base non-MySQL ({connection.vendor}) — rien a faire."
            ))
            return

        db_name = connection.settings_dict['NAME']
        with connection.cursor() as cursor:
            cursor.execute(f"ALTER DATABASE `{db_name}` CHARACTER SET utf8mb4")
            self.stdout.write(self.style.SUCCESS(f"Base `{db_name}` -> utf8mb4."))

            cursor.execute("SHOW TABLES")
            tables = [row[0] for row in cursor.fetchall()]
            for table in tables:
                cursor.execute(f"ALTER TABLE `{table}` CONVERT TO CHARACTER SET utf8mb4")
                self.stdout.write(f"  {table} -> utf8mb4")

        self.stdout.write(self.style.SUCCESS(
            f"{len(tables)} table(s) converties. Relancer `migrate` si besoin."
        ))

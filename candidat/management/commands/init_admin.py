from django.core.management.base import BaseCommand
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = "Crée ou réinitialise le compte administrateur avec les identifiants user / user"

    def handle(self, *args, **options):
        if User.objects.filter(username='user').exists():
            admin = User.objects.get(username='user')
            admin.set_password('user')
            admin.is_staff     = True
            admin.is_superuser = True
            admin.save()
            self.stdout.write(self.style.SUCCESS('Admin réinitialisé — identifiants : user / user'))
        else:
            admin = User.objects.create(
                username='user',
                email='admin@recrute.pro',
                is_staff=True,
                is_superuser=True,
            )
            admin.set_password('user')
            admin.save()
            self.stdout.write(self.style.SUCCESS('Admin créé — identifiants : user / user'))

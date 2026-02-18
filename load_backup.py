import os
from django.core.management.base import BaseCommand, CommandError
from django.core.management import call_command

class Command(BaseCommand):
    """
    Comando de gestión para cargar (restaurar) una copia de seguridad desde un archivo JSON.
    Utiliza el comando 'loaddata' de Django.
    """
    help = 'Carga datos desde un archivo de backup JSON. Uso: python manage.py load_backup <ruta_al_archivo.json>'

    def add_arguments(self, parser):
        # Argumento posicional para la ruta del archivo de backup
        parser.add_argument('backup_file', type=str, help='La ruta completa al archivo de backup JSON.')

    def handle(self, *args, **options):
        file_path = options['backup_file']

        # 1. Verificar que el archivo que quieres cargar realmente existe
        if not os.path.exists(file_path):
            raise CommandError(f'El archivo de backup no se encontró en la ruta: "{file_path}"')

        self.stdout.write(self.style.WARNING(f'Iniciando la restauración desde "{file_path}". Esto puede sobreescribir datos existentes en la base de datos.'))

        try:
            # 2. Llamar al comando 'loaddata' de Django, que es la herramienta oficial para esta tarea.
            call_command('loaddata', file_path)
            self.stdout.write(self.style.SUCCESS('¡Copia de seguridad restaurada exitosamente!'))
            self.stdout.write(self.style.NOTICE('Es recomendable que revises los datos en el panel de administración para confirmar que todo está correcto.'))
        except Exception as e:
            raise CommandError(f'Ocurrió un error durante la restauración: {e}')
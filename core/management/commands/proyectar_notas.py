# core/management/commands/proyectar_notas.py
from django.core.management.base import BaseCommand, CommandError
from core.models import Seccion
from core.ml import predict_final_for_seccion

class Command(BaseCommand):
    help = "Proyecta la nota final para todos los estudiantes de una sección."

    def add_arguments(self, parser):
        parser.add_argument("--seccion_id", type=int, help="ID de la sección", required=True)

    def handle(self, *args, **options):
        seccion_id = options["seccion_id"]
        try:
            seccion = Seccion.objects.select_related("curso", "profesor").get(pk=seccion_id)
        except Seccion.DoesNotExist:
            raise CommandError("Sección no encontrada.")

        try:
            out = predict_final_for_seccion(seccion)
        except ValueError as e:
            raise CommandError(str(e))

        self.stdout.write(self.style.SUCCESS(
            f"Modelo entrenado con {out['metrics']['n_train']} filas. R2={out['metrics']['r2']:.3f} RMSE={out['metrics']['rmse']:.3f}"
        ))
        for p in out["predictions"]:
            self.stdout.write(f"{p['codigo']}: pred_nota_final={p['pred_nota_final']}")

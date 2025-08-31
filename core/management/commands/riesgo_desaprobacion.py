# core/management/commands/riesgo_desaprobacion.py
from django.core.management.base import BaseCommand, CommandError
from core.models import Seccion
from core.ml import predict_risk_for_seccion

class Command(BaseCommand):
    help = "Calcula el riesgo de desaprobar para todos los estudiantes de una sección."

    def add_arguments(self, parser):
        parser.add_argument("--seccion_id", type=int, help="ID de la sección", required=True)

    def handle(self, *args, **options):
        seccion_id = options["seccion_id"]
        try:
            seccion = Seccion.objects.select_related("curso", "profesor").get(pk=seccion_id)
        except Seccion.DoesNotExist:
            raise CommandError("Sección no encontrada.")

        try:
            out = predict_risk_for_seccion(seccion)
        except ValueError as e:
            raise CommandError(str(e))

        self.stdout.write(self.style.SUCCESS(
            f"Modelo entrenado con {out['metrics']['n_train']} filas. Accuracy={out['metrics']['accuracy']:.3f}"
        ))
        for p in out["predictions"]:
            self.stdout.write(f"{p['codigo']}: prob={p['prob_desaprobacion']} riesgo={p['riesgo']}")

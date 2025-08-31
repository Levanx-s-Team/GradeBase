# core/views.py
from django.http import HttpResponse
from django.db.models import Q, Avg
from django.utils import timezone
import csv
from openpyxl import Workbook
from django.template.loader import render_to_string

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from xhtml2pdf import pisa

from .models import Estudiante, Curso, Seccion, Nota
from .serializers import (
    EstudianteSerializer, CursoSerializer, SeccionSerializer, NotaSerializer
)
from .permissions import (
    IsStudentReadOwnNotas, IsTeacherOfSectionForWrite, is_in_group
)

# ML helpers
from core.ml import predict_final_for_seccion, predict_risk_for_seccion


# =========================
# ESTUDIANTE
# =========================
class EstudianteViewSet(viewsets.ModelViewSet):
    queryset = Estudiante.objects.all()
    serializer_class = EstudianteSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return super().get_queryset()
        if is_in_group(user, "ESTUDIANTE"):
            return Estudiante.objects.filter(user=user)
        if is_in_group(user, "DOCENTE"):
            secciones_ids = Seccion.objects.filter(profesor=user).values_list("id", flat=True)
            return Estudiante.objects.filter(notas__seccion_id__in=secciones_ids).distinct()
        return Estudiante.objects.none()


# =========================
# CURSO
# =========================
class CursoViewSet(viewsets.ModelViewSet):
    queryset = Curso.objects.all()
    serializer_class = CursoSerializer
    permission_classes = [IsAuthenticated]


# =========================
# SECCION
# =========================
class SeccionViewSet(viewsets.ModelViewSet):
    queryset = Seccion.objects.all()
    serializer_class = SeccionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return super().get_queryset()
        if is_in_group(user, "DOCENTE"):
            return Seccion.objects.filter(profesor=user)
        if is_in_group(user, "ESTUDIANTE"):
            return Seccion.objects.filter(notas__estudiante__user=user).distinct()
        return Seccion.objects.none()


# =========================
# NOTA
# =========================
class NotaViewSet(viewsets.ModelViewSet):
    queryset = Nota.objects.all()
    serializer_class = NotaSerializer
    permission_classes = [IsAuthenticated, IsStudentReadOwnNotas, IsTeacherOfSectionForWrite]
    # Requiere django-filter + DEFAULT_FILTER_BACKENDS en settings
    filterset_fields = ['seccion__curso__codigo', 'seccion__nombre', 'estudiante__codigo']

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return super().get_queryset()
        if is_in_group(user, "DOCENTE"):
            return Nota.objects.filter(seccion__profesor=user)
        if is_in_group(user, "ESTUDIANTE"):
            return Nota.objects.filter(estudiante__user=user)
        return Nota.objects.none()

    # --- creación / edición con controles adicionales ---
    def perform_create(self, serializer):
        user = self.request.user
        if is_in_group(user, "ESTUDIANTE"):
            raise PermissionDenied("Los estudiantes no pueden crear notas.")
        if is_in_group(user, "DOCENTE"):
            # Solo puede crear en sus propias secciones
            seccion_id = self.request.data.get("seccion")
            if not seccion_id:
                raise PermissionDenied("Se requiere 'seccion'.")
            try:
                seccion = Seccion.objects.get(pk=seccion_id)
            except Seccion.DoesNotExist:
                raise PermissionDenied("Sección inválida.")
            if seccion.profesor_id != user.id:
                raise PermissionDenied("No puedes crear notas en secciones de otros docentes.")
        serializer.save()

    def perform_update(self, serializer):
        user = self.request.user
        instance = self.get_object()
        if is_in_group(user, "ESTUDIANTE"):
            raise PermissionDenied("Los estudiantes no pueden editar notas.")
        if is_in_group(user, "DOCENTE") and instance.seccion.profesor_id != user.id:
            raise PermissionDenied("No puedes editar notas de secciones de otros docentes.")
        serializer.save()

    # =========================
    # EXPORTACIONES
    # =========================
    @action(detail=False, methods=['get'], url_path='export/csv')
    def export_csv(self, request):
        qs = self._filtered_queryset_for_export()
        if not qs.exists():
            return HttpResponse("No hay datos para exportar con los filtros dados.", status=400)

        resp = HttpResponse(content_type='text/csv')
        resp['Content-Disposition'] = 'attachment; filename="notas.csv"'
        w = csv.writer(resp)
        w.writerow(['Codigo','Estudiante','Curso','Seccion','Av1','Av2','Av3','Participacion','Proyecto','Final'])
        for n in qs:
            w.writerow([
                n.estudiante.codigo,
                f"{n.estudiante.nombre} {n.estudiante.apellido}",
                n.seccion.curso.codigo,
                n.seccion.nombre,
                n.avance1, n.avance2, n.avance3, n.participacion, n.proyecto_final, n.nota_final
            ])
        return resp

    @action(detail=False, methods=['get'], url_path='export/xlsx')
    def export_xlsx(self, request):
        qs = self._filtered_queryset_for_export()
        if not qs.exists():
            return HttpResponse("No hay datos para exportar con los filtros dados.", status=400)

        wb = Workbook(); ws = wb.active; ws.title = "Notas"
        headers = ['Codigo','Estudiante','Curso','Seccion','Av1','Av2','Av3','Participacion','Proyecto','Final']
        ws.append(headers)
        for n in qs:
            ws.append([
                n.estudiante.codigo,
                f"{n.estudiante.nombre} {n.estudiante.apellido}",
                n.seccion.curso.codigo,
                n.seccion.nombre,
                n.avance1, n.avance2, n.avance3, n.participacion, n.proyecto_final, n.nota_final
            ])
        resp = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        resp['Content-Disposition'] = 'attachment; filename="notas.xlsx"'
        wb.save(resp)
        return resp

    @action(detail=False, methods=['get'], url_path='export/pdf')
    def export_pdf(self, request):
        """
        Exporta un PDF con las notas filtradas por ?curso=, ?seccion=, ?codigo=
        Respeta permisos:
          - Admin: todo
          - Docente: solo sus secciones
          - Estudiante: solo sus notas
        """
        qs = self._filtered_queryset_for_export().order_by(
            'seccion__curso__codigo', 'seccion__nombre', 'estudiante__apellido', 'estudiante__nombre'
        )
        if not qs.exists():
            return HttpResponse("No hay datos para exportar con los filtros dados.", status=400)

        first = qs.first()
        context = {
            "generado_en": timezone.now(),
            "usuario": request.user.get_username(),
            "curso": request.GET.get('curso') or getattr(first.seccion.curso, 'codigo', ''),
            "seccion": request.GET.get('seccion') or getattr(first.seccion, 'nombre', ''),
            "notas": qs,
            "promedio_general": qs.aggregate(avg=Avg('nota_final'))['avg'],
        }

        html = render_to_string("reportes/notas_pdf.html", context)

        response = HttpResponse(content_type='application/pdf')
        filename = f"reporte_notas_{timezone.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        pisa_status = pisa.CreatePDF(src=html, dest=response, encoding='utf-8')
        if pisa_status.err:
            return HttpResponse("Error al generar el PDF.", status=500)
        return response

    # =========================
    # MACHINE LEARNING
    # =========================
    def _resolve_seccion_from_request(self, request):
        """
        Acepta:
          - body: {"seccion_id": 123}
          - o body: {"curso": "CS101", "seccion": "A"}
        """
        seccion_id = request.data.get("seccion_id")
        if seccion_id:
            return Seccion.objects.select_related("curso", "profesor").get(pk=seccion_id)
        curso = request.data.get("curso")
        seccion_nombre = request.data.get("seccion")
        if curso and seccion_nombre:
            return Seccion.objects.select_related("curso", "profesor").get(
                curso__codigo=curso, nombre=seccion_nombre
            )
        raise Seccion.DoesNotExist("Falta 'seccion_id' o ('curso' y 'seccion').")

    def _can_run_ml_here(self, user, seccion):
        if user.is_staff:
            return True
        if is_in_group(user, "DOCENTE") and seccion.profesor_id == user.id:
            return True
        return False

    @action(detail=False, methods=['post'], url_path='ml/proyeccion')
    def ml_proyeccion(self, request):
        try:
            seccion = self._resolve_seccion_from_request(request)
        except Seccion.DoesNotExist as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        if not self._can_run_ml_here(request.user, seccion):
            return Response({"detail": "No autorizado para esta sección."}, status=status.HTTP_403_FORBIDDEN)

        try:
            out = predict_final_for_seccion(seccion)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "seccion": {"id": seccion.id, "curso": seccion.curso.codigo, "seccion": seccion.nombre},
            "model": {"type": "linear_regression", **out["metrics"]},
            "predictions": out["predictions"]
        })

    @action(detail=False, methods=['post'], url_path='ml/riesgo')
    def ml_riesgo(self, request):
        try:
            seccion = self._resolve_seccion_from_request(request)
        except Seccion.DoesNotExist as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        if not self._can_run_ml_here(request.user, seccion):
            return Response({"detail": "No autorizado para esta sección."}, status=status.HTTP_403_FORBIDDEN)

        try:
            out = predict_risk_for_seccion(seccion)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "seccion": {"id": seccion.id, "curso": seccion.curso.codigo, "seccion": seccion.nombre},
            "model": {"type": "logistic_regression", **out["metrics"]},
            "predictions": out["predictions"]
        })

    # --- helpers de export ---
    def _filtered_queryset_for_export(self):
        qs = self.get_queryset().select_related('estudiante', 'seccion', 'seccion__curso')
        curso = self.request.GET.get('curso')
        seccion = self.request.GET.get('seccion')
        codigo = self.request.GET.get('codigo')
        if curso:
            qs = qs.filter(seccion__curso__codigo=curso)
        if seccion:
            qs = qs.filter(seccion__nombre=seccion)
        if codigo:
            qs = qs.filter(estudiante__codigo=codigo)
        return qs

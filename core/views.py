from django.http import HttpResponse
from django.db.models import Q
import csv
from openpyxl import Workbook

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied

from .models import Estudiante, Curso, Seccion, Nota
from .serializers import (
    EstudianteSerializer, CursoSerializer, SeccionSerializer, NotaSerializer
)
from .permissions import (
    IsStudentReadOwnNotas, IsTeacherOfSectionForWrite, is_in_group
)


class EstudianteViewSet(viewsets.ModelViewSet):
    queryset = Estudiante.objects.all()
    serializer_class = EstudianteSerializer

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


class CursoViewSet(viewsets.ModelViewSet):
    queryset = Curso.objects.all()
    serializer_class = CursoSerializer
    # Permisos globales se manejan vía DEFAULT_PERMISSION_CLASSES (IsAuthenticated)


class SeccionViewSet(viewsets.ModelViewSet):
    queryset = Seccion.objects.all()
    serializer_class = SeccionSerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return super().get_queryset()
        if is_in_group(user, "DOCENTE"):
            return Seccion.objects.filter(profesor=user)
        if is_in_group(user, "ESTUDIANTE"):
            return Seccion.objects.filter(notas__estudiante__user=user).distinct()
        return Seccion.objects.none()


class NotaViewSet(viewsets.ModelViewSet):
    queryset = Nota.objects.all()
    serializer_class = NotaSerializer
    permission_classes = [IsStudentReadOwnNotas, IsTeacherOfSectionForWrite]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return super().get_queryset()
        if is_in_group(user, "DOCENTE"):
            return Nota.objects.filter(seccion__profesor=user)
        if is_in_group(user, "ESTUDIANTE"):
            return Nota.objects.filter(estudiante__user=user)
        return Nota.objects.none()

    # Importante: controles extra para creación/edición (obj perms no cubren create)
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

    @action(detail=False, methods=['get'], url_path='export/csv')
    def export_csv(self, request):
        qs = self._filtered_queryset_for_export()
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

    # --- helpers ---
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

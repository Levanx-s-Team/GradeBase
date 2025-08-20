from rest_framework.permissions import BasePermission, SAFE_METHODS

def is_in_group(user, name): return user.is_authenticated and user.groups.filter(name=name).exists()

class IsStudentReadOwnNotas(BasePermission):
    """Estudiante: solo lectura de sus propias Notas."""
    def has_permission(self, request, view):
        return True  # filtra en queryset; bloquea escritura abajo
    def has_object_permission(self, request, view, obj):
        if is_in_group(request.user, "ESTUDIANTE"):
            if request.method in SAFE_METHODS:
                return getattr(obj.estudiante, "user_id", None) == request.user.id
            return False
        return True  # otros roles se evalúan en otra perm

class IsTeacherOfSectionForWrite(BasePermission):
    """Docente: puede escribir solo en sus secciones; lectura permitida."""
    def has_object_permission(self, request, view, obj):
        if is_in_group(request.user, "DOCENTE"):
            if request.method in SAFE_METHODS:
                return True
            return getattr(obj.seccion, "profesor_id", None) == request.user.id
        return True  # admin pasa por defecto

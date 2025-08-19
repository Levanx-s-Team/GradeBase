from django.contrib import admin
from .models import Estudiante, Curso, Seccion, Nota

admin.site.register(Estudiante)
admin.site.register(Curso)
admin.site.register(Seccion)
admin.site.register(Nota)

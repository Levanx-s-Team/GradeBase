from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator


NOTA_MIN = 0.0
NOTA_MAX = 20.0
nota_validators = [MinValueValidator(NOTA_MIN), MaxValueValidator(NOTA_MAX)]


class Estudiante(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, null=True, blank=True,
        help_text="(Opcional) Usuario vinculado para login"
    )
    codigo = models.CharField(max_length=20, unique=True)
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    email = models.EmailField(unique=True)

    def __str__(self):
        return f"{self.codigo} - {self.nombre} {self.apellido}"


class Curso(models.Model):
    codigo = models.CharField(max_length=20, unique=True)
    nombre = models.CharField(max_length=200)

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"


class Seccion(models.Model):
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE, related_name="secciones")
    nombre = models.CharField(max_length=20)  # ej. "A", "B"
    profesor = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="secciones_dictadas"
    )

    class Meta:
        unique_together = ("curso", "nombre")
        verbose_name = "Sección"
        verbose_name_plural = "Secciones"

    def __str__(self):
        prof = f" ({self.profesor.username})" if self.profesor else ""
        return f"{self.curso.nombre} - {self.nombre}{prof}"


class Nota(models.Model):
    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name="notas")
    seccion = models.ForeignKey(Seccion, on_delete=models.CASCADE, related_name="notas")

    avance1 = models.FloatField(null=True, blank=True, validators=nota_validators)
    avance2 = models.FloatField(null=True, blank=True, validators=nota_validators)
    avance3 = models.FloatField(null=True, blank=True, validators=nota_validators)
    participacion = models.FloatField(null=True, blank=True, validators=nota_validators)
    proyecto_final = models.FloatField(null=True, blank=True, validators=nota_validators)
    nota_final = models.FloatField(null=True, blank=True, validators=nota_validators)

    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("estudiante", "seccion")  # una fila por alumno x sección
        ordering = ["-actualizado"]

    def __str__(self):
        return f"{self.estudiante.codigo} - {self.seccion}"

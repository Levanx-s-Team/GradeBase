from django.db import models

class Estudiante(models.Model):
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
        return self.nombre


class Seccion(models.Model):
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE)
    nombre = models.CharField(max_length=20)  # ej. "A", "B"

    def __str__(self):
        return f"{self.curso.nombre} - {self.nombre}"


class Nota(models.Model):
    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE)
    seccion = models.ForeignKey(Seccion, on_delete=models.CASCADE)
    avance1 = models.FloatField(null=True, blank=True)
    avance2 = models.FloatField(null=True, blank=True)
    avance3 = models.FloatField(null=True, blank=True)
    participacion = models.FloatField(null=True, blank=True)
    proyecto_final = models.FloatField(null=True, blank=True)
    nota_final = models.FloatField(null=True, blank=True)

    def __str__(self):
        return f"{self.estudiante.codigo} - {self.seccion}"

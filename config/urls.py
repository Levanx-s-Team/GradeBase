# config/urls.py
from django.contrib import admin
from django.urls import path, include
from rest_framework import routers
from django.views.generic import RedirectView


# Swagger/OpenAPI
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)

# JWT (views)
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    # opcional:
    # TokenVerifyView,
)

# Importar ViewSets
from core.views import EstudianteViewSet, CursoViewSet, SeccionViewSet, NotaViewSet

# Router DRF
router = routers.DefaultRouter()
router.register(r"estudiantes", EstudianteViewSet, basename="estudiante")
router.register(r"cursos", CursoViewSet, basename="curso")
router.register(r"secciones", SeccionViewSet, basename="seccion")
router.register(r"notas", NotaViewSet, basename="nota")

urlpatterns = [
    path("", RedirectView.as_view(url="/api/docs/swagger/", permanent=False)),
    # Admin
    path("admin/", admin.site.urls),

    # API principal
    path("api/", include(router.urls)),

    # JWT (endpoints explícitos)
    path("api/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    # opcional:
    # path("api/token/verify/", TokenVerifyView.as_view(), name="token_verify"),

    # Schema JSON
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),

    # Documentación interactiva
    path("api/docs/swagger/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/docs/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]

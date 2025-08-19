from rest_framework.routers import DefaultRouter
from .views import EstudianteViewSet, CursoViewSet, SeccionViewSet, NotaViewSet

router = DefaultRouter()
router.register(r'estudiantes', EstudianteViewSet)
router.register(r'cursos', CursoViewSet)
router.register(r'secciones', SeccionViewSet)
router.register(r'notas', NotaViewSet)

urlpatterns = router.urls

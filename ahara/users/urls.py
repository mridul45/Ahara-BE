from rest_framework.routers import DefaultRouter
from .views import AuthViewSet  # your AuthViewSet is in users/views.py

router = DefaultRouter()
router.register(r"auth", AuthViewSet, basename="auth")   # -> /users/auth/register/

urlpatterns = router.urls
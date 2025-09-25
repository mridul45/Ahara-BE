from rest_framework.routers import DefaultRouter

from .views import ContentViewSet  # your AuthViewSet is in users/views.py

router = DefaultRouter()
router.register(r"content", ContentViewSet, basename="content")  # -> /users/content/

urlpatterns = router.urls

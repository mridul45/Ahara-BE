from rest_framework.routers import DefaultRouter
from .views import IntelligenceViewSet

app_name = "intelligence"

router = DefaultRouter()
router.register(r"", IntelligenceViewSet, basename="intelligence") 

urlpatterns = router.urls
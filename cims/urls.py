
from django.urls import path
from .views import upload_csv, run_import, db_probe, remove_duplicates, remove_overlaps, whoami

app_name = "cims"
urlpatterns = [
    path("upload/", upload_csv, name="upload"),
    path("import/", run_import, name="import"), 
    path("db-probe/", db_probe, name="db_probe"),
    path("duplicates/", remove_duplicates, name="remove_duplicates"),
    path("overlaps/", remove_overlaps, name="remove_overlaps"),
    path("whoami/" , whoami, name="whoami"),
]


from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('runsheet', views.runsheet, name='runsheet'),
    path('runsheet-staff-search', views.runsheet_staff_search, name='runsheet-staff-search'),
    path('runsheet-staff', views.runsheet_staff, name='runsheet-staff'),
    path('generate-pdf', views.generate_pdf, name='generate-pdf'),
    path('facility-list/', views.facility_list, name='facility-list'),
    path('facility-visits/', views.facility_visits, name='facility-visits')
    #path('facility-runsheet', views.facility_runsheet, name='facility-runsheet'),
    #path('runsheet2', views.runsheet2, name='runsheet2'),
]

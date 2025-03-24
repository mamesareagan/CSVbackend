"""URL configuration for the csv_processor app."""

from django.urls import path  # Import Django's path for URL routing
from .views import CSVProcessorView  # Import the view for CSV processing

app_name = 'csv_processor'  # Namespace for URL resolution

urlpatterns = [
    # Route for CSV processing endpoint
    path('process-csv/', CSVProcessorView.as_view(), name='process-csv'),
    # Maps /process-csv/ to CSVProcessorView, named 'process-csv' for reverse lookup
]
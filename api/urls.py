from django.urls import path, include
from rest_framework import serializers, routers, viewsets
from . import views

class Asset:
    def __init__(self, price, vol):
        self.price = price
        self.vol = vol


router = routers.DefaultRouter()

urlpatterns = [
    path('', views.apiOverview),
    path('assetList/', views.assetList),
]
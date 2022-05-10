from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('getData/', views.getData),
    path('master', views.master),
    path('dev/', views.dev),
    path('dev/juno', views.juno),
    path('getAllTxs/', views.get_all_txs),
]
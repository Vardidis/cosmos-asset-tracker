from django.shortcuts import render
from django.http import JsonResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .serializers import AssetSerializer
from .models import Asset

@api_view(['GET'])
def apiOverview(request):
    api_urls = {
        'Balance': '/balance/',
        'Delegations': '/delegations',
        'Rewards': '/rewards',
        'Transactions': '/assetList',
    }
    return Response(api_urls)

@api_view(['GET'])
def assetList(request):
    assets = Asset('ADA', 12.8)
    serializer = AssetSerializer(assets, many=True)
    return Response(serializer.data)
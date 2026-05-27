from __future__ import annotations

from django.urls import path

from apps.marketplace.views import (
    CampaignDetail,
    CampaignListCreate,
    MyHoldingsList,
    activate_campaign,
    buy_shards,
)

urlpatterns = [
    path("campaigns/", CampaignListCreate.as_view(), name="campaign-list"),
    path("campaigns/<uuid:pk>/", CampaignDetail.as_view(), name="campaign-detail"),
    path("campaigns/<uuid:pk>/activate/", activate_campaign, name="campaign-activate"),
    path("campaigns/<uuid:pk>/buy/", buy_shards, name="campaign-buy"),
    path("holdings/", MyHoldingsList.as_view(), name="holding-list"),
]

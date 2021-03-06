# -*- coding: utf-8 -*-

import datetime

from django.db.models import Q
from rest_framework.permissions import IsAuthenticated, DjangoObjectPermissions
from rest_framework.response import Response
from rest_framework import status

from EuLevo.utils.viewset import EuLevoModelViewSet
from eulevo.models import Deal, DoneDeal
from eulevo.models import Package
from eulevo.models import Travel
from eulevo.serializers import DealSerializer, DoneDealSerializer, DoneDealViewSerializer
from eulevo.tasks import notify_deal


class DealViewSet(EuLevoModelViewSet):
    queryset = Deal.objects.all()
    serializer_class = DealSerializer
    permission_classes = (
        IsAuthenticated,
        DjangoObjectPermissions
    )

    http_method_names = ['get', 'post', 'patch']

    def create(self, request, *args, **kwargs):
        try:
            request.data['user'] = request.user.pk
        except AttributeError:
            pass

        deal = Deal.objects.filter(
            package__pk=request.data.get('package'),
            travel__pk=request.data.get('travel')
        ).first()

        if deal:
            self.deal = deal
            request.data['status'] = 1
            response = self.partial_update(request, *args, **kwargs)
            data = {
                'type': request.user.pk == self.deal.package.owner.pk and 'travel' or 'package',
                'id': request.user.pk == self.deal.package.owner.pk and self.deal.travel.pk or self.deal.package.pk,
            }

            notify_deal.delay(user_pk=request.user.pk, deal_pk=self.deal.pk, data_message=data)
            return response
        response = super(DealViewSet, self).create(request, *args, **kwargs)
        notify_deal.delay(
            user_pk=request.user.pk,
            deal_pk=Deal.objects.filter(
                package__pk=request.data.get('package'),
                travel__pk=request.data.get('travel')
            ).first().serializable_value('pk')
        )
        return response

    def get_object(self):
        if hasattr(self, 'deal'):
            return self.deal
        return super(DealViewSet, self).get_object()

    def list(self, request, *args, **kwargs):
        request.GET = request.GET.copy()

        self.queryset = self.queryset.filter(
            Q(package__owner=request.user) | Q(travel__owner=request.user),
            travel__dt_travel__gte=datetime.date.today()
        ).exclude(status__in=(3, 4, 5))

        if 'travel' in request.GET.keys():
            travel = Travel.objects.filter(pk=request.GET.get('travel'), owner=request.user).first()
            if not travel:
                import json
                data = json.dumps({
                    'error': True,
                    'message': 'Travel doesn\'t exists'
                })
                return Response(data)
            del request.GET['travel']
            self.queryset = self.queryset.filter(travel=travel)

        if 'package' in request.GET.keys():
            package = Package.objects.filter(pk=request.GET.get('package'), owner=request.user).first()
            if not package:
                import json
                data = json.dumps({
                    'error': True,
                    'message': 'Package doesn\'t exists'
                })
                return Response(data)
            del request.GET['package']
            self.queryset = self.queryset.filter(package=package)
        return super(DealViewSet, self).list(request, *args, **kwargs)


class DoneDealViewSet(EuLevoModelViewSet):
    queryset = DoneDeal.objects.all()
    serializer_class = DoneDealSerializer
    permission_classes = (
        IsAuthenticated,
        DjangoObjectPermissions,
    )

    http_method_names = ['get', 'post']

    def check_deal(self, request):
        try:
            deal = Deal.objects.get(pk=request.data.get('deal'))
            if deal.status is not 1:
                return False
            return True
        except Deal.DoesNotExist:
            return False

    def list(self, request, *args, **kwargs):
        self.serializer_class = DoneDealViewSerializer
        return super(DoneDealViewSet, self).list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        if not self.check_deal(request):
            import json
            data = {
                'error': True,
                'message': 'Deal not available'
            }
            return Response(data, status=status.HTTP_400_BAD_REQUEST)
        response = super(DoneDealViewSet, self).create(request, *args, **kwargs)
        # manda a notificação pro fcm
        notify_deal.delay(user_pk=request.user.pk, deal_pk=request.data['deal'])
        return response

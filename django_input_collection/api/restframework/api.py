from django.core.exceptions import PermissionDenied

from rest_framework import viewsets, views
from rest_framework.decorators import action
from rest_framework.response import Response

from . import serializers
from ...collection.collectors import resolve, registry
from ...encoders import CollectionSpecificationJSONEncoder
from ... import models


class CollectorEnabledMixin(object):
    serializer_class = None  # Obtained at runtime via the collector

    # Utils
    def _get_value(self, k):
        """ Reads target key from request ``query_params`` or else ``data``. """
        return self.request.query_params.get(k, self.request.data.get(k))

    # Pagination class via collector
    def set_pagination_class(self):
        collector = self.get_collector()
        model = self.get_queryset().model
        pagination_class = collector.get_pagination_class(model)
        if pagination_class is not False:
            self.pagination_class = pagination_class

    @property
    def paginator(self):
        self.set_pagination_class()
        return super(CollectorEnabledMixin, self).paginator

    # Serializer class via collector
    def get_serializer_class(self):
        collector = self.get_collector()
        model = self.get_queryset().model
        return collector.get_serializer_class(model)

    def get_serializer_context(self):
        context = super(CollectorEnabledMixin, self).get_serializer_context()
        context['collector'] = self.get_collector()
        return context

    # Collector instance support
    def get_collection_request(self):
        request_id = self._get_value('request')
        collection_request = models.CollectionRequest.objects.filter(id=request_id).first()
        return collection_request

    def get_collector(self):
        if not hasattr(self, '_collector'):
            collector_class = self.get_collector_class()
            kwargs = self.get_collector_kwargs()
            self._collector = collector_class(**kwargs)
        return self._collector

    def get_collector_class(self):
        identifier = self._get_value('collector')
        try:
            collector_class = resolve(identifier)
        except KeyError:
            raise PermissionDenied('Unknown collector reference')
        return collector_class

    def get_collector_kwargs(self):
        kwargs = {
            'collection_request': self.get_collection_request(),
            'group': self._get_value('group'),
        }
        kwargs.update(self.get_collector_context())
        return kwargs

    def get_collector_context(self):
        context = {}
        if self.request.user.is_authenticated:
            context['user'] = self.request.user
        return context


class MeasureViewSet(CollectorEnabledMixin, viewsets.ModelViewSet):
    queryset = models.Measure.objects.all()


class CollectionGroupViewSet(CollectorEnabledMixin, viewsets.ModelViewSet):
    queryset = models.CollectionGroup.objects.all()


class CollectionRequestViewSet(CollectorEnabledMixin, viewsets.ModelViewSet):
    queryset = models.CollectionRequest.objects.all()

    @action(detail=True, methods=['get'])
    def specification(self, request, *args, **kwargs):
        collector = self.get_collector()
        response = Response(collector.specification)

        # There's no such thing as a per-response renderer class, so here we are.  Thanks DRF.
        # The request's accepted_renderer will be pushed to the response in finalize_response()
        request.accepted_renderer.encoder_class = CollectionSpecificationJSONEncoder

        return response

    def get_collection_request(self):
        instance = self.get_object()
        if 'pk' in self.kwargs:
            return self.get_object()
        return super(CollectionRequestViewSet, self).get_collection_request()


class CollectionInstrumentViewSet(CollectorEnabledMixin, viewsets.ModelViewSet):
    queryset = models.CollectionInstrument.objects.all()

    def filter_queryset(self, queryset):
        collection_request = self.get_collection_request()
        queryset = queryset.filter(collection_request=collection_request)

        filters = {}
        group = self._get_value('group')
        if group:
            filters['group'] = group

        queryset = queryset.filter(**filters)
        return queryset

    # def get_collection_request(self):
    #     if 'pk' in self.kwargs:
    #         return self.get_object().collection_request
    #     return super(CollectionInstrumentViewSet, self).get_collection_request()


class CollectedInputViewSet(CollectorEnabledMixin, viewsets.ModelViewSet):
    def get_queryset(self):
        return models.get_input_model().objects.all()

    def get_collection_request(self):
        if 'pk' in self.kwargs:
            return self.get_object().collection_request
        else:
            instrument_id = self._get_value('instrument')
            try:
                # FIXME: No query access control
                instrument = models.CollectionInstrument.objects.get(id=instrument_id)
                return instrument.collection_request
            except:
                pass
        return super(CollectedInputViewSet, self).get_collection_request()

    def get_serializer_context(self, write_mode=None):
        context = super(CollectedInputViewSet, self).get_serializer_context()

        if write_mode is None and self.request.method in ['PUT', 'POST', 'PATCH']:
            write_mode = True

        if write_mode:
            context['write_mode'] = write_mode

        return context

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instrument = instance.instrument
        collector = self.get_collector()
        self.perform_destroy(instance)
        return collector.get_destroy_response(instrument)

    def perform_destroy(self, instance):
        """ Forwards deletion work to the collector instance. """
        # The create and update methods exist on the serializer for convenience of access to the
        # developer, but destroy() never touches a serializer, so customization must occur on
        # at the collector class instead.
        collector = self.get_collector()
        collector.remove(instance.instrument, instance)


class CollectorRegistryView(views.APIView):
    def get(self, request, *args, **kwargs):
        return Response({
            uid: '.'.join([cls.__module__, cls.__name__]) for uid, cls in sorted(registry.items())
        })
